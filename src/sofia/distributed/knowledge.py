"""Batch 22C: in-memory, evidence-based knowledge about enrolled peers.

This is NOT network discovery, authentication, liveness, or authorization.
An UNREACHABLE observation records a failed attempt, not an offline host.
Enrollment is a human-supplied identity/key pin, not proof of possession.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from sofia.distributed.identity import NodeEnrollment, NodeIdentityRegistry
from sofia.distributed.model import NodeObservation, NodeReachability


class PeerEvidenceFreshness(str, Enum):
    UNOBSERVED = "unobserved"
    CURRENT = "current"
    STALE = "stale"
    CLOCK_SKEW = "clock_skew"


@dataclass(frozen=True)
class PeerKnowledgeSnapshot:
    """Immutable view; neither reachability nor enrollment confers authority."""

    enrollment: NodeEnrollment
    observation: NodeObservation | None
    freshness: PeerEvidenceFreshness

    @property
    def reachability(self) -> NodeReachability:
        if self.observation is None or self.freshness is not PeerEvidenceFreshness.CURRENT:
            return NodeReachability.UNKNOWN
        return self.observation.reachability


class PeerKnowledge:
    """Records observations only for enrolled node IDs; never performs probes."""

    def __init__(self, max_age: timedelta) -> None:
        if not isinstance(max_age, timedelta):
            raise TypeError("max_age must be a timedelta.")
        if max_age <= timedelta(0):
            raise ValueError("max_age must be positive.")
        self._max_age = max_age
        self._identity = NodeIdentityRegistry()
        self._observations: dict[UUID, NodeObservation] = {}

    def enroll(self, record: NodeEnrollment) -> None:
        self._identity.enroll(record)

    def record(self, observation: NodeObservation) -> None:
        if not isinstance(observation, NodeObservation):
            raise TypeError("observation must be a NodeObservation.")
        if self._identity.get(observation.node_id) is None:
            raise ValueError("Cannot record an observation for an unenrolled node.")
        previous = self._observations.get(observation.node_id)
        if previous is not None:
            if observation.observed_at < previous.observed_at:
                raise ValueError("Older peer evidence cannot replace newer evidence.")
            if observation.observed_at == previous.observed_at:
                if observation == previous:
                    return  # Exact duplicate is idempotent.
                raise ValueError("Conflicting peer evidence has an equal timestamp.")
        self._observations[observation.node_id] = observation

    def snapshot(self, node_id: UUID, *, now: datetime) -> PeerKnowledgeSnapshot | None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID.")
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime.")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")
        enrollment = self._identity.get(node_id)
        if enrollment is None:
            return None
        observation = self._observations.get(node_id)
        if observation is None:
            freshness = PeerEvidenceFreshness.UNOBSERVED
        elif observation.observed_at > now:
            freshness = PeerEvidenceFreshness.CLOCK_SKEW
        elif now - observation.observed_at > self._max_age:
            freshness = PeerEvidenceFreshness.STALE
        else:
            freshness = PeerEvidenceFreshness.CURRENT
        return PeerKnowledgeSnapshot(enrollment, observation, freshness)
