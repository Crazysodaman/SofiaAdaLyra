"""Engineering 22C deterministic peer evidence contracts; no network calls."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.knowledge import PeerEvidenceFreshness, PeerKnowledge
from sofia.distributed.model import DistributedNode, NodeObservation, NodeReachability


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def enrolled(name="Artemis"):
    return NodeEnrollment(
        node=DistributedNode(uuid4(), name),
        public_key_sha256=fingerprint_public_key(name.encode()),
        provisioned_at=NOW,
        recorded_by="operator",
    )


def observed(record, when=NOW, reachability=NodeReachability.REACHABLE,
             evidence=("TCP endpoint answered",)):
    return NodeObservation(
        node_id=record.node.node_id,
        observed_at=when,
        source="explicit authorized inspection",
        reachability=reachability,
        evidence=evidence,
    )


def test_unobserved_enrollment_has_unknown_reachability():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.enrollment is record
    assert view.observation is None
    assert view.freshness is PeerEvidenceFreshness.UNOBSERVED
    assert view.reachability is NodeReachability.UNKNOWN
    assert peers.snapshot(uuid4(), now=NOW) is None


def test_recent_observation_is_current_but_not_authority():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    evidence = observed(record)
    peers.record(evidence)
    view = peers.snapshot(record.node.node_id, now=NOW + timedelta(minutes=5))
    assert view.freshness is PeerEvidenceFreshness.CURRENT
    assert view.observation is evidence
    assert view.reachability is NodeReachability.REACHABLE
    assert not hasattr(view, "authorized")
    assert not hasattr(peers, "execute")
    with pytest.raises(FrozenInstanceError):
        view.freshness = PeerEvidenceFreshness.STALE


def test_stale_reachability_falls_back_to_unknown_without_erasing_evidence():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    evidence = observed(record)
    peers.record(evidence)
    view = peers.snapshot(record.node.node_id, now=NOW + timedelta(minutes=5, seconds=1))
    assert view.freshness is PeerEvidenceFreshness.STALE
    assert view.reachability is NodeReachability.UNKNOWN
    assert view.observation is evidence


def test_unreachable_is_not_offline():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    peers.record(observed(record, reachability=NodeReachability.UNREACHABLE,
                          evidence=("TCP timeout",)))
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.reachability is NodeReachability.UNREACHABLE
    assert "offline" not in {state.value for state in NodeReachability}


def test_unknown_identity_cannot_insert_observation():
    peers = PeerKnowledge(timedelta(minutes=5))
    with pytest.raises(ValueError, match="unenrolled"):
        peers.record(observed(enrolled()))


def test_old_or_conflicting_observations_cannot_overwrite_latest():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    recent = observed(record, NOW)
    peers.record(recent)
    peers.record(recent)
    with pytest.raises(ValueError, match="Older"):
        peers.record(observed(record, NOW - timedelta(seconds=1)))
    with pytest.raises(ValueError, match="Conflicting"):
        peers.record(observed(record, NOW, NodeReachability.UNREACHABLE, ("fail",)))
    assert peers.snapshot(record.node.node_id, now=NOW).observation is recent


def test_clock_skew_cannot_report_future_evidence_as_current():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    peers.record(observed(record, NOW + timedelta(seconds=5)))
    view = peers.snapshot(record.node.node_id, now=NOW)
    assert view.freshness is PeerEvidenceFreshness.CLOCK_SKEW
    assert view.reachability is NodeReachability.UNKNOWN


@pytest.mark.parametrize("max_age", [timedelta(0), timedelta(seconds=-1), None, 30])
def test_invalid_freshness_window_rejected(max_age):
    with pytest.raises((TypeError, ValueError)):
        PeerKnowledge(max_age)


def test_snapshot_requires_timezone_aware_clock():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    with pytest.raises(ValueError, match="timezone-aware"):
        peers.snapshot(record.node.node_id, now=datetime(2026, 9, 20, 12))


def test_enrollment_conflicts_remain_rejected():
    peers = PeerKnowledge(timedelta(minutes=5))
    record = enrolled()
    peers.enroll(record)
    with pytest.raises(ValueError, match="already enrolled"):
        peers.enroll(record)
