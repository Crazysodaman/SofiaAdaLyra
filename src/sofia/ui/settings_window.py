"""Tkinter master settings window for the Sofía desktop/tray client."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
import json
import sqlite3
from uuid import uuid4

from sofia.config import create_production_configuration
from sofia.config.model_catalog import (
    RECOMMENDED_PRIMARY_CONTEXT_SIZE,
    RECOMMENDED_PRIMARY_MODEL,
    RECOMMENDED_SECONDARY_CONTEXT_SIZE,
    RECOMMENDED_SECONDARY_MODEL,
    known_local_model_names,
)
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.environment.model import LocationSubject
from sofia.machine.discovery import create_machine_discovery
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.ops.capability import OpsToolService
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.safe.secret_store import ProtectedSecretStore
from sofia.safe.permissions import (
    PermissionStore,
    capability_permission_policy,
    grantable_capabilities,
)
from .control_center import (
    DesktopControlSettings,
    DesktopControlSettingsStore,
    GameMode,
    MASTER_SETTINGS_SECTIONS,
    RemoteChatMode,
)
from .windows_startup import configure_windows_startup


def _ensure_state_database(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path):
            pass


def _local_host_id() -> str:
    return create_machine_discovery().discover().identity.machine_id


def _activity_override(mode: GameMode) -> ActivityMode:
    return {
        GameMode.AUTO: ActivityMode.AUTO,
        GameMode.ON: ActivityMode.GAMING,
        GameMode.OFF: ActivityMode.NORMAL,
    }[mode]


def _optional_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _optional_int(value: str, label: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    if not stripped.isascii() or not stripped.isdigit():
        raise ValueError(f"{label} must contain digits only")
    parsed = int(stripped)
    if parsed <= 0 or parsed >= (1 << 64):
        raise ValueError(f"{label} must be a positive Discord snowflake")
    return parsed


def _thinking_ui_value(value: bool | str) -> str:
    if value is True:
        return "on"
    if value is False:
        return "off"
    return value


def _thinking_setting(value: str) -> bool | str:
    normalized = value.strip().casefold()
    if normalized == "off":
        return False
    if normalized == "on":
        return True
    if normalized in {"low", "medium", "high", "xhigh"}:
        return normalized
    raise ValueError("Thinking must be off, on, low, medium, high, or xhigh")


def _optional_float(value: str, label: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric") from exc


def _permission_scope(value: str) -> dict:
    stripped = value.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("Permission scope must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Permission scope must be a JSON object")
    return parsed


def _csv_values(value: str) -> tuple[str, ...]:
    values = []
    for raw in value.split(","):
        item = raw.strip()
        if item and item not in values:
            values.append(item)
    return tuple(values)


def _network_scopes(value: str) -> tuple[str, ...]:
    scopes = []
    for raw in _csv_values(value):
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError as exc:
            raise ValueError(
                f"Invalid discovery scope {raw!r}; use CIDR such as 192.168.1.0/24"
            ) from exc
        normalized = str(network)
        if normalized not in scopes:
            scopes.append(normalized)
    return tuple(scopes)


def _optional_expiry_minutes(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    if not stripped.isascii() or not stripped.isdigit():
        raise ValueError("Grant expiry must be whole minutes or blank")
    minutes = int(stripped)
    if minutes <= 0:
        raise ValueError("Grant expiry must be positive")
    return minutes


def run_settings_window() -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    config = create_production_configuration()
    _ensure_state_database(config.state_path)
    store = DesktopControlSettingsStore(config.state_path)
    runtime_store = RuntimeUserSettingsStore(config.state_path)
    secrets = ProtectedSecretStore.for_state_path(config.state_path)
    permission_store = PermissionStore(config.state_path)
    execution_approvals = ExecutionApprovalVerifier(config.state_path)
    private_authority = permission_store.private_adult_authority()
    activity = HostActivityStore(config.state_path)
    current = store.enforce_canonical_local_chat(
        at=datetime.now(timezone.utc),
    )
    runtime = runtime_store.load()

    root = tk.Tk()
    root.title("Sofía Settings")
    root.geometry("920x720")
    root.minsize(760, 580)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=12)

    frames = {}
    for name in MASTER_SETTINGS_SECTIONS:
        frame = ttk.Frame(notebook, padding=14)
        notebook.add(frame, text=name)
        frames[name] = frame

    start_windows = tk.BooleanVar(value=current.start_with_windows)
    game_mode = tk.StringVar(value=current.game_mode.value)
    runtime_service = tk.StringVar(value=current.runtime_service_name)
    llm_service = tk.StringVar(value=current.llm_service_name)

    provider_model = tk.StringVar(value=runtime.provider_model)
    provider_context = tk.StringVar(value=str(runtime.provider_context_size))
    provider_thinking = tk.StringVar(
        value=_thinking_ui_value(runtime.provider_thinking)
    )
    cognitive_routing_enabled = tk.BooleanVar(
        value=runtime.cognitive_routing_enabled
    )
    cognitive_primary_model = tk.StringVar(
        value=runtime.cognitive_primary_model
    )
    cognitive_secondary_model = tk.StringVar(
        value=runtime.cognitive_secondary_model
    )
    cognitive_primary_context = tk.StringVar(
        value=str(runtime.cognitive_primary_context_size)
    )
    cognitive_secondary_context = tk.StringVar(
        value=str(runtime.cognitive_secondary_context_size)
    )
    cognitive_verify_enabled = tk.BooleanVar(
        value=runtime.cognitive_verify_enabled
    )
    cognitive_model_auto_manage = tk.BooleanVar(
        value=runtime.cognitive_model_auto_manage
    )
    cognitive_model_auto_install = tk.BooleanVar(
        value=runtime.cognitive_model_auto_install
    )
    cognitive_model_idle_unload_seconds = tk.StringVar(
        value=str(runtime.cognitive_model_idle_unload_seconds)
    )
    cognitive_model_keep_alive = tk.StringVar(
        value=runtime.cognitive_model_keep_alive
    )

    discord_enabled = tk.BooleanVar(value=runtime.discord_enabled)
    discord_owner = tk.StringVar(
        value="" if runtime.discord_owner_user_id is None
        else str(runtime.discord_owner_user_id)
    )
    discord_bot = tk.StringVar(
        value="" if runtime.discord_bot_user_id is None
        else str(runtime.discord_bot_user_id)
    )
    discord_channel = tk.StringVar(
        value="" if runtime.discord_dm_channel_id is None
        else str(runtime.discord_dm_channel_id)
    )
    discord_token = tk.StringVar(value="")
    discord_clear_token = tk.BooleanVar(value=False)
    discord_token_status = tk.StringVar(
        value=(
            "Token stored securely"
            if secrets.exists("discord-token")
            else "No stored token"
        )
    )

    ha_enabled = tk.BooleanVar(value=runtime.home_assistant_enabled)
    ha_url = tk.StringVar(value=runtime.home_assistant_url or "")
    ha_token = tk.StringVar(value="")
    ha_clear_token = tk.BooleanVar(value=False)
    ha_token_status = tk.StringVar(
        value=(
            "Token stored securely"
            if secrets.exists("home-assistant-token")
            else "No stored token"
        )
    )
    ha_weather = tk.StringVar(
        value=runtime.home_assistant_weather_entity or ""
    )
    ha_temp = tk.StringVar(
        value=runtime.home_assistant_indoor_temperature_entity or ""
    )
    ha_humidity = tk.StringVar(
        value=runtime.home_assistant_indoor_humidity_entity or ""
    )
    ha_location = tk.StringVar(
        value=runtime.home_assistant_current_location_entity or ""
    )
    ha_location_subject = tk.StringVar(
        value=(
            ""
            if runtime.home_assistant_current_location_subject is None
            else runtime.home_assistant_current_location_subject.value
        )
    )

    location_label = tk.StringVar(value=runtime.location_label or "")
    location_timezone = tk.StringVar(value=runtime.location_timezone or "")
    location_latitude = tk.StringVar(
        value=(
            ""
            if runtime.location_latitude is None
            else str(runtime.location_latitude)
        )
    )
    location_longitude = tk.StringVar(
        value=(
            ""
            if runtime.location_longitude is None
            else str(runtime.location_longitude)
        )
    )
    location_subject = tk.StringVar(value=runtime.location_subject.value)
    nws_enabled = tk.BooleanVar(value=runtime.nws_enabled)
    nws_subject = tk.StringVar(value=runtime.nws_location_subject.value)
    nws_station_id = tk.StringVar(value=runtime.nws_station_id or "")
    nws_user_agent = tk.StringVar(value=runtime.nws_user_agent)
    refresh_seconds = tk.StringVar(value=str(runtime.refresh_seconds))
    weather_age = tk.StringVar(value=str(runtime.weather_max_age_seconds))
    indoor_age = tk.StringVar(value=str(runtime.indoor_max_age_seconds))
    current_location_age = tk.StringVar(
        value=str(runtime.current_location_max_age_seconds)
    )

    fleet_discovery_enabled = tk.BooleanVar(
        value=runtime.fleet_discovery_enabled
    )
    fleet_discovery_scopes = tk.StringVar(
        value=", ".join(runtime.fleet_discovery_scopes)
    )
    fleet_discovery_targets = tk.StringVar(
        value=", ".join(runtime.fleet_discovery_targets)
    )
    fleet_discovery_interval = tk.StringVar(
        value=str(runtime.fleet_discovery_interval_seconds)
    )
    fleet_discovery_max_hosts = tk.StringVar(
        value=str(runtime.fleet_discovery_max_hosts_per_scope)
    )

    private_chat = tk.BooleanVar(value=private_authority.private_chat)
    adult_chat = tk.BooleanVar(value=private_authority.adult_chat)
    adult_avatar = tk.BooleanVar(value=private_authority.adult_avatar)
    adult_external_delivery = tk.BooleanVar(
        value=private_authority.adult_external_delivery
    )
    grant_capability = tk.StringVar(
        value=(
            grantable_capabilities()[0]
            if grantable_capabilities()
            else ""
        )
    )
    grant_scope = tk.StringVar(value="{}")
    grant_expiry_minutes = tk.StringVar(value="")

    general = frames["General"]
    ttk.Label(
        general,
        text=(
            "Closing the chat window leaves the independently running tray "
            "agent available. Use Exit UI from the tray to close the tray."
        ),
        wraplength=720,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Checkbutton(
        general,
        text="Start tray client with Windows",
        variable=start_windows,
    ).pack(anchor="w", pady=4)

    chat = frames["Chat"]
    ttk.Label(chat, text="Canonical conversation database").pack(anchor="w")
    ttk.Label(
        chat,
        text=str(config.state_path),
        wraplength=720,
    ).pack(anchor="w", pady=(2, 8))
    ttk.Label(
        chat,
        text=(
            "Desktop chat uses this one canonical Sofía state database. "
            "Fleet may place LLM work on another host, but chat/state authority "
            "does not move independently until state mobility and fencing are "
            "implemented."
        ),
        wraplength=720,
    ).pack(anchor="w")

    workloads = frames["Workloads"]
    ttk.Label(workloads, text="Game Mode").pack(anchor="w")
    ttk.Combobox(
        workloads,
        textvariable=game_mode,
        values=tuple(value.value for value in GameMode),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 10))
    ttk.Label(
        workloads,
        text=(
            "Auto uses observed activity. On protects this machine for "
            "gaming. Off disables gaming protection."
        ),
        wraplength=720,
    ).pack(anchor="w")

    models = frames["Models"]
    ttk.Label(models, text="Ollama model").pack(anchor="w")
    ttk.Combobox(
        models,
        textvariable=provider_model,
        values=known_local_model_names(),
        state="normal",
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(models, text="Context size").pack(anchor="w")
    ttk.Entry(
        models,
        textvariable=provider_context,
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(models, text="Thinking / reasoning effort").pack(anchor="w")
    ttk.Combobox(
        models,
        textvariable=provider_thinking,
        values=("off", "on", "low", "medium", "high", "xhigh"),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 4))
    ttk.Label(
        models,
        text=(
            "On uses the model's default thinking mode. Named levels are "
            "passed through to Ollama for models that support them."
        ),
        wraplength=720,
    ).pack(anchor="w", pady=(0, 12))

    routing_frame = ttk.LabelFrame(
        models,
        text="Dual-model cognition",
        padding=8,
    )
    routing_frame.pack(anchor="w", fill="x", pady=(0, 12))
    ttk.Checkbutton(
        routing_frame,
        text="Enable multi-model cognitive routing",
        variable=cognitive_routing_enabled,
    ).pack(anchor="w", pady=(0, 6))
    for label, variable in (
        ("Primary model", cognitive_primary_model),
        ("Secondary / open model", cognitive_secondary_model),
    ):
        ttk.Label(routing_frame, text=label).pack(anchor="w")
        ttk.Combobox(
            routing_frame,
            textvariable=variable,
            values=known_local_model_names(),
            state="normal",
        ).pack(anchor="w", fill="x", pady=(2, 5))
    for label, variable in (
        ("Primary context size", cognitive_primary_context),
        ("Secondary context size", cognitive_secondary_context),
    ):
        ttk.Label(routing_frame, text=label).pack(anchor="w")
        ttk.Entry(
            routing_frame,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 5))

    def load_recommended_pair() -> None:
        cognitive_primary_model.set(RECOMMENDED_PRIMARY_MODEL)
        cognitive_secondary_model.set(RECOMMENDED_SECONDARY_MODEL)
        cognitive_primary_context.set(str(RECOMMENDED_PRIMARY_CONTEXT_SIZE))
        cognitive_secondary_context.set(str(RECOMMENDED_SECONDARY_CONTEXT_SIZE))
        cognitive_routing_enabled.set(True)

    ttk.Button(
        routing_frame,
        text="Load recommended local pair",
        command=load_recommended_pair,
    ).pack(anchor="w", pady=(2, 6))
    ttk.Checkbutton(
        routing_frame,
        text="Enable two-pass verification for explicit verify requests",
        variable=cognitive_verify_enabled,
    ).pack(anchor="w", pady=(2, 4))
    ttk.Label(
        routing_frame,
        text=(
            "Model identities are owner-configurable. Routing uses the "
            "selected role assignments, and tool-enabled requests remain "
            "primary-only."
        ),
        wraplength=690,
    ).pack(anchor="w")

    lifecycle_frame = ttk.LabelFrame(
        models,
        text="Automatic model residency",
        padding=8,
    )
    lifecycle_frame.pack(anchor="w", fill="x", pady=(0, 12))
    ttk.Checkbutton(
        lifecycle_frame,
        text="Automatically wake and unload configured models",
        variable=cognitive_model_auto_manage,
    ).pack(anchor="w", pady=(0, 4))
    ttk.Checkbutton(
        lifecycle_frame,
        text="Automatically install missing configured models",
        variable=cognitive_model_auto_install,
    ).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        lifecycle_frame,
        text="Unload after idle seconds",
    ).pack(anchor="w")
    ttk.Entry(
        lifecycle_frame,
        textvariable=cognitive_model_idle_unload_seconds,
    ).pack(anchor="w", fill="x", pady=(2, 5))
    ttk.Label(
        lifecycle_frame,
        text="Ollama keep-alive after wake",
    ).pack(anchor="w")
    ttk.Entry(
        lifecycle_frame,
        textvariable=cognitive_model_keep_alive,
    ).pack(anchor="w", fill="x", pady=(2, 5))
    ttk.Label(
        lifecycle_frame,
        text=(
            "When enabled, Sofía's runtime stays alive even if every model "
            "is unloaded. A chat, reflection, or other cognitive request can "
            "wake the configured model role again automatically."
        ),
        wraplength=690,
    ).pack(anchor="w")

    ttk.Label(models, text="LLM Windows service name").pack(anchor="w")
    ttk.Entry(
        models,
        textvariable=llm_service,
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(models, text="Sofía runtime Windows service name").pack(
        anchor="w"
    )
    ttk.Entry(
        models,
        textvariable=runtime_service,
    ).pack(anchor="w", fill="x", pady=(2, 8))

    integrations = frames["Integrations"]
    integration_tabs = ttk.Notebook(integrations)
    integration_tabs.pack(fill="both", expand=True)
    discord_frame = ttk.Frame(integration_tabs, padding=10)
    ha_frame = ttk.Frame(integration_tabs, padding=10)
    integration_tabs.add(discord_frame, text="Discord")
    integration_tabs.add(ha_frame, text="Home Assistant")
    ttk.Checkbutton(
        discord_frame,
        text="Enable owner-only Discord DM integration",
        variable=discord_enabled,
    ).pack(anchor="w", pady=(0, 8))
    for label, variable in (
        ("Owner user ID", discord_owner),
        ("Bot user ID", discord_bot),
        ("DM channel ID (optional, auto-detected)", discord_channel),
    ):
        ttk.Label(discord_frame, text=label).pack(anchor="w")
        ttk.Entry(
            discord_frame,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(
        discord_frame,
        text=(
            "Leave DM Channel ID blank to let Sofía resolve the authenticated "
            "private DM automatically. A stored value is treated as a cache "
            "and corrected if Discord resolves a different channel."
        ),
        wraplength=700,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Label(discord_frame, text="Bot token").pack(anchor="w")
    ttk.Entry(
        discord_frame,
        textvariable=discord_token,
        show="•",
    ).pack(anchor="w", fill="x", pady=(2, 4))
    ttk.Label(
        discord_frame,
        textvariable=discord_token_status,
    ).pack(anchor="w")
    ttk.Checkbutton(
        discord_frame,
        text="Clear stored Discord token on Save",
        variable=discord_clear_token,
    ).pack(anchor="w", pady=(4, 0))
    ttk.Label(
        discord_frame,
        text=(
            "Leave the token box blank to keep the existing protected "
            "token. A new value replaces it."
        ),
        wraplength=700,
    ).pack(anchor="w", pady=(6, 0))

    ttk.Checkbutton(
        ha_frame,
        text="Enable Home Assistant environment integration",
        variable=ha_enabled,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Label(ha_frame, text="Base URL").pack(anchor="w")
    ttk.Entry(
        ha_frame,
        textvariable=ha_url,
    ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(ha_frame, text="Long-lived access token").pack(anchor="w")
    ttk.Entry(
        ha_frame,
        textvariable=ha_token,
        show="•",
    ).pack(anchor="w", fill="x", pady=(2, 4))
    ttk.Label(
        ha_frame,
        textvariable=ha_token_status,
    ).pack(anchor="w")
    ttk.Checkbutton(
        ha_frame,
        text="Clear stored Home Assistant token on Save",
        variable=ha_clear_token,
    ).pack(anchor="w", pady=(4, 8))
    for label, variable in (
        ("Weather entity", ha_weather),
        ("Indoor temperature entity", ha_temp),
        ("Indoor humidity entity", ha_humidity),
        ("Current-location entity", ha_location),
    ):
        ttk.Label(ha_frame, text=label).pack(anchor="w")
        ttk.Entry(
            ha_frame,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(ha_frame, text="Current-location subject").pack(anchor="w")
    ttk.Combobox(
        ha_frame,
        textvariable=ha_location_subject,
        values=("", "user", "site", "host"),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 0))

    environment = frames["Environment"]
    environment_tabs = ttk.Notebook(environment)
    environment_tabs.pack(fill="both", expand=True)
    location_frame = ttk.Frame(environment_tabs, padding=10)
    weather_frame = ttk.Frame(environment_tabs, padding=10)
    environment_tabs.add(location_frame, text="Location")
    environment_tabs.add(weather_frame, text="Weather")
    ttk.Label(
        location_frame,
        text=(
            "This is configured location context, not proof that a person "
            "or device is physically there now."
        ),
        wraplength=700,
    ).pack(anchor="w", pady=(0, 8))
    for label, variable in (
        ("Location label", location_label),
        ("Timezone, e.g. America/Chicago", location_timezone),
        ("Latitude (optional)", location_latitude),
        ("Longitude (optional)", location_longitude),
    ):
        ttk.Label(location_frame, text=label).pack(anchor="w")
        ttk.Entry(
            location_frame,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(location_frame, text="Location subject").pack(anchor="w")
    ttk.Combobox(
        location_frame,
        textvariable=location_subject,
        values=("user", "site", "host"),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 0))

    ttk.Checkbutton(
        weather_frame,
        text="Enable National Weather Service provider",
        variable=nws_enabled,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Label(weather_frame, text="NWS location subject").pack(anchor="w")
    ttk.Combobox(
        weather_frame,
        textvariable=nws_subject,
        values=("user", "site", "host"),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(weather_frame, text="NWS observation station").pack(anchor="w")
    ttk.Entry(
        weather_frame,
        textvariable=nws_station_id,
    ).pack(anchor="w", fill="x", pady=(2, 6))
    ttk.Label(weather_frame, text="NWS User-Agent").pack(anchor="w")
    ttk.Entry(
        weather_frame,
        textvariable=nws_user_agent,
    ).pack(anchor="w", fill="x", pady=(2, 8))
    for label, variable in (
        ("Refresh seconds", refresh_seconds),
        ("Weather max age seconds", weather_age),
        ("Indoor max age seconds", indoor_age),
        ("Current-location max age seconds", current_location_age),
    ):
        ttk.Label(weather_frame, text=label).pack(anchor="w")
        ttk.Entry(
            weather_frame,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 6))

    fleet_settings = frames["Fleet"]
    ttk.Label(
        fleet_settings,
        text=(
            "Approved scopes power read-only network discovery. Fleet "
            "auto-discovery may additionally record untrusted candidates, but "
            "adding/trusting a computer still requires exact approval."
        ),
        wraplength=720,
    ).pack(anchor="w", pady=(0, 8))
    ttk.Checkbutton(
        fleet_settings,
        text="Enable automatic Fleet candidate discovery",
        variable=fleet_discovery_enabled,
    ).pack(anchor="w", pady=(0, 8))
    for label, variable in (
        (
            "Approved network scopes (comma-separated CIDR)",
            fleet_discovery_scopes,
        ),
        (
            "Explicit Fleet-agent targets (optional, comma-separated)",
            fleet_discovery_targets,
        ),
        ("Discovery interval seconds (minimum 30)", fleet_discovery_interval),
        ("Maximum hosts per scope (1-1024)", fleet_discovery_max_hosts),
    ):
        ttk.Label(fleet_settings, text=label).pack(anchor="w")
        ttk.Entry(
            fleet_settings,
            textvariable=variable,
        ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(
        fleet_settings,
        text=(
            "Read-only network discovery can use approved scopes even when "
            "automatic Fleet candidate discovery is disabled."
        ),
        wraplength=720,
    ).pack(anchor="w")

    permissions = frames["Permissions"]
    ttk.Label(
        permissions,
        text=(
            "One permission engine governs observation, safe maintenance, "
            "standing reversible grants, protected actions, and authority "
            "changes. Read-only work never needs a per-use approval."
        ),
        wraplength=720,
    ).pack(anchor="w", pady=(0, 8))

    levels_frame = ttk.LabelFrame(
        permissions,
        text="Permission levels",
        padding=8,
    )
    levels_frame.pack(anchor="w", fill="x", pady=(0, 10))
    for level_text in (
        "1  Observe / Read — automatic, bounded read-only work.",
        "2  Safe Autonomous — bounded maintenance and internal housekeeping.",
        "3  Reversible / Scoped — standing grant or exact one-time approval.",
        "4  Protected / High Impact — exact approval for the action.",
        "5  Never Self-Authorized — only Sparks may change authority.",
    ):
        ttk.Label(
            levels_frame,
            text=level_text,
            wraplength=690,
        ).pack(anchor="w", pady=1)

    privacy_frame = ttk.LabelFrame(
        permissions,
        text="Private / adult authority",
        padding=8,
    )
    privacy_frame.pack(anchor="w", fill="x", pady=(0, 10))
    ttk.Checkbutton(
        privacy_frame,
        text="Allow private owner chat context",
        variable=private_chat,
    ).pack(anchor="w", pady=2)
    ttk.Checkbutton(
        privacy_frame,
        text="Allow adult chat in authenticated private owner context",
        variable=adult_chat,
    ).pack(anchor="w", pady=2)
    ttk.Checkbutton(
        privacy_frame,
        text="Allow adult/private avatar presentation in private owner context",
        variable=adult_avatar,
    ).pack(anchor="w", pady=2)
    ttk.Checkbutton(
        privacy_frame,
        text="Allow adult/private content through external delivery channels",
        variable=adult_external_delivery,
    ).pack(anchor="w", pady=2)
    ttk.Label(
        privacy_frame,
        text=(
            "These are privacy/authorization boundaries, not consent. "
            "External delivery stays separate so private chat/avatar authority "
            "does not silently spill into Discord, notifications, or public UI."
        ),
        wraplength=690,
    ).pack(anchor="w", pady=(6, 0))

    grants_frame = ttk.LabelFrame(
        permissions,
        text="Standing Level-3 grants",
        padding=8,
    )
    grants_frame.pack(fill="both", expand=True)
    permission_tree = ttk.Treeview(
        grants_frame,
        columns=("capability", "scope", "expires", "state"),
        show="headings",
        height=5,
    )
    permission_tree.heading("capability", text="Capability")
    permission_tree.heading("scope", text="Scope")
    permission_tree.heading("expires", text="Expires")
    permission_tree.heading("state", text="State")
    permission_tree.column("capability", width=220, stretch=True)
    permission_tree.column("scope", width=260, stretch=True)
    permission_tree.column("expires", width=130, stretch=False)
    permission_tree.column("state", width=80, stretch=False)
    permission_tree.pack(fill="both", expand=True, pady=(0, 8))

    grant_form = ttk.Frame(grants_frame)
    grant_form.pack(fill="x")
    ttk.Label(grant_form, text="Capability").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Combobox(
        grant_form,
        textvariable=grant_capability,
        values=grantable_capabilities(),
        state="readonly",
        width=34,
    ).grid(row=1, column=0, sticky="ew", padx=(0, 6))
    ttk.Label(grant_form, text="Scope JSON").grid(
        row=0, column=1, sticky="w"
    )
    ttk.Entry(
        grant_form,
        textvariable=grant_scope,
        width=42,
    ).grid(row=1, column=1, sticky="ew", padx=(0, 6))
    ttk.Label(grant_form, text="Expiry minutes (blank = standing)").grid(
        row=0, column=2, sticky="w"
    )
    ttk.Entry(
        grant_form,
        textvariable=grant_expiry_minutes,
        width=18,
    ).grid(row=1, column=2, sticky="ew")
    grant_form.columnconfigure(1, weight=1)
    ttk.Label(
        grants_frame,
        text=(
            'Scope is an exact parameter subset. Example: '
            '{"container_id":"mealie"} or {"name":"SofiaAdaLyra"}. '
            "An empty {} scope grants that capability broadly."
        ),
        wraplength=690,
    ).pack(anchor="w", pady=(6, 6))

    def refresh_permission_grants() -> None:
        for item in permission_tree.get_children():
            permission_tree.delete(item)
        now = datetime.now(timezone.utc)
        for grant in permission_store.grants(active_only=False):
            if grant.revoked_at is not None:
                state_text = "revoked"
            elif not grant.is_active_at(now):
                state_text = "expired"
            else:
                state_text = "active"
            permission_tree.insert(
                "",
                "end",
                iid=grant.grant_id,
                values=(
                    grant.capability,
                    json.dumps(
                        grant.scope,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    (
                        "never"
                        if grant.expires_at is None
                        else grant.expires_at.astimezone(
                            timezone.utc
                        ).strftime("%Y-%m-%d %H:%M UTC")
                    ),
                    state_text,
                ),
            )

    def grant_standing_permission() -> None:
        try:
            capability = grant_capability.get().strip()
            scope = _permission_scope(grant_scope.get())
            minutes = _optional_expiry_minutes(
                grant_expiry_minutes.get()
            )
            policy = capability_permission_policy(capability)
            if not messagebox.askyesno(
                "Grant standing permission?",
                (
                    f"Grant Level {int(policy.level)} permission for:\n\n"
                    f"{capability}\n\n"
                    f"Scope: {json.dumps(scope, sort_keys=True)}\n\n"
                    "This changes Sofía's durable authority."
                ),
                parent=root,
            ):
                return
            now = datetime.now(timezone.utc)
            permission_store.grant(
                capability,
                scope=scope,
                granted_by="Sparks",
                expires_at=(
                    None
                    if minutes is None
                    else now + timedelta(minutes=minutes)
                ),
                now=now,
            )
            refresh_permission_grants()
            status.set(
                "Standing permission granted. Runtime authority reads it live."
            )
        except Exception as exc:
            messagebox.showerror(
                "Permission not granted",
                f"{type(exc).__name__}: {exc}",
                parent=root,
            )

    def revoke_standing_permission() -> None:
        selected = permission_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo(
                "Select a grant",
                "Select one standing permission to revoke.",
                parent=root,
            )
            return
        grant_id = selected[0]
        if not messagebox.askyesno(
            "Revoke standing permission?",
            "Revoke the selected durable standing permission?",
            parent=root,
        ):
            return
        try:
            permission_store.revoke(
                grant_id,
                revoked_by="Sparks",
            )
            refresh_permission_grants()
            status.set("Standing permission revoked.")
        except Exception as exc:
            messagebox.showerror(
                "Permission not revoked",
                f"{type(exc).__name__}: {exc}",
                parent=root,
            )

    grant_buttons = ttk.Frame(grants_frame)
    grant_buttons.pack(fill="x")
    ttk.Button(
        grant_buttons,
        text="Grant",
        command=grant_standing_permission,
    ).pack(side="left")
    ttk.Button(
        grant_buttons,
        text="Revoke selected",
        command=revoke_standing_permission,
    ).pack(side="left", padx=(6, 0))
    ttk.Button(
        grant_buttons,
        text="Refresh",
        command=refresh_permission_grants,
    ).pack(side="left", padx=(6, 0))
    refresh_permission_grants()

    fleet_frame = ttk.LabelFrame(
        permissions,
        text="Fleet candidates",
        padding=8,
    )
    fleet_frame.pack(fill="both", expand=True, pady=(10, 0))
    ttk.Label(
        fleet_frame,
        text=(
            "Discovery is automatic/read-only. Adding a computer to Fleet is "
            "a protected trust change and always requires your exact approval."
        ),
        wraplength=690,
    ).pack(anchor="w", pady=(0, 6))
    fleet_tree = ttk.Treeview(
        fleet_frame,
        columns=("host", "node", "endpoint", "state"),
        show="headings",
        height=4,
    )
    fleet_tree.heading("host", text="Candidate")
    fleet_tree.heading("node", text="Observed node")
    fleet_tree.heading("endpoint", text="Observed endpoint")
    fleet_tree.heading("state", text="Enrollment")
    fleet_tree.column("host", width=140, stretch=True)
    fleet_tree.column("node", width=210, stretch=True)
    fleet_tree.column("endpoint", width=190, stretch=True)
    fleet_tree.column("state", width=130, stretch=False)
    fleet_tree.pack(fill="both", expand=True, pady=(0, 6))

    def refresh_fleet_candidates() -> None:
        for item in fleet_tree.get_children():
            fleet_tree.delete(item)
        fleet_ops = OpsToolService(config.state_path)
        for host in fleet_ops.fleet():
            if host["lifecycle"] != "candidate" or host["trusted"]:
                continue
            evidence = fleet_ops.enrollment_evidence(host["host_id"])
            if evidence is None:
                continue
            node = evidence["node_id"] or "not observed"
            endpoint = (
                "not observed"
                if not evidence["endpoint_hostname"]
                else (
                    f'{evidence["endpoint_hostname"]}:'
                    f'{evidence["endpoint_port"]}'
                )
            )
            state_text = (
                "ready for approval"
                if evidence["ready"]
                else "needs verified agent"
            )
            fleet_tree.insert(
                "",
                "end",
                iid=host["host_id"],
                values=(host["host_id"], node, endpoint, state_text),
            )

    def approve_fleet_candidate() -> None:
        selected = fleet_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo(
                "Select a Fleet candidate",
                "Select one discovered candidate to approve.",
                parent=root,
            )
            return
        host_id = selected[0]
        fleet_ops = OpsToolService(config.state_path)
        evidence = fleet_ops.enrollment_evidence(host_id)
        if evidence is None or evidence["ready"] is not True:
            messagebox.showerror(
                "Candidate is not enrollment-ready",
                (
                    "This candidate needs fresh verified Fleet-agent identity, "
                    "certificate, endpoint, and capability evidence first."
                ),
                parent=root,
            )
            return
        exact = {
            "host_id": host_id,
            "node_id": evidence["node_id"],
            "public_key_sha256": evidence["public_key_sha256"],
            "endpoint_hostname": evidence["endpoint_hostname"],
            "endpoint_port": evidence["endpoint_port"],
        }
        key = exact["public_key_sha256"]
        if not messagebox.askyesno(
            "Approve Fleet enrollment?",
            (
                "Trust and add this exact computer to Sofía's Fleet?\n\n"
                f"Host: {host_id}\n"
                f"Node ID: {exact['node_id']}\n"
                f"Endpoint: {exact['endpoint_hostname']}:"
                f"{exact['endpoint_port']}\n"
                f"Certificate key: {key}\n\n"
                "This is a protected Level-4 trust change. The approval is "
                "one-time and cannot be reused for another identity."
            ),
            parent=root,
        ):
            return
        try:
            now = datetime.now(timezone.utc)
            approval = ExecutionApproval(
                approval_id=str(uuid4()),
                capability="fleet.enroll",
                request_fingerprint=execution_fingerprint(
                    "fleet.enroll",
                    exact,
                ),
                approved_by="Sparks",
                approved_at=now,
                expires_at=now + timedelta(minutes=15),
            )
            execution_approvals.record(approval)
            result = fleet_ops.enroll_candidate({
                **exact,
                "approval_id": approval.approval_id,
            })
            refresh_fleet_candidates()
            status.set(
                f"Fleet candidate {result['host_id']} enrolled with exact "
                "one-time Sparks approval."
            )
        except Exception as exc:
            messagebox.showerror(
                "Fleet enrollment failed",
                f"{type(exc).__name__}: {exc}",
                parent=root,
            )

    fleet_buttons = ttk.Frame(fleet_frame)
    fleet_buttons.pack(fill="x")
    ttk.Button(
        fleet_buttons,
        text="Approve & enroll selected",
        command=approve_fleet_candidate,
    ).pack(side="left")
    ttk.Button(
        fleet_buttons,
        text="Refresh candidates",
        command=refresh_fleet_candidates,
    ).pack(side="left", padx=(6, 0))
    refresh_fleet_candidates()

    descriptions = {
        "Sofía": (
            "Identity and personality authority are protected elsewhere. "
            "No direct mutation controls are currently required here."
        ),
        "ACT": (
            "ACT policy controls are not yet exposed as owner-editable "
            "settings. Existing authority and stop rules remain in force."
        ),
        "Avatar": (
            "Avatar and wardrobe controls will appear here when their "
            "persistent owner-setting surface is ready."
        ),
        "Memory": (
            "Memory review, promotion, import and privacy actions use the "
            "reviewed memory workflow; bulk unsafe promotion is not exposed."
        ),
        "EVOLVE": (
            "EVOLVE changes remain review-and-approval operations rather "
            "than ordinary preferences."
        ),
        "Safety & Authority": (
            "Protected grants, revocations and emergency controls are "
            "intentionally not editable as ordinary UI preferences."
        ),
        "Advanced": (
            "Advanced diagnostics remain read-only or separately approved "
            "until a bounded owner-control surface is implemented."
        ),
    }
    for section, description in descriptions.items():
        ttk.Label(
            frames[section],
            text=description,
            wraplength=720,
        ).pack(anchor="w")

    status = tk.StringVar(value="")
    bottom = ttk.Frame(root, padding=(12, 0, 12, 12))
    bottom.pack(fill="x")
    ttk.Label(bottom, textvariable=status).pack(side="left")

    def _positive(value: str, label: str) -> int:
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer") from exc
        if parsed <= 0:
            raise ValueError(f"{label} must be positive")
        return parsed

    def save() -> None:
        try:
            selected_game_mode = GameMode(game_mode.get())
            updated = DesktopControlSettings(
                close_to_tray=current.close_to_tray,
                start_with_windows=bool(start_windows.get()),
                game_mode=selected_game_mode,
                remote_chat_mode=RemoteChatMode.LOCAL,
                pinned_chat_endpoint=None,
                runtime_service_name=runtime_service.get().strip(),
                llm_service_name=llm_service.get().strip(),
            )

            discord_token_value = discord_token.get().strip()
            discord_token_after_save = (
                False
                if discord_clear_token.get()
                else secrets.exists("discord-token")
            )
            if discord_token_value:
                discord_token_after_save = True
            if discord_enabled.get() and not discord_token_after_save:
                raise ValueError(
                    "Discord is enabled but no Discord bot token is stored"
                )

            ha_token_value = ha_token.get().strip()
            ha_token_after_save = (
                False
                if ha_clear_token.get()
                else secrets.exists("home-assistant-token")
            )
            if ha_token_value:
                ha_token_after_save = True
            if ha_enabled.get() and not ha_token_after_save:
                raise ValueError(
                    "Home Assistant is enabled but no access token is stored"
                )

            selected_location_subject = LocationSubject(
                location_subject.get()
            )
            selected_nws_subject = LocationSubject(
                nws_subject.get()
            )
            parsed_latitude = _optional_float(
                location_latitude.get(),
                "Latitude",
            )
            parsed_longitude = _optional_float(
                location_longitude.get(),
                "Longitude",
            )
            if (
                nws_enabled.get()
                and selected_nws_subject is not LocationSubject.HOST
                and (
                    selected_location_subject is not selected_nws_subject
                    or parsed_latitude is None
                    or parsed_longitude is None
                )
            ):
                raise ValueError(
                    "NWS requires configured coordinates for its selected "
                    "user/site location subject"
                )

            parsed_fleet_scopes = _network_scopes(
                fleet_discovery_scopes.get()
            )
            parsed_fleet_targets = _csv_values(
                fleet_discovery_targets.get()
            )
            if (
                fleet_discovery_enabled.get()
                and not parsed_fleet_scopes
                and not parsed_fleet_targets
            ):
                raise ValueError(
                    "Enabled Fleet discovery requires at least one approved "
                    "network scope or explicit agent target"
                )

            runtime_updated = RuntimeUserSettings(
                provider_model=provider_model.get().strip(),
                provider_context_size=_positive(
                    provider_context.get(),
                    "Context size",
                ),
                provider_thinking=_thinking_setting(
                    provider_thinking.get()
                ),
                cognitive_routing_enabled=bool(
                    cognitive_routing_enabled.get()
                ),
                cognitive_primary_model=(
                    cognitive_primary_model.get().strip()
                ),
                cognitive_secondary_model=(
                    cognitive_secondary_model.get().strip()
                ),
                cognitive_primary_context_size=_positive(
                    cognitive_primary_context.get(),
                    "Primary routing context size",
                ),
                cognitive_secondary_context_size=_positive(
                    cognitive_secondary_context.get(),
                    "Secondary routing context size",
                ),
                cognitive_verify_enabled=bool(
                    cognitive_verify_enabled.get()
                ),
                cognitive_model_auto_manage=bool(
                    cognitive_model_auto_manage.get()
                ),
                cognitive_model_auto_install=bool(
                    cognitive_model_auto_install.get()
                ),
                cognitive_model_idle_unload_seconds=_positive(
                    cognitive_model_idle_unload_seconds.get(),
                    "Model idle unload seconds",
                ),
                cognitive_model_keep_alive=(
                    cognitive_model_keep_alive.get().strip()
                ),
                discord_enabled=bool(discord_enabled.get()),
                discord_owner_user_id=_optional_int(
                    discord_owner.get(),
                    "Discord owner user ID",
                ),
                discord_bot_user_id=_optional_int(
                    discord_bot.get(),
                    "Discord bot user ID",
                ),
                discord_dm_channel_id=_optional_int(
                    discord_channel.get(),
                    "Discord DM channel ID",
                ),
                home_assistant_enabled=bool(ha_enabled.get()),
                home_assistant_url=_optional_text(ha_url.get()),
                home_assistant_weather_entity=_optional_text(
                    ha_weather.get()
                ),
                home_assistant_indoor_temperature_entity=_optional_text(
                    ha_temp.get()
                ),
                home_assistant_indoor_humidity_entity=_optional_text(
                    ha_humidity.get()
                ),
                home_assistant_current_location_entity=_optional_text(
                    ha_location.get()
                ),
                home_assistant_current_location_subject=(
                    None
                    if not ha_location_subject.get().strip()
                    else LocationSubject(
                        ha_location_subject.get().strip()
                    )
                ),
                location_label=_optional_text(location_label.get()),
                location_timezone=_optional_text(
                    location_timezone.get()
                ),
                location_latitude=parsed_latitude,
                location_longitude=parsed_longitude,
                location_subject=selected_location_subject,
                nws_enabled=bool(nws_enabled.get()),
                nws_location_subject=selected_nws_subject,
                nws_station_id=_optional_text(nws_station_id.get()),
                nws_user_agent=nws_user_agent.get().strip(),
                refresh_seconds=_positive(
                    refresh_seconds.get(),
                    "Refresh seconds",
                ),
                weather_max_age_seconds=_positive(
                    weather_age.get(),
                    "Weather max age",
                ),
                indoor_max_age_seconds=_positive(
                    indoor_age.get(),
                    "Indoor max age",
                ),
                current_location_max_age_seconds=_positive(
                    current_location_age.get(),
                    "Current-location max age",
                ),
                fleet_discovery_enabled=bool(
                    fleet_discovery_enabled.get()
                ),
                fleet_discovery_interval_seconds=_positive(
                    fleet_discovery_interval.get(),
                    "Fleet discovery interval seconds",
                ),
                fleet_discovery_targets=parsed_fleet_targets,
                fleet_discovery_scopes=parsed_fleet_scopes,
                fleet_discovery_max_hosts_per_scope=_positive(
                    fleet_discovery_max_hosts.get(),
                    "Fleet discovery maximum hosts per scope",
                ),
            )

            current_private_authority = (
                permission_store.private_adult_authority()
            )
            requested_private_authority = (
                bool(private_chat.get()),
                bool(adult_chat.get()),
                bool(adult_avatar.get()),
                bool(adult_external_delivery.get()),
            )
            existing_private_authority = (
                current_private_authority.private_chat,
                current_private_authority.adult_chat,
                current_private_authority.adult_avatar,
                current_private_authority.adult_external_delivery,
            )
            private_authority_changed = (
                requested_private_authority
                != existing_private_authority
            )
            if private_authority_changed and not messagebox.askyesno(
                "Change protected private/adult authority?",
                (
                    "This changes durable Level-5 authority controlled by "
                    "Sparks. Apply the selected private/adult permissions?"
                ),
                parent=root,
            ):
                return

            if discord_clear_token.get():
                secrets.clear("discord-token")
            if discord_token_value:
                secrets.set("discord-token", discord_token_value)

            if ha_clear_token.get():
                secrets.clear("home-assistant-token")
            if ha_token_value:
                secrets.set(
                    "home-assistant-token",
                    ha_token_value,
                )

            now = datetime.now(timezone.utc)
            if private_authority_changed:
                permission_store.set_private_adult_authority(
                    private_chat=requested_private_authority[0],
                    adult_chat=requested_private_authority[1],
                    adult_avatar=requested_private_authority[2],
                    adult_external_delivery=requested_private_authority[3],
                    updated_by="Sparks",
                    now=now,
                )
            configure_windows_startup(updated.start_with_windows)
            runtime_store.save(runtime_updated, at=now)
            store.save(updated, at=now)

            activity.set_override(
                _local_host_id(),
                _activity_override(selected_game_mode),
                at=now,
            )

            discord_token.set("")
            ha_token.set("")
            discord_clear_token.set(False)
            ha_clear_token.set(False)
            discord_token_status.set(
                "Token stored securely"
                if secrets.exists("discord-token")
                else "No stored token"
            )
            ha_token_status.set(
                "Token stored securely"
                if secrets.exists("home-assistant-token")
                else "No stored token"
            )
            status.set(
                "Saved. Permission and private/adult authority changes are durable; environment changes apply on the next turn and some integration changes may require a restart."
            )
        except Exception as exc:
            messagebox.showerror(
                "Settings not saved",
                f"{type(exc).__name__}: {exc}",
                parent=root,
            )

    ttk.Button(
        bottom,
        text="Save",
        command=save,
    ).pack(side="right")
    ttk.Button(
        bottom,
        text="Close",
        command=root.destroy,
    ).pack(side="right", padx=(0, 8))

    root.mainloop()
    return 0


def main() -> int:
    return run_settings_window()


if __name__ == "__main__":
    raise SystemExit(main())
