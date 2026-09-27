"""Fleet release convergence evidence and rollout planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sofia.release_integrity.manifest import ReleaseManifest


class NodeReleaseState(str, Enum):
    CURRENT = "current"
    OUTDATED = "outdated"
    CORRUPT = "corrupt"
    INCOMPATIBLE = "incompatible"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NodeReleaseObservation:
    host_id: str
    observed_at: datetime
    release_id: str | None
    manifest_digest: str | None
    signature_verified: bool
    artifacts_verified: bool
    state_schema_revision: int
    fleet_protocol_revision: int
    agent_protocol_revision: int
    healthy: bool
    quarantined: bool = False

    def __post_init__(self) -> None:
        if not self.host_id.strip():
            raise ValueError("host_id required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        for value in (
            self.signature_verified,
            self.artifacts_verified,
            self.healthy,
            self.quarantined,
        ):
            if not isinstance(value, bool):
                raise TypeError("release observation flags must be boolean")
        for label, value in (
            ("state_schema_revision", self.state_schema_revision),
            ("fleet_protocol_revision", self.fleet_protocol_revision),
            ("agent_protocol_revision", self.agent_protocol_revision),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be nonnegative")


def classify_release(
    observation: NodeReleaseObservation,
    target: ReleaseManifest,
) -> NodeReleaseState:
    if not isinstance(observation, NodeReleaseObservation):
        raise TypeError("NodeReleaseObservation required")
    if not isinstance(target, ReleaseManifest):
        raise TypeError("ReleaseManifest required")
    if observation.quarantined:
        return NodeReleaseState.QUARANTINED
    if (
        observation.release_id is None
        or observation.manifest_digest is None
    ):
        return NodeReleaseState.UNKNOWN
    if not observation.signature_verified or not observation.artifacts_verified:
        return NodeReleaseState.CORRUPT
    if (
        not target.state_schema.accepts(observation.state_schema_revision)
        or not target.fleet_protocol.accepts(
            observation.fleet_protocol_revision
        )
        or not target.agent_protocol.accepts(
            observation.agent_protocol_revision
        )
    ):
        return NodeReleaseState.INCOMPATIBLE
    if (
        observation.release_id != target.release_id
        or observation.manifest_digest != target.manifest_digest
    ):
        return NodeReleaseState.OUTDATED
    if not observation.healthy:
        return NodeReleaseState.UNKNOWN
    return NodeReleaseState.CURRENT


@dataclass(frozen=True, slots=True)
class RolloutPlan:
    release_id: str
    canary_hosts: tuple[str, ...]
    waves: tuple[tuple[str, ...], ...]


def plan_rollout(
    *,
    target: ReleaseManifest,
    eligible_host_ids: tuple[str, ...],
    canary_host_ids: tuple[str, ...],
    wave_size: int = 2,
) -> RolloutPlan:
    if not isinstance(target, ReleaseManifest):
        raise TypeError("ReleaseManifest required")
    if target.signature is None:
        raise PermissionError("Fleet rollout requires a signed release manifest")
    if type(wave_size) is not int or wave_size < 1:
        raise ValueError("wave_size must be positive")
    eligible = tuple(dict.fromkeys(eligible_host_ids))
    canaries = tuple(dict.fromkeys(canary_host_ids))
    if not canaries:
        raise ValueError("at least one explicit canary host is required")
    if any(host not in eligible for host in canaries):
        raise ValueError("canary hosts must be rollout-eligible")
    remainder = tuple(host for host in eligible if host not in set(canaries))
    waves = tuple(
        remainder[index:index + wave_size]
        for index in range(0, len(remainder), wave_size)
    )
    return RolloutPlan(
        release_id=target.release_id,
        canary_hosts=canaries,
        waves=waves,
    )
