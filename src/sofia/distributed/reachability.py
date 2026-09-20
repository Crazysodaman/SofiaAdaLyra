"""Engineering 22D: passive, evidence-based peer reachability reconciliation.

No probes, sockets, authentication, node discovery, or remote operations.
An expected state is a human expectation, never observed liveness.
Source names are caller supplied and do not prove signal independence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from sofia.distributed.knowledge import PeerKnowledgeSnapshot
from sofia.distributed.model import NodeObservation, NodeReachability


class ExpectedPeerState(str, Enum):
    UNSPECIFIED = "unspecified"
    EXPECTED_AVAILABLE = "expected_available"
    EXPECTED_UNAVAILABLE = "expected_unavailable"


class ReachabilityDiscrepancy(str, Enum):
    NONE = "none"
    EXPECTED_AVAILABLE_NOT_CONFIRMED = "expected_available_not_confirmed"
    EXPECTED_UNAVAILABLE_BUT_REACHABLE = "expected_unavailable_but_reachable"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


@dataclass(frozen=True)
class PeerReachabilityAssessment:
    """Original evidence remains available; no 'offline' verdict is possible."""

    node_id: object
    expected: ExpectedPeerState
    reachability: NodeReachability
    discrepancy: ReachabilityDiscrepancy
    current: tuple[NodeObservation, ...]
    stale: tuple[NodeObservation, ...]
    future: tuple[NodeObservation, ...]


def assess_peer_reachability(
    peer: PeerKnowledgeSnapshot,
    *,
    observations: tuple[NodeObservation, ...] = (),
    now: datetime,
    max_age: timedelta,
    expected: ExpectedPeerState = ExpectedPeerState.UNSPECIFIED,
) -> PeerReachabilityAssessment:
    """Reconcile the latest *current* caller-supplied evidence per source.

    The 22C latest observation is included automatically. Contradictory
    evidence yields DEGRADED, not a fabricated online/offline decision.
    """
    if not isinstance(peer, PeerKnowledgeSnapshot):
        raise TypeError("peer must be a PeerKnowledgeSnapshot.")
    if not isinstance(observations, tuple):
        raise TypeError("observations must be a tuple.")
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime.")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")
    if not isinstance(max_age, timedelta):
        raise TypeError("max_age must be a timedelta.")
    if max_age <= timedelta(0):
        raise ValueError("max_age must be positive.")
    if not isinstance(expected, ExpectedPeerState):
        raise TypeError("expected must be an ExpectedPeerState.")

    node_id = peer.enrollment.node.node_id
    all_observations = ((peer.observation,) if peer.observation is not None else ()) + observations
    latest: dict[str, NodeObservation] = {}
    stale: list[NodeObservation] = []
    future: list[NodeObservation] = []
    for item in all_observations:
        if not isinstance(item, NodeObservation):
            raise TypeError("observations must contain NodeObservation instances.")
        if item.node_id != node_id:
            raise ValueError("Observation does not belong to the enrolled node.")
        if item.observed_at > now:
            future.append(item)
        elif now - item.observed_at > max_age:
            stale.append(item)
        else:
            previous = latest.get(item.source)
            if previous is None or item.observed_at > previous.observed_at:
                latest[item.source] = item
            elif item.observed_at == previous.observed_at and item != previous:
                raise ValueError("Conflicting evidence from one source has an equal timestamp.")

    current = tuple(latest[source] for source in sorted(latest))
    values = {item.reachability for item in current}
    if NodeReachability.DEGRADED in values or (
        NodeReachability.REACHABLE in values and NodeReachability.UNREACHABLE in values
    ):
        effective = NodeReachability.DEGRADED
    elif NodeReachability.REACHABLE in values:
        effective = NodeReachability.REACHABLE
    elif NodeReachability.UNREACHABLE in values:
        effective = NodeReachability.UNREACHABLE
    else:
        effective = NodeReachability.UNKNOWN

    if effective is NodeReachability.DEGRADED:
        discrepancy = ReachabilityDiscrepancy.CONFLICTING_EVIDENCE
    elif expected is ExpectedPeerState.EXPECTED_AVAILABLE and effective is not NodeReachability.REACHABLE:
        discrepancy = ReachabilityDiscrepancy.EXPECTED_AVAILABLE_NOT_CONFIRMED
    elif expected is ExpectedPeerState.EXPECTED_UNAVAILABLE and effective is NodeReachability.REACHABLE:
        discrepancy = ReachabilityDiscrepancy.EXPECTED_UNAVAILABLE_BUT_REACHABLE
    else:
        discrepancy = ReachabilityDiscrepancy.NONE

    return PeerReachabilityAssessment(
        node_id=node_id,
        expected=expected,
        reachability=effective,
        discrepancy=discrepancy,
        current=current,
        stale=tuple(stale),
        future=tuple(future),
    )
