"""Conservative repair proposals from reviewed Fleet drift.

Drift is evidence that desired and observed state differ. It is not authority
and it is not enough information to guess a repair. This planner proposes only
operations whose next step is structurally unambiguous. It never authorizes or
executes anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .desired import Drift


class RepairProposalKind(str, Enum):
    WORKLOAD_MIGRATION = "workload_migration"
    NO_SAFE_REPAIR = "no_safe_repair"


@dataclass(frozen=True, slots=True)
class FleetRepairProposal:
    drift: Drift
    kind: RepairProposalKind
    reason: str
    workload_id: str | None = None
    source_host_id: str | None = None
    target_host_id: str | None = None
    authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.drift, Drift):
            raise TypeError("drift must be Drift")
        if not isinstance(self.kind, RepairProposalKind):
            raise TypeError("kind must be RepairProposalKind")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")
        if type(self.authorized) is not bool:
            raise TypeError("authorized must be bool")
        if self.authorized:
            raise ValueError(
                "Fleet repair proposals cannot carry execution authority"
            )
        if self.kind is RepairProposalKind.WORKLOAD_MIGRATION:
            if not all(
                isinstance(value, str) and value.strip()
                for value in (
                    self.workload_id,
                    self.source_host_id,
                    self.target_host_id,
                )
            ):
                raise ValueError(
                    "workload migration proposal requires workload/source/target"
                )
        else:
            if any(
                value is not None
                for value in (
                    self.workload_id,
                    self.source_host_id,
                    self.target_host_id,
                )
            ):
                raise ValueError(
                    "no-safe-repair proposal cannot carry migration targets"
                )


class FleetRepairPlanner:
    """Turn drift into reviewable proposals without creating authority."""

    def propose(self, drift: Drift) -> FleetRepairProposal:
        if not isinstance(drift, Drift):
            raise TypeError("drift must be Drift")

        if (
            drift.kind == "workload_placement"
            and drift.observed is not None
            and drift.expected.strip()
            and drift.observed.strip()
            and drift.expected != drift.observed
        ):
            return FleetRepairProposal(
                drift=drift,
                kind=RepairProposalKind.WORKLOAD_MIGRATION,
                reason=(
                    "observed workload host differs from desired host; "
                    "migration may be reviewed"
                ),
                workload_id=drift.subject_id,
                source_host_id=drift.observed,
                target_host_id=drift.expected,
            )

        if drift.kind == "workload_placement" and drift.observed is None:
            return FleetRepairProposal(
                drift=drift,
                kind=RepairProposalKind.NO_SAFE_REPAIR,
                reason=(
                    "workload is not observed on a source host; do not invent "
                    "a migration source or assume it is safe to start"
                ),
            )

        if drift.kind == "host_lifecycle":
            return FleetRepairProposal(
                drift=drift,
                kind=RepairProposalKind.NO_SAFE_REPAIR,
                reason=(
                    "host lifecycle drift does not identify a causal repair; "
                    "inspect health evidence before proposing maintenance"
                ),
            )

        return FleetRepairProposal(
            drift=drift,
            kind=RepairProposalKind.NO_SAFE_REPAIR,
            reason="drift kind has no reviewed automatic repair mapping",
        )

    def propose_all(
        self,
        drift: tuple[Drift, ...],
    ) -> tuple[FleetRepairProposal, ...]:
        if not isinstance(drift, tuple):
            raise TypeError("drift must be a tuple")
        return tuple(self.propose(item) for item in drift)
