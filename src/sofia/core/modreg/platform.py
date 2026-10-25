"""Typed Platform module observations and the fake observer for tests.

These contracts mirror the owner-approved Platform interface shapes
(`module.describe`, health V1, placement modes, result statuses) without
importing or reimplementing a Platform. Core consumes observations as
OPERATIONAL EVIDENCE ONLY: availability here never grants execution
authority. When no Platform observer is available, projections must
report UNKNOWN honestly instead of assuming states.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ModuleObservationKind(str, Enum):
    """Files a module-awareness row can be grounded on."""

    DESCRIBED = "described"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    FAILED = "failed"
    UNKNOWN_STATE = "unknown_state"
    QUARANTINED = "quarantined"
    PLACEMENT = "placement"
    OUTCOME = "outcome"


class OutcomeStatus(str, Enum):
    """Result V1 status vocabulary (subset Platform settles)."""

    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUCCEEDED_REPORTED_UNVERIFIED = "succeeded_reported_unverified"
    SUCCEEDED_VERIFIED = "succeeded_verified"


class PlacementMode(str, Enum):
    PORTABLE_STATELESS = "portable_stateless"
    CHECKPOINT_RESTART = "checkpoint_restart"
    HOST_PINNED = "host_pinned"
    CANONICAL_PINNED = "canonical_pinned"


def _aware(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("observation timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ModuleDescribeObservation:
    """module.describe evidence for one installed module instance."""

    module_id: str
    version: str
    capabilities: tuple[str, ...]
    requires_permission: frozenset[str]
    active_profile: str
    simulated_only: frozenset[str]
    observed_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("module_id", self.module_id),
            ("version", self.version),
            ("active_profile", self.active_profile),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if type(self.capabilities) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.capabilities
        ):
            raise TypeError("capabilities must be a tuple of names")
        if not (
            isinstance(self.requires_permission, frozenset)
            and isinstance(self.simulated_only, frozenset)
        ):
            raise TypeError("permission/simulation sets must be frozensets")
        if not self.requires_permission <= set(self.capabilities):
            raise ValueError(
                "requires_permission entries must be declared capabilities"
            )
        if not self.simulated_only <= set(self.capabilities):
            raise ValueError(
                "simulated_only entries must be declared capabilities"
            )
        _aware(self.observed_at)


@dataclass(frozen=True, slots=True)
class ModuleHealthObservation:
    """Health V1 evidence; unreachable and unknown stay truthful."""

    module_instance_id: str
    host_identity: str
    lifecycle: str
    health: ModuleObservationKind
    reason_codes: tuple[str, ...]
    blocked_dependencies: tuple[str, ...]
    fresh_until: datetime
    observed_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("module_instance_id", self.module_instance_id),
            ("host_identity", self.host_identity),
            ("lifecycle", self.lifecycle),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if not isinstance(self.health, ModuleObservationKind) or self.health in (
            ModuleObservationKind.PLACEMENT,
            ModuleObservationKind.OUTCOME,
        ):
            raise TypeError("health must be a health observation kind")
        if type(self.reason_codes) is not tuple or type(
            self.blocked_dependencies
        ) is not tuple:
            raise TypeError("reason/blocked sets must be tuples")
        _aware(self.fresh_until)
        _aware(self.observed_at)
        if self.fresh_until < self.observed_at:
            raise ValueError("freshness cannot precede observation")


@dataclass(frozen=True, slots=True)
class PlacementObservation:
    """One logical module's component placement on enrolled hosts."""

    module_id: str
    component: str
    host_identity: str
    placement_mode: PlacementMode
    eligible_hosts: tuple[str, ...]
    device_affinity: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("module_id", self.module_id),
            ("component", self.component),
            ("host_identity", self.host_identity),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if not isinstance(self.placement_mode, PlacementMode):
            raise TypeError("placement_mode must be a PlacementMode")
        if type(self.eligible_hosts) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.eligible_hosts
        ):
            raise TypeError("eligible_hosts must be a tuple of names")
        if self.device_affinity is not None and (
            not isinstance(self.device_affinity, str)
            or not self.device_affinity.strip()
        ):
            raise ValueError("device_affinity must be None or nonempty")
        _aware(self.observed_at)


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    """A settled effect outcome for one authorized request."""

    request_id: str
    module_id: str
    capability: str
    status: OutcomeStatus
    verification_method: str | None
    error_class: str | None
    settled_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("request_id", self.request_id),
            ("module_id", self.module_id),
            ("capability", self.capability),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if not isinstance(self.status, OutcomeStatus):
            raise TypeError("status must be an OutcomeStatus")
        for optional in (self.verification_method, self.error_class):
            if optional is not None and (
                not isinstance(optional, str) or not optional.strip()
            ):
                raise ValueError(
                    "verification/error fields must be None or nonempty"
                )
        _aware(self.settled_at)


@dataclass(frozen=True, slots=True)
class OutcomePage:
    """Bounded historical outcome page from one observer-owned journal."""

    outcomes: tuple[OutcomeObservation, ...]
    next_cursor: str | None
    has_more: bool

    def __post_init__(self) -> None:
        if type(self.outcomes) is not tuple or any(
            not isinstance(item, OutcomeObservation) for item in self.outcomes
        ):
            raise TypeError("outcomes must be a tuple of OutcomeObservation")
        if self.next_cursor is not None and (
            not isinstance(self.next_cursor, str)
            or not self.next_cursor.strip()
            or len(self.next_cursor) > 200
        ):
            raise ValueError("next_cursor must be None or bounded nonempty text")
        if type(self.has_more) is not bool:
            raise TypeError("has_more must be bool")
        if self.has_more and self.next_cursor is None:
            raise ValueError("a continuing page requires a next cursor")


class PlatformModuleObserver:
    """Read-only seam for Codex's Platform module manager (PLAT-05/07/04).

    Implementations return only observations they can ground. Returning
    empty tuples for absent state is honest and allowed; Core must not
    infer installed/active/authorized from absence of observations.
    """

    def described(self) -> tuple[ModuleDescribeObservation, ...]:
        raise NotImplementedError

    def health(self) -> tuple[ModuleHealthObservation, ...]:
        raise NotImplementedError

    def placements(self) -> tuple[PlacementObservation, ...]:
        raise NotImplementedError

    def outcomes(self) -> tuple[OutcomeObservation, ...]:
        raise NotImplementedError

    def outcome_page(
        self, *, after_cursor: str | None, limit: int,
    ) -> OutcomePage:
        """Compatibility page for observers without durable source cursors.

        Production journal observers override this. Test/fixed observers are
        intentionally a single immutable page and therefore return no cursor.
        """
        if after_cursor is not None:
            return OutcomePage((), None, False)
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("outcome page limit must be in 1..128")
        outcomes = self.outcomes()
        if len(outcomes) > limit:
            raise RuntimeError(
                "observer has no durable cursor for the requested outcome backlog"
            )
        return OutcomePage(tuple(outcomes), None, False)


@dataclass(frozen=True, slots=True)
class FakeCapabilitySpec:
    module_id: str
    version: str
    capabilities: tuple[str, ...]
    requires_permission: tuple[str, ...] = ()
    simulated_only: tuple[str, ...] = ()
    active_profile: str = "OBSERVE"


class FakePlatformModuleObserver(PlatformModuleObserver):
    """Bounded fake Platform adapter for Core-serving tests.

    Records the fixed module world described at construction. It grants
    nothing: Core still has no permission to execute anything.
    """

    def __init__(
        self,
        specs: Sequence[FakeCapabilitySpec] = (),
        health_rows: Sequence[tuple[str, str, ModuleObservationKind]] = (),
        placements: Sequence[PlacementObservation] = (),
        outcomes: Sequence[OutcomeObservation] = (),
        fresh_until: datetime | None = None,
    ) -> None:
        stamp = fresh_until or _aware(
            datetime.now(timezone.utc)
        )
        self._described: tuple[ModuleDescribeObservation, ...] = tuple(
            ModuleDescribeObservation(
                module_id=spec.module_id,
                version=spec.version,
                capabilities=tuple(spec.capabilities),
                requires_permission=frozenset(spec.requires_permission),
                active_profile=spec.active_profile,
                simulated_only=frozenset(spec.simulated_only),
                observed_at=stamp,
            )
            for spec in specs
        )
        self._health: tuple[ModuleHealthObservation, ...] = tuple(
            ModuleHealthObservation(
                module_instance_id=instance,
                host_identity=host,
                lifecycle="ACTIVE",
                health=kind,
                reason_codes=(),
                blocked_dependencies=(),
                fresh_until=stamp,
                observed_at=stamp,
            )
            for instance, host, kind in health_rows
        )
        self._placements: tuple[PlacementObservation, ...] = tuple(placements)
        self._outcomes: tuple[OutcomeObservation, ...] = tuple(outcomes)

    def described(self) -> tuple[ModuleDescribeObservation, ...]:
        return self._described

    def health(self) -> tuple[ModuleHealthObservation, ...]:
        return self._health

    def placements(self) -> tuple[PlacementObservation, ...]:
        return self._placements

    def outcomes(self) -> tuple[OutcomeObservation, ...]:
        return self._outcomes
