from __future__ import annotations

from dataclasses import replace
import json

from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.environment.model import LocationSubject
from sofia.state.model import StateKey
from sofia.state.plane import StatePlane


_ALLOWED_KEYS = frozenset(
    {
        "provider.model",
        "provider.temperature",
        "provider.seed",
        "provider.context_size",
        "provider.thinking",
        "environment.refresh_seconds",
        "environment.weather_max_age_seconds",
        "environment.indoor_max_age_seconds",
        "environment.current_location_max_age_seconds",
        "environment.home_assistant_weather_entity",
        "environment.home_assistant_indoor_temperature_entity",
        "environment.home_assistant_indoor_humidity_entity",
        "environment.home_assistant_current_location_entity",
        "environment.home_assistant_current_location_subject",
        "environment.nws_enabled",
        "environment.nws_location_subject",
        "environment.nws_user_agent",
    }
)


def validate_reviewed_configuration_content(
    key: str,
    content: str,
) -> object:
    if key not in _ALLOWED_KEYS:
        raise PermissionError(
            f"reviewed runtime configuration does not permit key {key!r}"
        )
    if not isinstance(content, str):
        raise TypeError("reviewed configuration content must be text")
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "reviewed configuration must be JSON"
        ) from exc
    if not isinstance(document, dict) or set(document) != {"value"}:
        raise ValueError(
            'reviewed configuration must be exactly {"value": ...}'
        )
    return document["value"]


def _positive_int(value: object, key: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{key} requires a positive integer")
    return value


def _optional_string(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} requires null or nonempty text")
    return value.strip()


def _apply_provider(
    provider: ProviderConfiguration,
    key: str,
    value: object,
) -> ProviderConfiguration:
    field = key.split(".", 1)[1]
    if field == "model":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("provider.model requires nonempty text")
        return replace(provider, model=value.strip())
    if field == "temperature":
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
        ):
            raise ValueError(
                "provider.temperature requires null or a nonnegative number"
            )
        return replace(provider, temperature=value)
    if field == "seed":
        if value is not None and type(value) is not int:
            raise ValueError("provider.seed requires null or an integer")
        return replace(provider, seed=value)
    if field == "context_size":
        if value is not None:
            value = _positive_int(value, key)
        return replace(provider, context_size=value)
    if field == "thinking":
        if value is not None and not isinstance(value, (bool, str)):
            raise ValueError(
                "provider.thinking requires null, boolean, or text"
            )
        if isinstance(value, str) and not value.strip():
            raise ValueError(
                "provider.thinking text cannot be blank"
            )
        return replace(provider, thinking=value)
    raise PermissionError(f"unsupported provider key {key!r}")


def _apply_environment(configuration, key: str, value: object):
    field = key.split(".", 1)[1]
    if field in {
        "refresh_seconds",
        "weather_max_age_seconds",
        "indoor_max_age_seconds",
        "current_location_max_age_seconds",
    }:
        return replace(
            configuration,
            **{field: _positive_int(value, key)},
        )
    if field in {
        "home_assistant_weather_entity",
        "home_assistant_indoor_temperature_entity",
        "home_assistant_indoor_humidity_entity",
        "home_assistant_current_location_entity",
        "nws_user_agent",
    }:
        if field == "nws_user_agent":
            parsed = _optional_string(value, key)
            if parsed is None:
                raise ValueError("nws_user_agent cannot be null")
        else:
            parsed = _optional_string(value, key)
        return replace(configuration, **{field: parsed})
    if field == "home_assistant_current_location_subject":
        parsed = None if value is None else LocationSubject(str(value))
        return replace(
            configuration,
            home_assistant_current_location_subject=parsed,
        )
    if field == "nws_enabled":
        if type(value) is not bool:
            raise ValueError("environment.nws_enabled requires a boolean")
        return replace(configuration, nws_enabled=value)
    if field == "nws_location_subject":
        return replace(
            configuration,
            nws_location_subject=LocationSubject(str(value)),
        )
    raise PermissionError(f"unsupported environment key {key!r}")


def apply_reviewed_configuration(
    configuration: SofiaConfiguration,
    state_plane: StatePlane,
) -> SofiaConfiguration:
    """Apply only explicitly reviewed, bounded State Plane configuration."""
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be a SofiaConfiguration")
    if not isinstance(state_plane, StatePlane):
        raise TypeError("state_plane must be a StatePlane")

    result = configuration
    for key in sorted(_ALLOWED_KEYS):
        record = state_plane.read(
            StateKey(namespace="evolve-config", key=key)
        )
        if record is None:
            continue
        value = validate_reviewed_configuration_content(
            key,
            record.value.decode("utf-8"),
        )
        if key.startswith("provider."):
            result = replace(
                result,
                provider=_apply_provider(result.provider, key, value),
            )
        elif key.startswith("environment."):
            result = replace(
                result,
                environment=_apply_environment(
                    result.environment,
                    key,
                    value,
                ),
            )
    return result
