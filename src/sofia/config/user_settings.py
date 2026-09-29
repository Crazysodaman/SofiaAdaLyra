from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from sofia.environment.model import LocationSubject


@dataclass(frozen=True, slots=True)
class RuntimeUserSettings:
    provider_model: str = "qwen3:14b"
    provider_context_size: int = 20000
    provider_thinking: bool | str = False

    cognitive_routing_enabled: bool = False
    cognitive_primary_model: str = "qwen3.5:9b"
    cognitive_secondary_model: str = "huihui_ai/qwen3.5-abliterated:4b"
    cognitive_primary_context_size: int = 16000
    cognitive_secondary_context_size: int = 8192
    cognitive_verify_enabled: bool = True

    discord_enabled: bool = False
    discord_owner_user_id: int | None = None
    discord_bot_user_id: int | None = None
    discord_dm_channel_id: int | None = None

    home_assistant_enabled: bool = False
    home_assistant_url: str | None = None
    home_assistant_weather_entity: str | None = None
    home_assistant_indoor_temperature_entity: str | None = None
    home_assistant_indoor_humidity_entity: str | None = None
    home_assistant_current_location_entity: str | None = None
    home_assistant_current_location_subject: LocationSubject | None = None

    location_label: str | None = None
    location_timezone: str | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_subject: LocationSubject = LocationSubject.USER

    nws_enabled: bool = False
    nws_location_subject: LocationSubject = LocationSubject.USER
    nws_user_agent: str = "SofiaAdaLyra/1.0"

    refresh_seconds: int = 300
    weather_max_age_seconds: int = 1800
    indoor_max_age_seconds: int = 900
    current_location_max_age_seconds: int = 900

    def __post_init__(self) -> None:
        if not isinstance(self.provider_model, str) or not self.provider_model.strip():
            raise ValueError("provider_model is required")
        if type(self.provider_context_size) is not int or self.provider_context_size <= 0:
            raise ValueError("provider_context_size must be positive")
        if type(self.provider_thinking) is not bool:
            if not isinstance(self.provider_thinking, str):
                raise TypeError(
                    "provider_thinking must be boolean or a reasoning level"
                )
            normalized_thinking = self.provider_thinking.strip().casefold()
            if normalized_thinking not in {
                "low",
                "medium",
                "high",
                "xhigh",
            }:
                raise ValueError(
                    "provider_thinking reasoning level must be "
                    "low, medium, high, or xhigh"
                )
            object.__setattr__(
                self,
                "provider_thinking",
                normalized_thinking,
            )

        for name in (
            "cognitive_routing_enabled",
            "cognitive_verify_enabled",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        for name in (
            "cognitive_primary_model",
            "cognitive_secondary_model",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        for name in (
            "cognitive_primary_context_size",
            "cognitive_secondary_context_size",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive")

        for name in ("discord_enabled", "home_assistant_enabled", "nws_enabled"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        for name in (
            "discord_owner_user_id",
            "discord_bot_user_id",
            "discord_dm_channel_id",
        ):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not int or value <= 0 or value >= (1 << 64)
            ):
                raise ValueError(f"{name} must be a positive Discord snowflake")
        if (
            self.discord_owner_user_id is not None
            and self.discord_owner_user_id == self.discord_bot_user_id
        ):
            raise ValueError("Discord owner and bot IDs must differ")
        if self.discord_enabled and any(
            value is None
            for value in (
                self.discord_owner_user_id,
                self.discord_bot_user_id,
            )
        ):
            raise ValueError("enabled Discord requires owner and bot IDs")

        for name in (
            "home_assistant_url",
            "home_assistant_weather_entity",
            "home_assistant_indoor_temperature_entity",
            "home_assistant_indoor_humidity_entity",
            "home_assistant_current_location_entity",
            "location_label",
            "location_timezone",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{name} must be nonempty or None")

        if self.home_assistant_enabled and not self.home_assistant_url:
            raise ValueError("enabled Home Assistant requires a base URL")
        if self.home_assistant_enabled and not any(
            (
                self.home_assistant_weather_entity,
                self.home_assistant_indoor_temperature_entity,
                self.home_assistant_indoor_humidity_entity,
                self.home_assistant_current_location_entity,
            )
        ):
            raise ValueError(
                "enabled Home Assistant requires at least one entity"
            )

        if not isinstance(self.location_subject, LocationSubject):
            raise TypeError("location_subject must be a LocationSubject")
        if not isinstance(self.nws_location_subject, LocationSubject):
            raise TypeError("nws_location_subject must be a LocationSubject")
        if (
            self.home_assistant_current_location_subject is not None
            and not isinstance(
                self.home_assistant_current_location_subject,
                LocationSubject,
            )
        ):
            raise TypeError(
                "home_assistant_current_location_subject must be "
                "LocationSubject or None"
            )

        if bool(self.location_label) != bool(self.location_timezone):
            raise ValueError(
                "location label and timezone must be supplied together"
            )
        if (self.location_latitude is None) != (
            self.location_longitude is None
        ):
            raise ValueError(
                "location latitude and longitude must be supplied together"
            )
        if self.location_latitude is not None:
            lat = float(self.location_latitude)
            lon = float(self.location_longitude)
            if not -90.0 <= lat <= 90.0:
                raise ValueError("location latitude must be between -90 and 90")
            if not -180.0 <= lon <= 180.0:
                raise ValueError("location longitude must be between -180 and 180")
            object.__setattr__(self, "location_latitude", lat)
            object.__setattr__(self, "location_longitude", lon)

        if (
            not isinstance(self.nws_user_agent, str)
            or not self.nws_user_agent.strip()
        ):
            raise ValueError("nws_user_agent is required")

        for name in (
            "refresh_seconds",
            "weather_max_age_seconds",
            "indoor_max_age_seconds",
            "current_location_max_age_seconds",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive")

    def environment_mapping(self) -> dict[str, str]:
        result = {
            "SOFIA_ENVIRONMENT_REFRESH_SECONDS": str(self.refresh_seconds),
            "SOFIA_ENVIRONMENT_WEATHER_MAX_AGE_SECONDS": str(
                self.weather_max_age_seconds
            ),
            "SOFIA_ENVIRONMENT_INDOOR_MAX_AGE_SECONDS": str(
                self.indoor_max_age_seconds
            ),
            "SOFIA_ENVIRONMENT_CURRENT_LOCATION_MAX_AGE_SECONDS": str(
                self.current_location_max_age_seconds
            ),
            "SOFIA_ENVIRONMENT_NWS_ENABLED": "1" if self.nws_enabled else "0",
            "SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT": (
                self.nws_location_subject.value
            ),
            "SOFIA_ENVIRONMENT_NWS_USER_AGENT": self.nws_user_agent,
        }
        if self.location_label and self.location_timezone:
            result.update(
                {
                    "SOFIA_ENVIRONMENT_LOCATION_LABEL": self.location_label,
                    "SOFIA_ENVIRONMENT_TIMEZONE": self.location_timezone,
                    "SOFIA_ENVIRONMENT_LOCATION_SUBJECT": (
                        self.location_subject.value
                    ),
                }
            )
            if self.location_latitude is not None:
                result["SOFIA_ENVIRONMENT_LATITUDE"] = str(
                    self.location_latitude
                )
                result["SOFIA_ENVIRONMENT_LONGITUDE"] = str(
                    self.location_longitude
                )

        if self.home_assistant_enabled:
            entity_values = (
                (
                    "SOFIA_ENVIRONMENT_HA_WEATHER_ENTITY",
                    self.home_assistant_weather_entity,
                ),
                (
                    "SOFIA_ENVIRONMENT_HA_INDOOR_TEMPERATURE_ENTITY",
                    self.home_assistant_indoor_temperature_entity,
                ),
                (
                    "SOFIA_ENVIRONMENT_HA_INDOOR_HUMIDITY_ENTITY",
                    self.home_assistant_indoor_humidity_entity,
                ),
                (
                    "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY",
                    self.home_assistant_current_location_entity,
                ),
            )
            for key, value in entity_values:
                if value:
                    result[key] = value
            if self.home_assistant_current_location_subject is not None:
                result[
                    "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_SUBJECT"
                ] = self.home_assistant_current_location_subject.value
        return result


class RuntimeUserSettingsStore:
    _KEY = "runtime-user-settings"

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ui_runtime_settings (
                    settings_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(settings: RuntimeUserSettings) -> str:
        raw = asdict(settings)
        for key in (
            "location_subject",
            "nws_location_subject",
            "home_assistant_current_location_subject",
        ):
            value = raw[key]
            raw[key] = None if value is None else value.value
        return json.dumps(raw, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _decode(raw: str) -> RuntimeUserSettings:
        data = json.loads(raw)
        data["location_subject"] = LocationSubject(
            data.get("location_subject", "user")
        )
        data["nws_location_subject"] = LocationSubject(
            data.get("nws_location_subject", "user")
        )
        ha_subject = data.get("home_assistant_current_location_subject")
        data["home_assistant_current_location_subject"] = (
            None if ha_subject is None else LocationSubject(ha_subject)
        )
        return RuntimeUserSettings(**data)

    def load(self) -> RuntimeUserSettings:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT value_json FROM ui_runtime_settings "
                "WHERE settings_key=?",
                (self._KEY,),
            ).fetchone()
        if row is None:
            return RuntimeUserSettings()
        return self._decode(str(row[0]))

    def save(
        self,
        settings: RuntimeUserSettings,
        *,
        at: datetime | None = None,
    ) -> None:
        if not isinstance(settings, RuntimeUserSettings):
            raise TypeError("settings must be RuntimeUserSettings")
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("settings timestamp must be timezone-aware")
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO ui_runtime_settings
                    (settings_key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(settings_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (
                    self._KEY,
                    self._encode(settings),
                    moment.astimezone(timezone.utc).isoformat(),
                ),
            )
