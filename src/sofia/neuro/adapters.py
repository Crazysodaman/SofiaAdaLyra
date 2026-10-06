"""Pure adapters from authoritative subsystem state to attention-only signals."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import math
import re

from sofia.emotion.model import CurrentEmotionalState
from sofia.environment.model import EnvironmentFreshness, EnvironmentSnapshot
from sofia.ops.model import HostTelemetry
from sofia.voice import TTSStatus

from .model import NeuralSignal


def _slug(value: object, *, fallback: str = "unknown") -> str:
    raw = str(getattr(value, "value", value)).strip().casefold()
    safe = re.sub(r"[^a-z0-9_.:/-]+", "-", raw).strip("-")
    if not safe:
        return fallback
    if len(safe) <= 72:
        return safe
    digest = sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{safe[:59]}-{digest}"


def _signal(
    *,
    kind: str,
    source: str,
    value: float,
    confidence: float,
    novelty: float,
    urgency: float,
    observed_at: datetime,
    ttl_seconds: float,
) -> NeuralSignal:
    return NeuralSignal(
        source=_slug(source),
        kind=kind,
        value=max(0.0, min(1.0, value)),
        confidence=max(0.0, min(1.0, confidence)),
        novelty=max(0.0, min(1.0, novelty)),
        urgency=max(0.0, min(1.0, urgency)),
        observed_at=observed_at.astimezone(timezone.utc),
        ttl_seconds=ttl_seconds,
    )


def environment_signals(snapshot: EnvironmentSnapshot) -> tuple[NeuralSignal, ...]:
    if not isinstance(snapshot, EnvironmentSnapshot):
        raise TypeError("snapshot must be EnvironmentSnapshot")
    at = snapshot.observed_at
    local = snapshot.user_local_time or snapshot.host_local_time
    hour = local.hour
    daypart = (
        "night" if hour < 6 else
        "morning" if hour < 12 else
        "afternoon" if hour < 18 else
        "evening" if hour < 22 else
        "night"
    )
    result = [
        _signal(
            kind="environment", source=f"daypart:{daypart}", value=0.45,
            confidence=1.0, novelty=0.2, urgency=0.2, observed_at=at,
            ttl_seconds=3600.0,
        )
    ]
    if snapshot.season is not None:
        result.append(_signal(
            kind="environment", source=f"season:{_slug(snapshot.season)}",
            value=0.3, confidence=0.9, novelty=0.15, urgency=0.1,
            observed_at=at, ttl_seconds=21600.0,
        ))
    location = snapshot.effective_location
    if location is not None:
        result.append(_signal(
            kind="environment",
            source=(
                f"location:{_slug(location.subject)}:{_slug(location.kind)}"
            ),
            value=0.35,
            confidence=(
                0.9
                if snapshot.current_location_freshness
                is EnvironmentFreshness.CURRENT
                else 0.7
            ),
            novelty=0.25, urgency=0.15, observed_at=at,
            ttl_seconds=1800.0,
        ))
    if snapshot.daylight is not None:
        result.append(_signal(
            kind="environment",
            source=f"daylight:{_slug(snapshot.daylight.state)}",
            value=0.4, confidence=0.95, novelty=0.2, urgency=0.15,
            observed_at=at, ttl_seconds=1800.0,
        ))
    if (
        snapshot.weather is not None
        and snapshot.weather_freshness is EnvironmentFreshness.CURRENT
    ):
        weather = snapshot.weather
        result.append(_signal(
            kind="environment", source=f"weather:{_slug(weather.condition)}",
            value=0.55, confidence=0.9, novelty=0.45, urgency=0.3,
            observed_at=weather.observed_at, ttl_seconds=max(
                1.0, min(86400.0, (weather.expires_at - weather.observed_at).total_seconds())
            ),
        ))
    if snapshot.provider_errors:
        result.append(_signal(
            kind="environment", source="provider:error", value=0.65,
            confidence=1.0, novelty=0.7, urgency=0.65, observed_at=at,
            ttl_seconds=900.0,
        ))
    if (
        snapshot.indoor is not None
        and snapshot.indoor_freshness is EnvironmentFreshness.CURRENT
    ):
        indoor = snapshot.indoor
        if indoor.temperature_c is not None and (
            indoor.temperature_c <= 12.0 or indoor.temperature_c >= 30.0
        ):
            result.append(_signal(
                kind="environment", source="indoor:temperature-extreme",
                value=0.7, confidence=0.9, novelty=0.55, urgency=0.6,
                observed_at=indoor.observed_at,
                ttl_seconds=max(1.0, min(
                    86400.0,
                    (indoor.expires_at - indoor.observed_at).total_seconds(),
                )),
            ))
        if indoor.humidity_percent is not None and (
            indoor.humidity_percent <= 20.0 or indoor.humidity_percent >= 75.0
        ):
            result.append(_signal(
                kind="environment", source="indoor:humidity-extreme",
                value=0.65, confidence=0.9, novelty=0.5, urgency=0.5,
                observed_at=indoor.observed_at,
                ttl_seconds=max(1.0, min(
                    86400.0,
                    (indoor.expires_at - indoor.observed_at).total_seconds(),
                )),
            ))
    return tuple(result)


def body_signals(snapshot: EnvironmentSnapshot) -> tuple[NeuralSignal, ...]:
    """Map authenticated phone/BODY observations without inferring intent."""
    if not isinstance(snapshot, EnvironmentSnapshot):
        raise TypeError("snapshot must be EnvironmentSnapshot")
    mobile = snapshot.mobile
    if mobile is None or snapshot.mobile_freshness is not EnvironmentFreshness.CURRENT:
        return ()
    at = mobile.observed_at
    result = [_signal(
        kind="body", source=f"activity:{_slug(mobile.activity)}", value=0.5,
        confidence=0.8, novelty=0.35, urgency=0.25, observed_at=at,
        ttl_seconds=max(1.0, min(86400.0, (mobile.expires_at - at).total_seconds())),
    )]
    if mobile.battery_percent is not None and mobile.battery_percent <= 25:
        severity = (25.0 - mobile.battery_percent) / 25.0
        result.append(_signal(
            kind="body", source="phone:battery-low",
            value=0.55 + 0.4 * severity, confidence=0.95,
            novelty=0.5, urgency=0.5 + 0.45 * severity,
            observed_at=at, ttl_seconds=600.0,
        ))
    if str(getattr(mobile.network, "value", mobile.network)) == "offline":
        result.append(_signal(
            kind="body", source="phone:offline", value=0.8,
            confidence=0.95, novelty=0.7, urgency=0.7,
            observed_at=at, ttl_seconds=300.0,
        ))
    if mobile.proximity_near is not None:
        result.append(_signal(
            kind="body",
            source=("phone:proximity-near" if mobile.proximity_near
                    else "phone:proximity-clear"),
            value=0.35, confidence=0.9, novelty=0.3, urgency=0.2,
            observed_at=at, ttl_seconds=120.0,
        ))
    if mobile.charging:
        result.append(_signal(
            kind="body", source="phone:charging", value=0.25,
            confidence=0.95, novelty=0.15, urgency=0.1,
            observed_at=at, ttl_seconds=300.0,
        ))
    return tuple(result)


def emotion_signals(state: CurrentEmotionalState) -> tuple[NeuralSignal, ...]:
    if not isinstance(state, CurrentEmotionalState):
        raise TypeError("state must be CurrentEmotionalState")
    return tuple(
        _signal(
            kind="emotion", source=f"state:{_slug(item.name)}",
            value=item.intensity, confidence=0.95,
            novelty=min(0.9, 0.25 + item.intensity * 0.5),
            urgency=min(0.9, 0.2 + item.intensity * 0.65),
            observed_at=state.as_of, ttl_seconds=1800.0,
        )
        for item in state.active
    )


def telemetry_signals(telemetry: HostTelemetry) -> tuple[NeuralSignal, ...]:
    if not isinstance(telemetry, HostTelemetry):
        raise TypeError("telemetry must be HostTelemetry")
    at = telemetry.observed_at
    result: list[NeuralSignal] = []
    for name, percent in (("cpu", telemetry.cpu_percent), ("gpu", telemetry.gpu_percent)):
        if percent is not None and percent >= 70.0:
            level = percent / 100.0
            result.append(_signal(
                kind="ops", source=f"host:{name}-load", value=level,
                confidence=0.95, novelty=0.5, urgency=max(0.45, level),
                observed_at=at, ttl_seconds=180.0,
            ))
    if telemetry.ram_used_bytes is not None and telemetry.ram_total_bytes:
        ratio = telemetry.ram_used_bytes / telemetry.ram_total_bytes
        if ratio >= 0.75:
            result.append(_signal(
                kind="ops", source="host:ram-pressure", value=ratio,
                confidence=0.98, novelty=0.5, urgency=max(0.5, ratio),
                observed_at=at, ttl_seconds=180.0,
            ))
    if telemetry.storage_free_bytes is not None and telemetry.storage_free_bytes < 10 * 1024**3:
        severity = 1.0 - telemetry.storage_free_bytes / (10 * 1024**3)
        result.append(_signal(
            kind="ops", source="host:storage-low", value=0.6 + severity * 0.4,
            confidence=0.98, novelty=0.65, urgency=0.65 + severity * 0.35,
            observed_at=at, ttl_seconds=600.0,
        ))
    if telemetry.temperature_c is not None and telemetry.temperature_c >= 75.0:
        severity = min(1.0, (telemetry.temperature_c - 60.0) / 40.0)
        result.append(_signal(
            kind="ops", source="host:temperature-high", value=severity,
            confidence=0.9, novelty=0.65, urgency=max(0.6, severity),
            observed_at=at, ttl_seconds=180.0,
        ))
    if telemetry.throttled:
        result.append(_signal(
            kind="ops", source="host:throttled", value=1.0,
            confidence=1.0, novelty=0.8, urgency=0.9,
            observed_at=at, ttl_seconds=300.0,
        ))
    return tuple(result)


def voice_signals(status: TTSStatus, *, observed_at: datetime) -> tuple[NeuralSignal, ...]:
    if not isinstance(status, TTSStatus):
        raise TypeError("status must be TTSStatus")
    if not status.enabled:
        return ()
    if status.healthy is False or status.available is False:
        return (_signal(
            kind="voice", source="tts:degraded", value=0.75,
            confidence=1.0, novelty=0.65, urgency=0.65,
            observed_at=observed_at, ttl_seconds=300.0,
        ),)
    if status.started:
        return (_signal(
            kind="voice", source="tts:ready", value=0.3,
            confidence=0.95, novelty=0.15, urgency=0.1,
            observed_at=observed_at, ttl_seconds=300.0,
        ),)
    return ()


def avatar_signals(snapshot: dict, *, observed_at: datetime) -> tuple[NeuralSignal, ...]:
    if not isinstance(snapshot, dict):
        raise TypeError("avatar snapshot must be a dict")
    current = snapshot.get("current")
    if not isinstance(current, dict):
        return ()
    result = [_signal(
        kind="avatar", source=f"outfit:{_slug(current.get('outfit_id'))}",
        value=0.35, confidence=1.0, novelty=0.25, urgency=0.1,
        observed_at=observed_at, ttl_seconds=1800.0,
    )]
    appearance = current.get("appearance")
    if isinstance(appearance, dict):
        for field in ("posture", "expression", "activity"):
            value = appearance.get(field)
            if value:
                result.append(_signal(
                    kind="avatar", source=f"{field}:{_slug(value)}",
                    value=0.4, confidence=1.0, novelty=0.3, urgency=0.15,
                    observed_at=observed_at, ttl_seconds=900.0,
                ))
    return tuple(result)


def recency_value(*, occurred_at: datetime, now: datetime, half_life_hours: float) -> float:
    age = max(0.0, (now - occurred_at).total_seconds())
    return math.pow(0.5, age / (half_life_hours * 3600.0))
