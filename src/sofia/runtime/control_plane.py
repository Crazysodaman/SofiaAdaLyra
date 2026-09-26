"""Explicit, disabled-by-default wiring for RUN, OPS, ACT, and EVOLVE.

This control plane composes package primitives around the canonical Sofía state
database. It starts no thread, opens no network connection, sends no message,
moves no workload, and grants no amendment authority. Consequential boundaries
remain explicit injected dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from sofia.act.delivery import (
    ActDeliveryRunner,
    ActOutbox,
    BoundMessage,
    DeliveryLimits,
    DeliveryPayload,
    SendResult,
)
from sofia.act.outreach import Policy
from sofia.evolve.approval import ApprovalVerifier
from sofia.evolve.executor import ProtectedAmendmentExecutor, ProtectedPaths
from sofia.evolve.revision import (
    ReviewedRevisionExecutor,
    RevisionAdapter,
    RevisionApprovalVerifier,
)
from sofia.interaction.goal_journal import GoalJournal
from sofia.ops.capability import OpsToolService
from sofia.run.act_schedule import ActSchedulePolicy, ScheduledActRunner
from sofia.run.lease import LocalRunLeaseStore
from sofia.run.periodic import (
    OpportunityPolicy,
    PeriodicThoughtGate,
    PeriodicThoughtRunner,
)
from sofia.run.supervisor import (
    LocalRuntimeSupervisor,
    ManagedRuntimeBackend,
    SupervisorPolicy,
)


class RuntimeControlPlane:
    """Canonical host-side composition boundary for operational packages."""

    def __init__(
        self,
        *,
        state_path: str | Path,
        ops_service: OpsToolService | None = None,
    ) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("state_path is required")

        self.state_path = Path(state_path)
        self.ops_service = (
            ops_service
            if ops_service is not None
            else OpsToolService(self.state_path)
        )
        if not isinstance(self.ops_service, OpsToolService):
            raise TypeError("OpsToolService required")

        self._opened = False
        self._goal_journal: GoalJournal | None = None
        self._act_outbox: ActOutbox | None = None
        self._run_lease_store: LocalRunLeaseStore | None = None
        self._run_periodic_gate: PeriodicThoughtGate | None = None

    @property
    def opened(self) -> bool:
        return self._opened

    def open(self) -> None:
        """Bind durable local primitives after conversation persistence is open."""
        if self._opened:
            return
        if not self.state_path.is_file():
            raise FileNotFoundError("existing application state database required")

        # GoalJournal owns the INTERACT queue schema that ACT binds to.
        goal_journal = GoalJournal(self.state_path)
        act_outbox = ActOutbox(self.state_path)
        run_lease_store = LocalRunLeaseStore(self.state_path)
        run_periodic_gate = PeriodicThoughtGate(
            self.state_path,
            OpportunityPolicy(),
        )

        self._goal_journal = goal_journal
        self._act_outbox = act_outbox
        self._run_lease_store = run_lease_store
        self._run_periodic_gate = run_periodic_gate
        self._opened = True

    def close(self) -> None:
        """Detach operational boundaries; package stores hold no live connection."""
        self._goal_journal = None
        self._act_outbox = None
        self._run_lease_store = None
        self._run_periodic_gate = None
        self._opened = False

    def _require_open(self) -> None:
        if not self._opened:
            raise RuntimeError("runtime control plane is not open")

    @property
    def goal_journal(self) -> GoalJournal:
        self._require_open()
        assert self._goal_journal is not None
        return self._goal_journal

    @property
    def act_outbox(self) -> ActOutbox:
        self._require_open()
        assert self._act_outbox is not None
        return self._act_outbox

    @property
    def run_lease_store(self) -> LocalRunLeaseStore:
        self._require_open()
        assert self._run_lease_store is not None
        return self._run_lease_store

    @property
    def run_periodic_gate(self) -> PeriodicThoughtGate:
        self._require_open()
        assert self._run_periodic_gate is not None
        return self._run_periodic_gate

    def create_periodic_runner(
        self,
        reflect_one: Callable[[], str | None],
        *,
        policy: OpportunityPolicy | None = None,
    ) -> PeriodicThoughtRunner:
        """Create a host-invoked RUN tick; default policy remains disabled."""
        self._require_open()
        gate = (
            self.run_periodic_gate
            if policy is None
            else PeriodicThoughtGate(self.state_path, policy)
        )
        return PeriodicThoughtRunner(gate, reflect_one)

    def create_scheduled_delivery_runner(
        self,
        sender: Callable[[DeliveryPayload], SendResult],
        *,
        policy_for: Callable[[BoundMessage], Policy | None],
        attempt_id_for: Callable[[BoundMessage], str],
        schedule: ActSchedulePolicy = ActSchedulePolicy(),
        limits: DeliveryLimits = DeliveryLimits(),
    ) -> ScheduledActRunner:
        """Create the host-invoked RUN→ACT scheduler; disabled by default."""
        self._require_open()
        return ScheduledActRunner(
            journal=self.goal_journal,
            outbox=self.act_outbox,
            sender=sender,
            policy_for=policy_for,
            attempt_id_for=attempt_id_for,
            schedule=schedule,
            limits=limits,
        )

    def create_delivery_runner(
        self,
        sender: Callable[[DeliveryPayload], SendResult],
        *,
        limits: DeliveryLimits = DeliveryLimits(),
    ) -> ActDeliveryRunner:
        """Create an ACT runner; construction never invokes the sender."""
        self._require_open()
        return ActDeliveryRunner(
            self.act_outbox,
            sender,
            limits=limits,
        )

    def create_supervisor(
        self,
        backend: ManagedRuntimeBackend,
        *,
        policy: SupervisorPolicy = SupervisorPolicy(),
    ) -> LocalRuntimeSupervisor:
        """Create a local RUN reconcile loop around the canonical lease store."""
        self._require_open()
        return LocalRuntimeSupervisor(
            state_path=self.state_path,
            lease_store=self.run_lease_store,
            backend=backend,
            policy=policy,
        )

    def create_reviewed_revision_executor(
        self,
        *,
        adapter: RevisionAdapter,
        verifier: RevisionApprovalVerifier,
    ) -> ReviewedRevisionExecutor:
        """Create EVOLVE config/preference execution with explicit verification."""
        self._require_open()
        return ReviewedRevisionExecutor(
            state_path=self.state_path,
            adapter=adapter,
            verifier=verifier,
        )

    def create_protected_amendment_executor(
        self,
        *,
        paths: ProtectedPaths,
        verifier: ApprovalVerifier,
    ) -> ProtectedAmendmentExecutor:
        """Create protected EVOLVE execution; no verifier is supplied implicitly."""
        self._require_open()
        return ProtectedAmendmentExecutor(
            state_path=self.state_path,
            paths=paths,
            verifier=verifier,
        )
