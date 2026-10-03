from datetime import datetime, timezone

from sofia.ops.workload import WorkloadInstance, WorkloadPhase
from sofia.ops.workload_store import WorkloadInstanceStore


NOW = datetime(2026, 10, 3, 15, 45, tzinfo=timezone.utc)


def test_workload_instance_store_round_trips_and_updates(tmp_path):
    store = WorkloadInstanceStore(tmp_path / "sofia.db")
    original = WorkloadInstance(
        instance_id="plex-1",
        workload_id="plex",
        version="1",
        host_id="venus",
        phase=WorkloadPhase.READY,
        lease_epoch=4,
    )
    store.observe(original, at=NOW)

    assert store.instances() == (original,)

    moved = WorkloadInstance(
        instance_id="plex-1",
        workload_id="plex",
        version="2",
        host_id="artemis",
        phase=WorkloadPhase.STARTING,
        lease_epoch=5,
    )
    store.observe(moved, at=NOW)

    assert store.instances() == (moved,)


def test_workload_instance_removal_is_explicit(tmp_path):
    store = WorkloadInstanceStore(tmp_path / "sofia.db")
    store.observe(
        WorkloadInstance(
            instance_id="plex-1",
            workload_id="plex",
            version="1",
            host_id="venus",
            phase=WorkloadPhase.READY,
        ),
        at=NOW,
    )

    assert store.remove("plex-1") is True
    assert store.remove("plex-1") is False
    assert store.instances() == ()
