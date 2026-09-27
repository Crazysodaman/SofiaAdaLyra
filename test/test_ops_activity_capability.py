from datetime import datetime, timezone
import sqlite3

from sofia.ops import ActivityMode, FleetHost, HostLifecycle, HostTelemetry
from sofia.ops.capability import OpsToolService


NOW = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)


def _host(host_id: str, cpu: float) -> FleetHost:
    return FleetHost(
        host_id,
        "windows",
        "x86_64",
        HostLifecycle.CANDIDATE,
        True,
        HostTelemetry(
            NOW,
            cpu_percent=cpu,
            ram_used_bytes=1,
            ram_total_bytes=100,
        ),
    )


def test_ops_tool_placement_uses_same_durable_game_mode_evidence(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    service.activity.set_override("venus", ActivityMode.GAMING, at=NOW)
    service.activity.set_override("artemis", ActivityMode.NORMAL, at=NOW)

    decision = service.choose_placement(
        {
            "workload_id": "background",
            "version": "1",
            "supported_platforms": ["windows"],
            "supported_architectures": ["x86_64"],
        }
    )

    assert decision["host_id"] == "artemis"
    assert decision["eligible_hosts"][0] == "artemis"


def test_ops_tool_can_explicitly_allow_interactive_host(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass

    service = OpsToolService(state)
    for host in (_host("venus", 5), _host("artemis", 30)):
        service.registry.register_candidate(host)
        service.registry.transition(host.host_id, HostLifecycle.ENROLLED)
        service.registry.transition(host.host_id, HostLifecycle.HEALTHY)

    service.activity.set_override("venus", ActivityMode.GAMING, at=NOW)

    decision = service.choose_placement(
        {
            "workload_id": "desktop-client",
            "version": "1",
            "supported_platforms": ["windows"],
            "supported_architectures": ["x86_64"],
            "allow_interactive_host": True,
        }
    )

    assert decision["host_id"] == "venus"
