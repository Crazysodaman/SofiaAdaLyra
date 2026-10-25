"""MOD-SENSORS: strictly bounded interpretation of pre-authorized sensor samples.

Device authentication, calibration trust, authorization and retention belong to
Platform. This module performs no IO and cannot discover a device.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping
import re

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-SENSORS"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "sensors.interpret_readings.v1"
PROFILE = "OBSERVE"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_KINDS = {"temperature_c": (-100.0, 100.0), "humidity_percent": (0.0, 100.0), "illuminance_lux": (0.0, 200000.0), "pressure_hpa": (300.0, 1200.0), "battery_percent": (0.0, 100.0)}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "sensor_ref", "observed_at", "kind", "value", "quality"})


def evaluate_readings(readings: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must have timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid max_age_seconds")
    if type(readings) is not list or not 1 <= len(readings) <= 64:
        raise ValueError("readings must contain 1..64 entries")
    rows = []
    seen = set()
    for reading in readings:
        if not isinstance(reading, Mapping) or set(reading) != _FIELDS:
            raise ValueError("sensor reading fields mismatch")
        source, sensor, kind = (reading[key] for key in ("source_ref", "sensor_ref", "kind"))
        if any(not isinstance(x, str) or not _REF.fullmatch(x) for x in (source, sensor)):
            raise ValueError("invalid sensor identity")
        if kind not in _KINDS:
            raise ValueError("unsupported sensor kind")
        if (source, sensor, kind) in seen:
            raise ValueError("duplicate reading identity")
        seen.add((source, sensor, kind))
        val = reading["value"]
        if val is not None and (type(val) not in (int, float) or not isfinite(val)):
            raise ValueError("non-finite or non-numeric reading")
        if reading["quality"] not in ("unverified", "calibrated", "unknown"):
            raise ValueError("unsupported quality flag")
        try:
            when = datetime.fromisoformat(reading["observed_at"])
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("timestamp without timezone")
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid sensor timestamp") from exc
        seconds = (now.astimezone(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()
        freshness = "future" if seconds < -5 else "stale" if seconds > max_age_seconds else "fresh"
        low, high = _KINDS[kind]
        status = "unknown"
        if freshness == "fresh" and val is not None:
            status = "out_of_range" if not low <= val <= high else "observed"
        rows.append({"source_ref": source, "sensor_ref": sensor, "kind": kind, "observed_at": when.astimezone(timezone.utc).isoformat(), "freshness": freshness, "status": status, "value": val if freshness == "fresh" and status == "observed" else None, "quality_claim": reading["quality"]})
    return {"schema": "sofia.sensors.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION), "observations": rows, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Summarize approved environmental samples, without hardware access.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"readings"}:
            raise ValueError("invalid capability request")
        return evaluate_readings(request.parameters["readings"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
