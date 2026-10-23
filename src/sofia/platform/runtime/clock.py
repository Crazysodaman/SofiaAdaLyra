"""Read-only runtime clock evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RuntimeClockSnapshot:
    utc: datetime
    host_local: datetime
    host_timezone_label: str


def runtime_clock_snapshot(*, now: datetime | None = None) -> RuntimeClockSnapshot:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Clock time must be timezone-aware.")
    utc = current.astimezone(timezone.utc)
    local = utc.astimezone()
    return RuntimeClockSnapshot(
        utc=utc,
        host_local=local,
        host_timezone_label=local.tzname() or "unknown",
    )
