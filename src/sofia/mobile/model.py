"""Strict wire model for read-only Android sensor reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any

from sofia.environment.model import MobileActivityState, MobileNetworkTransport


_DEVICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


def _optional_number(
    payload: dict[str, Any], name: str, minimum: float, maximum: float
) -> float | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or null")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{name} outside supported bounds")
    return number


@dataclass(frozen=True, slots=True)
class MobileSensorReport:
    device_id: str
    observed_at: datetime
    timezone_name: str
    latitude: float | None
    longitude: float | None
    accuracy_meters: float | None
    battery_percent: float | None
    charging: bool | None
    network: MobileNetworkTransport
    activity: MobileActivityState
    ambient_light_lux: float | None
    pressure_hpa: float | None
    proximity_near: bool | None
    step_counter: float | None

    @classmethod
    def from_payload(cls, payload: Any) -> "MobileSensorReport":
        if not isinstance(payload, dict):
            raise TypeError("mobile sensor report must be an object")
        allowed = {
            "device_id", "observed_at", "timezone", "latitude", "longitude",
            "accuracy_meters", "battery_percent", "charging", "network",
            "activity", "ambient_light_lux", "pressure_hpa",
            "proximity_near", "step_counter",
        }
        if set(payload) - allowed:
            raise ValueError("mobile sensor report contains unknown fields")
        device_id = payload.get("device_id")
        if not isinstance(device_id, str) or _DEVICE.fullmatch(device_id) is None:
            raise ValueError("invalid mobile device_id")
        raw_time = payload.get("observed_at")
        if not isinstance(raw_time, str):
            raise TypeError("observed_at must be an ISO timestamp")
        try:
            observed_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO timestamp") from exc
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        observed_at = observed_at.astimezone(timezone.utc)
        timezone_name = payload.get("timezone")
        if (
            not isinstance(timezone_name, str)
            or not timezone_name.strip()
            or len(timezone_name) > 80
            or any(ord(character) < 32 for character in timezone_name)
        ):
            raise ValueError("invalid mobile timezone")
        latitude = _optional_number(payload, "latitude", -90.0, 90.0)
        longitude = _optional_number(payload, "longitude", -180.0, 180.0)
        accuracy = _optional_number(
            payload, "accuracy_meters", 0.0, 40_100_000.0
        )
        if (latitude is None) != (longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if accuracy is not None and latitude is None:
            raise ValueError("accuracy requires coordinates")
        charging = payload.get("charging")
        proximity = payload.get("proximity_near")
        for name, value in (("charging", charging), ("proximity_near", proximity)):
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or null")
        try:
            network = MobileNetworkTransport(payload.get("network", "other"))
            activity = MobileActivityState(payload.get("activity", "unknown"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid mobile network or activity state") from exc
        return cls(
            device_id=device_id,
            observed_at=observed_at,
            timezone_name=timezone_name.strip(),
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy,
            battery_percent=_optional_number(
                payload, "battery_percent", 0.0, 100.0
            ),
            charging=charging,
            network=network,
            activity=activity,
            ambient_light_lux=_optional_number(
                payload, "ambient_light_lux", 0.0, 250_000.0
            ),
            pressure_hpa=_optional_number(payload, "pressure_hpa", 300.0, 1_200.0),
            proximity_near=proximity,
            step_counter=_optional_number(
                payload, "step_counter", 0.0, 1_000_000_000.0
            ),
        )
