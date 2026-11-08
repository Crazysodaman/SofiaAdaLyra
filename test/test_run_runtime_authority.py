"""CORE-001 disposable local runtime-authority acceptance negatives.

No production state, owner secrets, actual SCM, or external network.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.run.heartbeat import ApplicationHeartbeatStore
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.run.runtime_authority import require_local_runtime_authority
from sofia.platform.safe.operator_stop import OperatorStopStore


def _state(tmp_path: Path):
    path = tmp_path / "disposable-runtime.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved(value TEXT)")
    return path


def _admit(tmp_path):
    path = _state(tmp_path)
    now = datetime.now(timezone.utc)
    leases = LocalRunLeaseStore(path)
    acquired = leases.acquire(
        owner_id="run-watchdog:disposable", now=now, ttl_seconds=180,
    )
    assert acquired.lease is not None
    ApplicationHeartbeatStore(path).bind_generation(
        acquired.lease.epoch, now=now,
    )
    return path, now, leases, acquired.lease


def test_core001_valid_lease_generation_and_stop_clear_are_required(tmp_path):
    path, now, _, lease = _admit(tmp_path)
    observed = require_local_runtime_authority(
        path, expected_epoch=lease.epoch, at=now,
    )
    assert observed.owner_id == lease.owner_id
    assert observed.epoch == lease.epoch


@pytest.mark.parametrize("epoch", [None, 0, -1, True, "1"])
def test_core001_absent_or_invalid_epoch_fails_closed(tmp_path, epoch):
    path, now, _, _ = _admit(tmp_path)
    with pytest.raises(PermissionError, match="positive generation"):
        require_local_runtime_authority(path, expected_epoch=epoch, at=now)


def test_core001_heartbeat_generation_without_lease_does_not_grant_authority(tmp_path):
    path = _state(tmp_path)
    now = datetime.now(timezone.utc)
    ApplicationHeartbeatStore(path).bind_generation(9, now=now)
    with pytest.raises(PermissionError, match="lease"):
        require_local_runtime_authority(path, expected_epoch=9, at=now)


def test_core001_stale_generation_rejected(tmp_path):
    path, now, _, lease = _admit(tmp_path)
    with pytest.raises(PermissionError, match="generation"):
        require_local_runtime_authority(
            path, expected_epoch=lease.epoch + 1, at=now,
        )


def test_core001_expired_lease_cannot_emit_core_ready(tmp_path):
    path, now, _, lease = _admit(tmp_path)
    with pytest.raises(PermissionError, match="lease"):
        require_local_runtime_authority(
            path, expected_epoch=lease.epoch,
            at=now + timedelta(seconds=181),
        )


def test_core001_revoked_lease_cannot_emit_core_ready(tmp_path):
    path, now, leases, lease = _admit(tmp_path)
    leases.release(lease, now=now + timedelta(seconds=1))
    with pytest.raises(PermissionError, match="lease"):
        require_local_runtime_authority(
            path, expected_epoch=lease.epoch, at=now + timedelta(seconds=2),
        )


def test_core001_second_watchdog_cannot_claim_live_authority(tmp_path):
    path, now, leases, lease = _admit(tmp_path)
    second = leases.acquire(
        owner_id="run-watchdog:other", now=now + timedelta(seconds=1),
        ttl_seconds=180,
    )
    assert second.lease is None
    assert second.status == "held_by_other"
    assert require_local_runtime_authority(
        path, expected_epoch=lease.epoch, at=now + timedelta(seconds=1),
    ).owner_id == lease.owner_id


def test_core001_operator_stop_overrides_live_lease(tmp_path):
    path, now, _, lease = _admit(tmp_path)
    OperatorStopStore(path).set(
        active=True, updated_by="Sparks", reason="disposable stop",
    )
    with pytest.raises(PermissionError, match="STOP"):
        require_local_runtime_authority(
            path, expected_epoch=lease.epoch, at=now,
        )


def test_core001_missing_state_cannot_invent_authority(tmp_path):
    with pytest.raises(Exception):
        require_local_runtime_authority(
            tmp_path / "absent.db", expected_epoch=1,
            at=datetime.now(timezone.utc),
        )
    assert not (tmp_path / "absent.db").exists()
