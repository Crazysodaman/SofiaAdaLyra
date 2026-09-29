"""Tkinter master settings window for the Sofía desktop/tray client."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

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
from sofia.safe.secret_store import ProtectedSecretStore
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


def run_settings_window() -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    config = create_production_configuration()
    _ensure_state_database(config.state_path)
    store = DesktopControlSettingsStore(config.state_path)
    runtime_store = RuntimeUserSettingsStore(config.state_path)
    secrets = ProtectedSecretStore.for_state_path(config.state_path)
    activity = HostActivityStore(config.state_path)
    current = store.load()
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
    remote_mode = tk.StringVar(value=current.remote_chat_mode.value)
    pinned_endpoint = tk.StringVar(value=current.pinned_chat_endpoint or "")
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
    nws_user_agent = tk.StringVar(value=runtime.nws_user_agent)
    refresh_seconds = tk.StringVar(value=str(runtime.refresh_seconds))
    weather_age = tk.StringVar(value=str(runtime.weather_max_age_seconds))
    indoor_age = tk.StringVar(value=str(runtime.indoor_max_age_seconds))
    current_location_age = tk.StringVar(
        value=str(runtime.current_location_max_age_seconds)
    )

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
    ttk.Label(chat, text="Desktop chat routing").pack(anchor="w")
    ttk.Combobox(
        chat,
        textvariable=remote_mode,
        values=tuple(value.value for value in RemoteChatMode),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(chat, text="Pinned runtime endpoint").pack(anchor="w")
    ttk.Entry(
        chat,
        textvariable=pinned_endpoint,
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(
        chat,
        text=(
            "Fleet-auto follows the authoritative ready Sofía runtime. "
            "Pinned mode uses the configured mTLS endpoint. Local keeps "
            "the desktop on this machine."
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

    descriptions = {
        "Sofía": (
            "Identity and personality authority are protected elsewhere. "
            "No direct mutation controls are currently required here."
        ),
        "ACT": (
            "ACT policy controls are not yet exposed as owner-editable "
            "settings. Existing authority and stop rules remain in force."
        ),
        "Fleet": (
            "Fleet enrollment and maintenance controls remain governed by "
            "OPS/RUN workflows rather than free-form settings."
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
                remote_chat_mode=RemoteChatMode(remote_mode.get()),
                pinned_chat_endpoint=(
                    pinned_endpoint.get().strip() or None
                ),
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
            )

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
                "Saved. Restart Sofía to apply runtime/integration changes."
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
