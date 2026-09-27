from datetime import datetime, timezone

import sofia.distributed.agent_tools as tools_module
from sofia.distributed.agent_tools import create_default_agent_dispatcher
from sofia.ops.model import HostTelemetry


def test_default_agent_advertises_read_only_ops_telemetry():
    dispatcher = create_default_agent_dispatcher()
    capabilities = {
        item.name: set(item.operations)
        for item in dispatcher.inventory()
    }

    assert "ops.telemetry" in capabilities
    assert capabilities["ops.telemetry"] == {"latest"}


def test_ops_telemetry_handler_returns_plain_normalized_snapshot(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "collect_local_telemetry",
        lambda: HostTelemetry(
            observed_at=datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc),
            cpu_percent=25.0,
            ram_used_bytes=4,
            ram_total_bytes=8,
            storage_free_bytes=16,
        ),
    )
    dispatcher = create_default_agent_dispatcher()

    result = dispatcher.execute("ops.telemetry", "latest", {})

    assert result["cpu_percent"] == 25.0
    assert result["ram_used_bytes"] == 4
    assert result["ram_total_bytes"] == 8
    assert result["storage_free_bytes"] == 16
