"""Engineering 22D evidence fusion tests; no sockets or network probes."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.knowledge import PeerKnowledge
from sofia.distributed.model import DistributedNode, NodeObservation, NodeReachability
from sofia.distributed.reachability import (
    ExpectedPeerState, ReachabilityDiscrepancy, assess_peer_reachability,
)

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
AGE = timedelta(minutes=5)


def fixture_peer(base_observation=None):
    node = DistributedNode(uuid4(), "Artemis")
    enrollment = NodeEnrollment(
        node=node, public_key_sha256=fingerprint_public_key(b"example-key"),
        provisioned_at=NOW, recorded_by="operator",
    )
    peers = PeerKnowledge(AGE)
    peers.enroll(enrollment)
    if base_observation is not None:
        peers.record(base_observation)
    return peers.snapshot(node.node_id, now=NOW)


def signal(peer, source, state, at=NOW):
    return NodeObservation(
        node_id=peer.enrollment.node.node_id,
        observed_at=at, source=source, reachability=state,
        evidence=(f"Reported by {source}",),
    )


def assess(peer, *items, expected=ExpectedPeerState.UNSPECIFIED, now=NOW):
    return assess_peer_reachability(peer, observations=items, now=now,
                                    max_age=AGE, expected=expected)


def test_missing_signals_are_unknown_even_when_expected_online():
    peer = fixture_peer()
    result = assess(peer, expected=ExpectedPeerState.EXPECTED_AVAILABLE)
    assert result.reachability is NodeReachability.UNKNOWN
    assert result.discrepancy is ReachabilityDiscrepancy.EXPECTED_AVAILABLE_NOT_CONFIRMED
    assert result.current == ()
    assert not hasattr(result, "authorized")


def test_current_reachable_signal_does_not_grant_authority():
    peer = fixture_peer()
    result = assess(peer, signal(peer, "tcp", NodeReachability.REACHABLE))
    assert result.reachability is NodeReachability.REACHABLE
    assert result.discrepancy is ReachabilityDiscrepancy.NONE
    assert not hasattr(result, "authenticated")
    assert not hasattr(result, "execute")
    with pytest.raises(FrozenInstanceError):
        result.reachability = NodeReachability.UNKNOWN


def test_failed_probe_is_unreachable_not_offline():
    peer = fixture_peer()
    result = assess(peer, signal(peer, "tcp", NodeReachability.UNREACHABLE),
                    expected=ExpectedPeerState.EXPECTED_AVAILABLE)
    assert result.reachability is NodeReachability.UNREACHABLE
    assert result.discrepancy is ReachabilityDiscrepancy.EXPECTED_AVAILABLE_NOT_CONFIRMED
    assert "offline" not in {item.value for item in NodeReachability}


def test_conflicting_sources_report_degraded_and_keep_evidence():
    peer = fixture_peer()
    result = assess(peer, signal(peer, "tcp", NodeReachability.UNREACHABLE),
                    signal(peer, "service", NodeReachability.REACHABLE))
    assert result.reachability is NodeReachability.DEGRADED
    assert result.discrepancy is ReachabilityDiscrepancy.CONFLICTING_EVIDENCE
    assert len(result.current) == 2


def test_latest_per_source_wins_regardless_of_input_order():
    peer = fixture_peer()
    old = signal(peer, "tcp", NodeReachability.UNREACHABLE, NOW - timedelta(seconds=30))
    new = signal(peer, "tcp", NodeReachability.REACHABLE)
    assert assess(peer, old, new).reachability is NodeReachability.REACHABLE
    assert assess(peer, new, old).current == (new,)


def test_stale_and_future_evidence_cannot_claim_current_reachability():
    peer = fixture_peer()
    old = signal(peer, "tcp", NodeReachability.REACHABLE, NOW - AGE - timedelta(seconds=1))
    future = signal(peer, "service", NodeReachability.REACHABLE, NOW + timedelta(seconds=1))
    result = assess(peer, old, future)
    assert result.reachability is NodeReachability.UNKNOWN
    assert result.stale == (old,)
    assert result.future == (future,)


def test_expectation_is_metadata_not_observed_status():
    peer = fixture_peer()
    observed = signal(peer, "tcp", NodeReachability.REACHABLE)
    result = assess(peer, observed, expected=ExpectedPeerState.EXPECTED_UNAVAILABLE)
    assert result.reachability is NodeReachability.REACHABLE
    assert result.discrepancy is ReachabilityDiscrepancy.EXPECTED_UNAVAILABLE_BUT_REACHABLE


def test_22c_snapshot_evidence_is_automatically_included():
    node = DistributedNode(uuid4(), "Eos")
    enrollment = NodeEnrollment(node, fingerprint_public_key(b"different-key"), NOW, "operator")
    knowledge = PeerKnowledge(AGE)
    knowledge.enroll(enrollment)
    record = NodeObservation(node.node_id, NOW, "service", NodeReachability.REACHABLE,
                             evidence=("Service responded",))
    knowledge.record(record)
    peer = knowledge.snapshot(node.node_id, now=NOW)
    result = assess(peer)
    assert result.current == (record,)
    assert result.reachability is NodeReachability.REACHABLE


def test_rejects_mismatched_node_and_timestamp_conflict():
    peer = fixture_peer()
    foreign = NodeObservation(uuid4(), NOW, "tcp", NodeReachability.UNKNOWN)
    with pytest.raises(ValueError, match="enrolled node"):
        assess(peer, foreign)
    first = signal(peer, "tcp", NodeReachability.REACHABLE)
    conflicting = signal(peer, "tcp", NodeReachability.UNREACHABLE)
    with pytest.raises(ValueError, match="Conflicting"):
        assess(peer, first, conflicting)


@pytest.mark.parametrize("invalid", [datetime(2026, 9, 20, 12), None])
def test_invalid_clock_rejected(invalid):
    with pytest.raises((ValueError, TypeError)):
        assess_peer_reachability(fixture_peer(), now=invalid, max_age=AGE)


def test_no_expected_claim_from_stale_snapshot():
    peer = fixture_peer()
    old = signal(peer, "tcp", NodeReachability.REACHABLE, NOW - AGE - timedelta(seconds=1))
    result = assess(peer, old, expected=ExpectedPeerState.EXPECTED_AVAILABLE)
    assert result.reachability is NodeReachability.UNKNOWN
    assert result.discrepancy is ReachabilityDiscrepancy.EXPECTED_AVAILABLE_NOT_CONFIRMED
