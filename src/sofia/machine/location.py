"""Durable operator-configured locations for known machines.

Machine discovery observes identity/hardware. This registry stores stable
operator configuration keyed by that identity. A configured location is not
proof that the machine is physically present there right now.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCHEMA_VERSION = 1


def _text(value: str, label: str, *, limit: int = 160) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    result = value.strip()
    if len(result) > limit:
        raise ValueError(f"{label} is too long")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in result):
        raise ValueError(f"{label} contains control characters")
    return result


def _coordinate(
    value: float | int,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    if not minimum <= result <= maximum:
        raise ValueError(
            f"{label} must be between {minimum:g} and {maximum:g}"
        )
    return result


@dataclass(frozen=True, slots=True)
class MachineLocationRecord:
    machine_id: str
    hostname: str
    label: str
    timezone: str
    latitude: float
    longitude: float
    updated_at: datetime
    source: str = "operator"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "machine_id",
            _text(self.machine_id, "machine_id", limit=256),
        )
        object.__setattr__(
            self,
            "hostname",
            _text(self.hostname, "hostname", limit=256),
        )
        object.__setattr__(
            self,
            "label",
            _text(self.label, "location label"),
        )
        timezone_name = _text(
            self.timezone,
            "timezone",
            limit=80,
        )
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"unknown machine location timezone: {timezone_name}"
            ) from exc
        object.__setattr__(self, "timezone", timezone_name)
        object.__setattr__(
            self,
            "latitude",
            _coordinate(
                self.latitude,
                "latitude",
                minimum=-90.0,
                maximum=90.0,
            ),
        )
        object.__setattr__(
            self,
            "longitude",
            _coordinate(
                self.longitude,
                "longitude",
                minimum=-180.0,
                maximum=180.0,
            ),
        )
        if (
            not isinstance(self.updated_at, datetime)
            or self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError(
                "machine location updated_at must be timezone-aware"
            )
        object.__setattr__(
            self,
            "source",
            _text(self.source, "location source", limit=128),
        )


class MachineLocationRegistry:
    """Atomic JSON persistence for stable per-machine location config."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: dict[str, MachineLocationRecord] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "machine location registry contains invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(
                "machine location registry root must be an object"
            )
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                "unsupported machine location schema_version: "
                f"{payload.get('schema_version')!r}"
            )
        rows = payload.get("locations")
        if not isinstance(rows, list):
            raise ValueError(
                "machine location registry locations must be an array"
            )

        loaded: dict[str, MachineLocationRecord] = {}
        for raw in rows:
            if not isinstance(raw, dict):
                raise ValueError(
                    "machine location entry must be an object"
                )
            try:
                updated_at = datetime.fromisoformat(
                    raw["updated_at"]
                )
                record = MachineLocationRecord(
                    machine_id=raw["machine_id"],
                    hostname=raw["hostname"],
                    label=raw["label"],
                    timezone=raw["timezone"],
                    latitude=raw["latitude"],
                    longitude=raw["longitude"],
                    updated_at=updated_at,
                    source=raw.get("source", "operator"),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "invalid machine location entry"
                ) from exc
            if record.machine_id in loaded:
                raise ValueError(
                    "duplicate machine_id in machine location registry"
                )
            loaded[record.machine_id] = record
        self._records = loaded

    def get(
        self,
        machine_id: str,
    ) -> MachineLocationRecord | None:
        if not isinstance(machine_id, str) or not machine_id.strip():
            raise ValueError("machine_id is required")
        return self._records.get(machine_id.strip())

    def find_hostname(
        self,
        hostname: str,
    ) -> tuple[MachineLocationRecord, ...]:
        if not isinstance(hostname, str) or not hostname.strip():
            raise ValueError("hostname is required")
        wanted = hostname.strip().casefold()
        return tuple(
            record
            for record in self.records()
            if record.hostname.casefold() == wanted
        )

    def set(
        self,
        record: MachineLocationRecord,
    ) -> None:
        if not isinstance(record, MachineLocationRecord):
            raise TypeError(
                "record must be MachineLocationRecord"
            )
        self._records[record.machine_id] = record
        self.flush()

    def records(self) -> tuple[MachineLocationRecord, ...]:
        return tuple(
            self._records[key]
            for key in sorted(self._records)
        )

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "locations": [
                {
                    "machine_id": record.machine_id,
                    "hostname": record.hostname,
                    "label": record.label,
                    "timezone": record.timezone,
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "updated_at": record.updated_at.isoformat(),
                    "source": record.source,
                }
                for record in self.records()
            ],
        }
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


def new_machine_location(
    *,
    machine_id: str,
    hostname: str,
    label: str,
    timezone_name: str,
    latitude: float,
    longitude: float,
    source: str = "operator",
    updated_at: datetime | None = None,
) -> MachineLocationRecord:
    return MachineLocationRecord(
        machine_id=machine_id,
        hostname=hostname,
        label=label,
        timezone=timezone_name,
        latitude=latitude,
        longitude=longitude,
        updated_at=updated_at or datetime.now(timezone.utc),
        source=source,
    )
