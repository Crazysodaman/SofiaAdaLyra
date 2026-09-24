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


def runtime_clock_prompt(*, now: datetime | None = None) -> str:
    clock = runtime_clock_snapshot(now=now)
    return (
        "TRUSTED RUNTIME CLOCK\n"
        f"Current UTC: {clock.utc.isoformat()}\n"
        f"Current host-local time: {clock.host_local.isoformat()}\n"
        f"Host timezone label: {clock.host_timezone_label}\n"
        "This is read-only evidence from the running machine clock."
    )
