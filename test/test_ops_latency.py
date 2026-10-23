from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.ops.latency import FleetLatencyStore


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def test_authenticated_round_trips_dedupe_and_survive_restart(canonical_state_path):
    node_id = uuid4()
    request_ids = [uuid4() for _ in range(3)]
    store = FleetLatencyStore(canonical_state_path)
    for index, request_id in enumerate(request_ids):
        assert store.append_authenticated(
            request_id=request_id, host_id="artemis", node_id=node_id,
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=10.0 + index,
            observed_at=NOW + timedelta(seconds=index),
        )
    assert not store.append_authenticated(
        request_id=request_ids[-1], host_id="artemis", node_id=node_id,
        capability="system.inspect", operation="system",
        outcome="reported_success", elapsed_ms=999.0,
        observed_at=NOW + timedelta(seconds=3),
    )

    estimate = FleetLatencyStore(canonical_state_path).estimate(
        host_id="artemis", node_id=node_id, at=NOW + timedelta(seconds=4),
    )
    assert estimate is not None
    assert estimate.sample_count == 3
    assert estimate.baseline_last_ms == 12.0
    assert 10.0 <= estimate.predicted_ms <= 12.0
    assert estimate.evidence_kind == "pinned_mtls_operation_result"


def test_latency_estimate_never_crosses_host_or_node_identity(canonical_state_path):
    store = FleetLatencyStore(canonical_state_path)
    expected = uuid4()
    for _ in range(3):
        store.append_authenticated(
            request_id=uuid4(), host_id="venus", node_id=uuid4(),
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=20.0, observed_at=NOW,
        )
    assert store.estimate(host_id="venus", node_id=expected, at=NOW) is None
    assert store.estimate(host_id="artemis", node_id=expected, at=NOW) is None


@pytest.mark.parametrize("elapsed", (0.0, -1.0, float("inf"), float("nan"), 7_200_001.0))
def test_latency_store_rejects_invalid_measurements(canonical_state_path, elapsed):
    with pytest.raises(ValueError):
        FleetLatencyStore(canonical_state_path).append_authenticated(
            request_id=uuid4(), host_id="venus", node_id=uuid4(),
            capability="system.inspect", operation="system",
            outcome="reported_success", elapsed_ms=elapsed, observed_at=NOW,
        )
