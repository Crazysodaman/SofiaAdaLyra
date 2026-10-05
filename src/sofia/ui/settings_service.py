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
        and runtime.outreach.notification_service
        and runtime.home_assistant_url
        and outreach_token_present
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
        warning += " Proactive outreach is enabled but remains inactive until its Home Assistant URL, protected token, and notification service are configured."
    return "Saved to the canonical database. Environment and tray controls refresh automatically; restart Sofía for other changes." + warning


def database_diagnostics(path: Path) -> str:
    """Inspect the selected canonical database without evaluating arbitrary SQL."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        integrity = db.execute("PRAGMA quick_check").fetchall()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return f"Database: {path}\nIntegrity: {integrity}\nSize: {path.stat().st_size:,} bytes\nTables ({len(tables)}):\n" + "\n".join(row[0] for row in tables)
