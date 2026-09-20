"""Offline acceptance tests for the first Engineering Batch 22A slice."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.distributed.model import (
    DistributedNode,
    NodeEndpoint,
    NodeObservation,
    NodeReachability,
    NodeTransport,
)


def test_node_identity_survives_hostname_change():
    node_id = uuid4()
    node = DistributedNode(node_id=node_id, name="Artemis")
    first = NodeObservation(
        node_id=node.node_id,
        observed_at=datetime.now(timezone.utc),
        source="authorized_probe",
        reachability=NodeReachability.REACHABLE,
        endpoint=NodeEndpoint("artemis.lan", 22, NodeTransport.SSH),
        evidence=("authenticated endpoint responded",),
    )
    later = NodeObservation(
        node_id=node.node_id,
        observed_at=datetime.now(timezone.utc),
        source="authorized_probe",
        reachability=NodeReachability.REACHABLE,
        endpoint=NodeEndpoint("artemis-new.lan", 22, NodeTransport.SSH),
        evidence=("authenticated endpoint responded",),
    )
    assert first.node_id == later.node_id == node.node_id
    assert first.endpoint != later.endpoint


def test_unreachable_is_not_claimed_offline_or_authorized():
    observation = NodeObservation(
        node_id=uuid4(),
        observed_at=datetime.now(timezone.utc),
        source="tcp_probe",
        reachability=NodeReachability.UNREACHABLE,
        evidence=("TCP connection timed out",),
    )
    assert observation.reachability is NodeReachability.UNREACHABLE
    assert "offline" not in {state.value for state in NodeReachability}
    assert not hasattr(observation, "authorized")
    assert not hasattr(observation, "execute")


def test_unknown_is_explicit_and_requires_no_invented_evidence():
    observation = NodeObservation(
        node_id=uuid4(),
        observed_at=datetime.now(timezone.utc),
        source="inventory",
        reachability=NodeReachability.UNKNOWN,
    )
    assert observation.endpoint is None
    assert observation.evidence == ()


def test_reachability_claim_without_evidence_fails_closed():
    with pytest.raises(ValueError, match="requires evidence"):
        NodeObservation(
            node_id=uuid4(),
            observed_at=datetime.now(timezone.utc),
            source="probe",
            reachability=NodeReachability.REACHABLE,
        )


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        NodeObservation(
            node_id=uuid4(),
            observed_at=datetime(2026, 9, 20),
            source="probe",
            reachability=NodeReachability.UNKNOWN,
        )


@pytest.mark.parametrize("port", [0, 65536, True, "22"])
def test_invalid_endpoint_port_is_rejected(port):
    with pytest.raises(ValueError, match="port"):
        NodeEndpoint("artemis.lan", port, NodeTransport.SSH)


def test_contracts_are_immutable():
    node = DistributedNode(node_id=uuid4(), name="Artemis")
    with pytest.raises(FrozenInstanceError):
        node.name = "different"
    observation = NodeObservation(
        node_id=node.node_id,
        observed_at=datetime.now(timezone.utc),
        source="inventory",
        reachability=NodeReachability.UNKNOWN,
    )
    with pytest.raises(FrozenInstanceError):
        observation.source = "rewritten"
