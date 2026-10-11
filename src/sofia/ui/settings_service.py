"""Durable settings operations shared by the desktop settings controls."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.safe.secret_store import ProtectedSecretStore
from sofia.mobile.provisioning import mobile_companion_ready
from .control_center import DesktopControlSettings, DesktopControlSettingsStore, GameMode
from .windows_startup import configure_windows_startup


def save_settings(
    path: Path,
    desktop: DesktopControlSettings,
    runtime: RuntimeUserSettings,
    *,
    host_id: str,
    secret_changes: dict[str, str | None] | None = None,
    secrets: ProtectedSecretStore | None = None,
) -> str:
    """Commit all SQLite owners together; compensate secrets on a failed save.

    Windows registry configuration is an external effect. A registry failure
    must not discard otherwise valid durable preferences.
    """
    if not isinstance(desktop, DesktopControlSettings) or not isinstance(runtime, RuntimeUserSettings):
        raise TypeError("Validated desktop and runtime settings required")
    if runtime.avatar_daily_outfit is not None:
        from sofia.avatar.wardrobe_review import WardrobeReviewStore
        catalog = WardrobeReviewStore(path).catalog()
        if runtime.avatar_daily_outfit not in {plan.outfit_id for plan in catalog.presets if not plan.private_only}:
            raise ValueError("Daily outfit must be an approved public wardrobe preset")
    desktop_store = DesktopControlSettingsStore(path)
    runtime_store = RuntimeUserSettingsStore(path)
    activity = HostActivityStore(path)
    secrets = secrets or ProtectedSecretStore.for_state_path(path)
    changes = secret_changes or {}
    if set(changes) - {"discord-token", "home-assistant-token"}:
        raise ValueError("Unknown settings secret")
    outreach_enabled = runtime.outreach is not None and runtime.outreach.enabled
    for enabled, key in ((runtime.discord_enabled, "discord-token"), (runtime.home_assistant_enabled, "home-assistant-token")):
        present = bool(changes[key]) if key in changes else secrets.exists(key)
        if enabled and not present:
            raise ValueError(f"Enabled integration requires a stored {key}")
    outreach_token_present = (
        bool(changes["home-assistant-token"])
        if "home-assistant-token" in changes
        else secrets.exists("home-assistant-token")
    )
    outreach_ready = bool(
        outreach_enabled
        and runtime.outreach is not None
        and (
            runtime.outreach.delivery_channel == "desktop"
            or (
                runtime.outreach.delivery_channel == "mobile"
                and mobile_companion_ready(path)
            )
            or (
                runtime.outreach.delivery_channel == "discord"
                and runtime.discord_enabled
                and runtime.discord_dm_channel_id is not None
            )
            or (
                runtime.outreach.delivery_channel == "home_assistant"
                and runtime.outreach.notification_service
                and runtime.home_assistant_url
                and outreach_token_present
            )
        )
    )
    previous = desktop_store.load()
    backups = {}
    for key in changes:
        target = secrets.root / secrets._name(key)
        backups[target] = target.read_bytes() if target.exists() else None
    now = datetime.now(timezone.utc)
    try:
        for key, value in changes.items():
            if value is None:
                secrets.clear(key)
            else:
                secrets.set(key, value)
        with closing(sqlite3.connect(path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            runtime_store.save(runtime, at=now, connection=db)
            desktop_store.save(desktop, at=now, connection=db)
            activity.set_override(host_id, {
                GameMode.AUTO: ActivityMode.AUTO, GameMode.ON: ActivityMode.GAMING,
                GameMode.OFF: ActivityMode.NORMAL,
            }[desktop.game_mode], at=now, connection=db)
    except Exception:
        for target, ciphertext in backups.items():
            if ciphertext is None:
                target.unlink(missing_ok=True)
            else:
                temporary = target.with_suffix(".restore")
                temporary.write_bytes(ciphertext)
                temporary.replace(target)
        raise
    warning = ""
    if sys.platform == "win32":
        try:
            configure_windows_startup(desktop.start_with_windows, state_path=path)
        except OSError as exc:
            warning = f" Windows startup registration failed: {exc}. Save again to retry."
    elif desktop.start_with_windows != previous.start_with_windows and desktop.start_with_windows:
        warning = " Windows startup registration is available on Windows."
    if outreach_enabled and not outreach_ready:
        if runtime.outreach is not None and runtime.outreach.delivery_channel == "mobile":
            warning += " Proactive mobile outreach requires the authenticated mobile endpoint and pairing token."
        elif runtime.outreach is not None and runtime.outreach.delivery_channel == "discord":
            warning += " Proactive Discord outreach requires enabled Discord, its protected token, and a verified owner DM channel. Choose desktop delivery to use the tray immediately."
        else:
            warning += " Proactive outreach is enabled but its selected Home Assistant delivery requires a URL, protected token, and notification service. Choose desktop delivery to use the tray without Home Assistant."
    return "Saved to the canonical database. Environment and tray controls refresh automatically; restart Sofía for other changes." + warning


def database_diagnostics(path: Path) -> str:
    """Inspect the selected canonical database without evaluating arbitrary SQL."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        integrity = db.execute("PRAGMA quick_check").fetchall()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return f"Database: {path}\nIntegrity: {integrity}\nSize: {path.stat().st_size:,} bytes\nTables ({len(tables)}):\n" + "\n".join(row[0] for row in tables)



def install_approved_configured_model(
    path: Path,
    *,
    role: str,
    expected_model: str,
    host_id: str,
    approval_id: str,
):
    """Execute one explicitly owner-approved local Ollama model installation.

    The existing one-use SAFE execution approval is consumed *before* the
    backend pull.  A saved auto-install preference, model output or approval
    for another host/role/model cannot trigger this action. The effective
    production configuration is reloaded to avoid approving stale settings.

    The function is called only by the desktop owner's explicit Settings
    action, and never by an autonomous scheduler or model-generated tool.
    """
    from datetime import datetime, timezone

    from sofia.cognition.model_lifecycle import (
        CognitiveModelRole, ModelLifecycleManager, ModelLifecycleStatus,
    )
    from sofia.config import create_production_configuration
    from sofia.config.cognitive_models import CognitiveModelSelection
    from sofia.integrations.ollama import OllamaAdapter
    from sofia.safe.execution_approval import ExecutionApprovalVerifier
    from sofia.safe.operator_stop import OperatorStopStore

    if type(role) is not str or role not in {"primary", "secondary"}:
        raise ValueError("only named configured model roles can be installed")
    if (
        not isinstance(expected_model, str) or not expected_model.strip()
        or len(expected_model) > 200
        or not isinstance(host_id, str) or not host_id.strip()
        or len(host_id) > 200
        or not isinstance(approval_id, str) or not approval_id.strip()
        or len(approval_id) > 300
    ):
        raise ValueError("exact model, local host, and owner approval required")
    canonical_path = Path(path)
    if OperatorStopStore(canonical_path).current().active:
        raise PermissionError("operator stop forbids model installation")
    configuration = create_production_configuration(state_path=canonical_path)
    selection = CognitiveModelSelection.from_configuration(configuration)
    selected = CognitiveModelRole(role)
    provider = (
        selection.primary
        if selected is CognitiveModelRole.PRIMARY
        else selection.secondary
    )
    if (
        provider is None or provider.provider != "ollama"
        or provider.model != expected_model
    ):
        raise PermissionError("configured local Ollama role changed since approval")

    manager = ModelLifecycleManager(
        selection=selection,
        policy=configuration.model_lifecycle,
        backend=OllamaAdapter(),
    )
    verifier = ExecutionApprovalVerifier(canonical_path)

    def consume_exact_approval(ref, approved_role, model):
        if (
            ref != approval_id or approved_role is not selected
            or model != expected_model
        ):
            return False
        if OperatorStopStore(canonical_path).current().active:
            return False
        verifier.consume(
            approval_id=approval_id,
            capability="cognition.model.install",
            parameters={
                "role": role,
                "model": expected_model,
                "host_id": host_id,
            },
            now=datetime.now(timezone.utc),
        )
        return True

    from sofia.safe.audit import AuditChain

    def record_outcome(event_type: str, reason: str) -> None:
        AuditChain(canonical_path).append(
            actor_id="system:owner-model-installer",
            event_type=event_type,
            event_id=f"cognition-model-install:{approval_id}",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "approval_id": approval_id,
                "role": role,
                "model": expected_model,
                "host_id": host_id,
                "result": reason,
            },
        )

    try:
        status = manager.install(
            selected,
            operator_approval_ref=approval_id,
            verify_operator_approval=consume_exact_approval,
        )
    except Exception as exc:
        # A failed pull may have written partial Ollama assets; the exact
        # operator approval is never replayed, and outcome remains auditable.
        record_outcome("cognition.model.install.failed", type(exc).__name__)
        raise
    record_outcome("cognition.model.install.observed", status.state.value)
    return status
