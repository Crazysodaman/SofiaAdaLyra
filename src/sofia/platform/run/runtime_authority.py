"""Local runtime admission proof for service-hosted Core lifecycle.

This checks local RUN evidence only. It is NOT a signed Core release approval,
distributed writer lock, Core Link enrollment, or permission to bypass SAFE.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sofia.platform.run.heartbeat import ApplicationHeartbeatStore
from sofia.platform.run.lease import LocalRunLeaseStore, RunLease
from sofia.platform.safe.operator_stop import OperatorStopStore


def require_local_runtime_authority(
    state_path: Path, *, expected_epoch: int | None,
    at: datetime | None = None,
) -> RunLease:
    """Refuse CORE_READY/start without a fresh local writer lease and STOP check.

    No missing or unknown authority is interpreted as success. Local leases
    prevent duplicate watchdog ownership of this state store; they do not
    solve cross-host network partitions. Full Platform authority is separate.
    """
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be Path")
    if type(expected_epoch) is not int or expected_epoch < 1:
        raise PermissionError("CORE_READY requires a positive generation")
    moment = datetime.now(timezone.utc) if at is None else at
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("authority observation requires timezone-aware time")
    moment = moment.astimezone(timezone.utc)

    # STOP dominates even a live lease. Treat failure to read authority as a
    # failed admission rather than fabricating an unavailable service result.
    if OperatorStopStore(state_path).current().active:
        raise PermissionError("operator STOP denies Core readiness")
    if ApplicationHeartbeatStore(state_path).current_generation() != expected_epoch:
        raise PermissionError("stale or absent runtime generation")
    lease = LocalRunLeaseStore(state_path).current(now=moment)
    if lease is None or lease.epoch != expected_epoch:
        raise PermissionError("Core readiness requires a current local RUN lease")
    return lease
