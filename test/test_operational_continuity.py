from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)
from sofia.operational.store import OperationalStore


def test_first_runtime_has_unknown_continuity(
    tmp_path: Path,
):
    store = OperationalStore(
        tmp_path / "sofia.db"
    )

    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    continuity = store.continuity_for(
        current_runtime_id=runtime_id,
        current_started_at=started_at,
    )

    assert continuity.evidence_status is (
        ContinuityEvidenceStatus.UNKNOWN
    )

    assert continuity.current_runtime_id == runtime_id
    assert continuity.current_started_at == started_at

    assert continuity.previous_runtime_id is None
    assert continuity.previous_started_at is None
    assert continuity.previous_stopped_at is None
    assert continuity.previous_lifecycle_state is None

    assert continuity.restart_observed is None

    store.close()


def test_previous_successful_runtime_is_observed(
    tmp_path: Path,
):
    store = OperationalStore(
        tmp_path / "sofia.db"
    )

    first_runtime_id = uuid4()
    first_started_at = datetime.now(timezone.utc)

    store.record_started(
        runtime_id=first_runtime_id,
        started_at=first_started_at,
    )

    first_stopped_at = (
        first_started_at
        + timedelta(seconds=5)
    )

    store.record_stopped(
        runtime_id=first_runtime_id,
        stopped_at=first_stopped_at,
    )

    second_runtime_id = uuid4()
    second_started_at = (
        first_stopped_at
        + timedelta(seconds=5)
    )

    continuity = store.continuity_for(
        current_runtime_id=second_runtime_id,
        current_started_at=second_started_at,
    )

    assert continuity.evidence_status is (
        ContinuityEvidenceStatus.OBSERVED
    )

    assert continuity.current_runtime_id == second_runtime_id
    assert continuity.current_started_at == second_started_at

    assert continuity.previous_runtime_id == first_runtime_id
    assert continuity.previous_started_at == first_started_at
    assert continuity.previous_stopped_at == first_stopped_at
    assert continuity.previous_lifecycle_state == "stopped"

    assert continuity.restart_observed is True

    store.close()


def test_runtime_history_survives_store_recreation(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"

    first_store = OperationalStore(
        database_path
    )

    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    first_store.record_started(
        runtime_id=runtime_id,
        started_at=started_at,
    )

    stopped_at = started_at + timedelta(
        seconds=10
    )

    first_store.record_stopped(
        runtime_id=runtime_id,
        stopped_at=stopped_at,
    )

    first_store.close()

    second_store = OperationalStore(
        database_path
    )

    current_runtime_id = uuid4()
    current_started_at = stopped_at + timedelta(
        seconds=10
    )

    continuity = second_store.continuity_for(
        current_runtime_id=current_runtime_id,
        current_started_at=current_started_at,
    )

    assert continuity.previous_runtime_id == runtime_id
    assert continuity.previous_started_at == started_at
    assert continuity.previous_stopped_at == stopped_at

    second_store.close()


def test_failed_start_record_is_not_created(
    tmp_path: Path,
):
    store = OperationalStore(
        tmp_path / "sofia.db"
    )

    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    with pytest.raises(RuntimeError):
        raise RuntimeError("simulated startup failure")

    assert store.latest_runtime() is None

    store.close()


def test_runtime_continuity_is_immutable():
    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.UNKNOWN,
        current_runtime_id=runtime_id,
        current_started_at=started_at,
    )

    with pytest.raises(AttributeError):
        continuity.current_runtime_id = uuid4()


def test_observed_continuity_requires_previous_runtime():
    with pytest.raises(ValueError):
        RuntimeContinuity(
            evidence_status=ContinuityEvidenceStatus.OBSERVED,
            current_runtime_id=uuid4(),
            current_started_at=datetime.now(timezone.utc),
        )


def test_continuity_requires_timezone_aware_current_start():
    with pytest.raises(ValueError):
        RuntimeContinuity(
            evidence_status=ContinuityEvidenceStatus.UNKNOWN,
            current_runtime_id=uuid4(),
            current_started_at=datetime.now(),
        )


def test_store_rejects_naive_start_timestamp(
    tmp_path: Path,
):
    store = OperationalStore(
        tmp_path / "sofia.db"
    )

    with pytest.raises(ValueError):
        store.record_started(
            runtime_id=uuid4(),
            started_at=datetime.now(),
        )

    store.close()


def test_store_rejects_naive_stop_timestamp(
    tmp_path: Path,
):
    store = OperationalStore(
        tmp_path / "sofia.db"
    )

    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    store.record_started(
        runtime_id=runtime_id,
        started_at=started_at,
    )

    with pytest.raises(ValueError):
        store.record_stopped(
            runtime_id=runtime_id,
            stopped_at=datetime.now(),
        )

    store.close()