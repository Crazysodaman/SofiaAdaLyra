from datetime import datetime, timezone

from sofia.ops.desired import DesiredHostState, DesiredWorkloadPlacement
from sofia.ops.desired_store import DesiredFleetStateStore
from sofia.ops.model import HostLifecycle


NOW = datetime(2026, 10, 3, 15, 30, tzinfo=timezone.utc)


def test_desired_fleet_state_round_trips_and_overwrites(tmp_path):
    store = DesiredFleetStateStore(tmp_path / "sofia.db")

    store.set_host(
        DesiredHostState("artemis", HostLifecycle.HEALTHY),
        at=NOW,
    )
    store.set_workload(
        DesiredWorkloadPlacement("plex", "dionysus"),
        at=NOW,
    )

    assert store.hosts() == (
        DesiredHostState("artemis", HostLifecycle.HEALTHY),
    )
    assert store.workloads() == (
        DesiredWorkloadPlacement("plex", "dionysus"),
    )

    store.set_host(
        DesiredHostState("artemis", HostLifecycle.MAINTENANCE),
        at=NOW,
    )
    store.set_workload(
        DesiredWorkloadPlacement("plex", "persephone"),
        at=NOW,
    )

    assert store.hosts() == (
        DesiredHostState("artemis", HostLifecycle.MAINTENANCE),
    )
    assert store.workloads() == (
        DesiredWorkloadPlacement("plex", "persephone"),
    )


def test_desired_state_removal_is_explicit_and_idempotent(tmp_path):
    store = DesiredFleetStateStore(tmp_path / "sofia.db")
    store.set_host(
        DesiredHostState("artemis", HostLifecycle.HEALTHY),
        at=NOW,
    )
    store.set_workload(
        DesiredWorkloadPlacement("plex", "dionysus"),
        at=NOW,
    )

    assert store.remove_host("artemis") is True
    assert store.remove_host("artemis") is False
    assert store.remove_workload("plex") is True
    assert store.remove_workload("plex") is False
    assert store.hosts() == ()
    assert store.workloads() == ()
