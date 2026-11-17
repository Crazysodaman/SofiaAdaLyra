"""Shared inference adapter: policy, budgets, residency and fair dispatch.

The adapter is a bounded coordinator over one exact backend model.  It does not
enroll hosts, reserve resources or grant authority; callers must already hold a
Platform/Fleet admission decision for the work they submit.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Callable, Protocol


from .budget import BudgetLedger
from .contract import (
    BackendOutput, CapacityDenied, GenerationCall,
    InferenceRequest, InferenceResult, InvalidBackendOutput, ModelIdentity,
    ModelNotInstalled, ModelResidencyError, ModelSubstitutionError,
    ProviderPolicy, QueuePressureError, DuplicateInferenceRequest, WorkloadClass,
)
from .gaming import GamingPolicy
from .residency import (
    ModelLoadDeferred, ModelResidencyTracker, ResidencyTelemetry,
)
from .scheduler import (
    CancelOutcome, Claim, FairInferenceScheduler, JobState, JobView,
    SchedulerSnapshot,
)
from .telemetry import (
    CapacityDecision, CapacitySource, HostCapacity, ModelFootprint,
    admit_generation, verified_idle,
)


class InferenceBackend(Protocol):
    """One exact local backend; no fallback routing is permitted here."""

    def generate(self, call: GenerationCall) -> BackendOutput:
        ...

    def cancel(self, job_id: str) -> bool:
        ...


class AdmissionAuthority(Protocol):
    """Narrow view of the existing Platform/Fleet admission decision."""

    def admit(self, request: InferenceRequest, now: float) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class SubmitDecision:
    accepted: bool
    job: JobView | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    result: InferenceResult | None
    reason: str | None
    capacity: CapacityDecision | None
    evidence_level: str | None
    job_state: JobState | None


@dataclass(frozen=True, slots=True)
class CancellationResult:
    outcome: CancelOutcome
    job_state: JobState | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class PreloadDecision:
    allowed: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class AdapterTelemetry:
    model: ModelIdentity
    footprint: ModelFootprint
    scheduler: SchedulerSnapshot
    residency: ResidencyTelemetry
    backend_calls: int
    capacity_denials: int
    last_capacity: CapacityDecision | None


class SharedInferenceAdapter:
    """One shared backend serving multiple isolated Core identities."""

    def __init__(
        self, *,
        backend: InferenceBackend,
        admission: AdmissionAuthority,
        model: ModelIdentity,
        footprint: ModelFootprint,
        policy: ProviderPolicy,
        residency: ModelResidencyTracker,
        capacity: CapacitySource,
        budgets: BudgetLedger,
        scheduler: FairInferenceScheduler | None = None,
        gaming: GamingPolicy | None = None,
        clock: Callable[[], float] = monotonic,
        max_parallel: int = 1,
        keep_alive_seconds: float | None = None,
    ) -> None:
        if not callable(getattr(admission, "admit", None)):
            raise TypeError("admission must expose admit(request, now)")
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if not isinstance(footprint, ModelFootprint):
            raise TypeError("footprint must be ModelFootprint")
        if not isinstance(policy, ProviderPolicy):
            raise TypeError("policy must be ProviderPolicy")
        if not isinstance(residency, ModelResidencyTracker):
            raise TypeError("residency must be ModelResidencyTracker")
        if not callable(capacity.snapshot):
            raise TypeError("capacity source must expose snapshot(now)")
        if not isinstance(budgets, BudgetLedger):
            raise TypeError("budgets must be BudgetLedger")
        if scheduler is not None and not isinstance(scheduler, FairInferenceScheduler):
            raise TypeError("scheduler must be FairInferenceScheduler")
        if gaming is not None and not isinstance(gaming, GamingPolicy):
            raise TypeError("gaming must be GamingPolicy")
        if not callable(clock):
            raise TypeError("clock must be callable")
        if type(max_parallel) is not int or not 1 <= max_parallel <= 8:
            raise ValueError("max_parallel must be in 1..8")
        if keep_alive_seconds is not None and (
            type(keep_alive_seconds) not in (int, float)
            or float(keep_alive_seconds) < 0
        ):
            raise ValueError("keep_alive_seconds must be non-negative or None")
        self.backend = backend
        self.admission = admission
        self.model = model
        self.footprint = footprint
        self.policy = policy
        self.residency = residency
        self.capacity = capacity
        self.budgets = budgets
        self.scheduler = (
            scheduler if scheduler is not None
            else FairInferenceScheduler()
        )
        self.gaming = gaming if gaming is not None else GamingPolicy()
        self.clock = clock
        self.max_parallel = max_parallel
        self.keep_alive_seconds = (
            None if keep_alive_seconds is None else float(keep_alive_seconds)
        )
        self._backend_calls = 0
        self._capacity_denials = 0
        self._last_capacity: CapacityDecision | None = None

    def _now(self, now: float | None) -> float:
        moment = self.clock() if now is None else now
        if type(moment) not in (int, float):
            raise ValueError("now must be a number")
        return float(moment)

    def submit(
        self, *,
        request_id: str,
        core,
        conversation_id: str,
        workload_class: WorkloadClass,
        messages,
        max_output_tokens: int,
        context_tokens: int = 4096,
        timeout_seconds: float = 120.0,
        keep_alive: str | None = None,
        now: float | None = None,
    ) -> SubmitDecision:
        request = InferenceRequest(
            request_id=request_id,
            core=core,
            conversation_id=conversation_id,
            workload_class=workload_class,
            messages=tuple(messages),
            model=self.model,
            context_tokens=context_tokens,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            keep_alive=keep_alive,
        )
        moment = self._now(now)
        try:
            admitted = bool(self.admission.admit(request, moment))
        except Exception:
            return SubmitDecision(
                False, None,
                "Platform/Fleet admission failed closed for this workload",
            )
        if not admitted:
            return SubmitDecision(
                False, None,
                "Platform/Fleet admission denied this workload",
            )
        if not self.policy.allows(self.model):
            return SubmitDecision(
                False, None,
                "provider/model is not authorized; no cloud fallback is permitted",
            )
        if not self.residency.is_installed(self.model):
            return SubmitDecision(
                False, None,
                "exact model is not installed; downloads and CPU fallback are "
                "not permitted",
            )
        budget = self.budgets.check(
            request.core, request.conversation_id,
            request.max_output_tokens, moment,
        )
        if not budget.allowed:
            return SubmitDecision(False, None, budget.reason)
        try:
            job = self.scheduler.enqueue(request, moment)
        except (QueuePressureError, DuplicateInferenceRequest) as exc:
            return SubmitDecision(False, None, str(exc))
        consumed = self.budgets.consume(
            request.core, request.conversation_id,
            request.max_output_tokens, moment,
        )
        if not consumed.allowed:
            self.scheduler.cancel(job.job_id, moment)
            return SubmitDecision(False, None, consumed.reason)
        return SubmitDecision(True, job, None)

    def _capacity_decision(
        self, snapshot: HostCapacity, now: float,
    ) -> CapacityDecision:
        active = self.scheduler.snapshot().active
        decision = admit_generation(
            snapshot, self.footprint, active_generations=active,
            max_parallel=self.max_parallel, now=now,
            already_resident=self.model in self.residency.loaded,
        )
        self._last_capacity = decision
        if not decision.allowed:
            self._capacity_denials += 1
        return decision

    def capacity_decision(self, now: float | None = None) -> CapacityDecision:
        moment = self._now(now)
        return self._capacity_decision(self.capacity.snapshot(moment), moment)

    def dispatch_next(self, now: float | None = None) -> DispatchOutcome:
        moment = self._now(now)
        snapshot = self.capacity.snapshot(moment)
        capacity = self._capacity_decision(snapshot, moment)
        if not capacity.allowed:
            return DispatchOutcome(
                None, capacity.reason, capacity, snapshot.evidence_level, None,
            )
        self.scheduler.set_active_limit(capacity.parallel_slots)
        claim = self.scheduler.claim_next(moment, snapshot.activity, self.gaming)
        if claim is None:
            return DispatchOutcome(
                None, "no admissible inference request", capacity,
                snapshot.evidence_level, None,
            )
        return self._execute(claim, snapshot, capacity, moment)

    def _execute(
        self, claim: Claim, snapshot: HostCapacity, capacity: CapacityDecision,
        now: float,
    ) -> DispatchOutcome:
        idle = verified_idle(snapshot, now)
        allow_load = self.gaming.model_load_allowed(
            claim.request.workload_class, snapshot.activity,
            verified_idle=idle,
        )
        try:
            self.residency.ensure_loaded(
                self.model, self.footprint, snapshot, now,
                allow_load=allow_load,
                keep_alive_seconds=self.keep_alive_seconds,
            )
        except ModelLoadDeferred as exc:
            self.scheduler.requeue(claim, now, str(exc))
            return DispatchOutcome(
                None, str(exc), capacity, snapshot.evidence_level,
                JobState.DEFERRED,
            )
        except ModelNotInstalled as exc:
            self.scheduler.fail(claim.job_id, now, uncertain=False)
            return DispatchOutcome(
                None, str(exc), capacity, snapshot.evidence_level,
                JobState.FAILED,
            )
        except CapacityDenied as exc:
            self.scheduler.requeue(claim, now, str(exc))
            return DispatchOutcome(
                None, str(exc), capacity, snapshot.evidence_level,
                JobState.DEFERRED,
            )
        except ModelResidencyError as exc:
            self.scheduler.fail(claim.job_id, now, uncertain=False)
            return DispatchOutcome(
                None, str(exc), capacity, snapshot.evidence_level,
                JobState.FAILED,
            )

        self.residency.begin_generation(self.model, now)
        call = GenerationCall(
            job_id=claim.job_id,
            request=claim.request,
            model=self.model,
            messages=claim.request.messages,
            context_tokens=claim.request.context_tokens,
            max_output_tokens=claim.request.max_output_tokens,
            keep_alive=claim.request.keep_alive,
            deadline_at=claim.deadline_at,
        )
        try:
            self._backend_calls += 1
            output = self.backend.generate(call)
        except Exception as exc:
            self.residency.end_generation(self.model, now)
            self.scheduler.fail(claim.job_id, now, uncertain=True)
            raise ModelResidencyError(
                "backend generation failed with an uncertain outcome"
            ) from exc
        try:
            result = InferenceResult.build(claim.request, output)
        except (ModelSubstitutionError, InvalidBackendOutput):
            self.residency.end_generation(self.model, now)
            self.scheduler.fail(claim.job_id, now, uncertain=False)
            raise
        self.residency.end_generation(self.model, now)
        self.scheduler.complete(claim.job_id, now)
        return DispatchOutcome(
            result, None, capacity, result.evidence_level.value,
            JobState.COMPLETED,
        )

    def cancel(
        self, job_id: str, now: float | None = None,
    ) -> CancellationResult:
        moment = self._now(now)
        view = self.scheduler.status(job_id)
        if view is None:
            return CancellationResult(CancelOutcome.UNKNOWN_JOB, None, None)
        confirmed: bool | None = None
        if view.state is JobState.IN_FLIGHT:
            try:
                confirmed = bool(self.backend.cancel(job_id))
            except Exception:
                confirmed = False
        outcome = self.scheduler.cancel(
            job_id, moment, backend_confirmed=confirmed,
        )
        updated = self.scheduler.status(job_id)
        if outcome is CancelOutcome.CANCELLED and view.state is JobState.IN_FLIGHT:
            self._safe_end_generation(moment)
        return CancellationResult(
            outcome,
            None if updated is None else updated.state,
            None if updated is None else updated.reason,
        )

    def _safe_end_generation(self, now: float) -> None:
        try:
            self.residency.end_generation(self.model, now)
        except ModelResidencyError:
            pass

    def timeouts(self, now: float | None = None) -> tuple[str, ...]:
        moment = self._now(now)
        changed = self.scheduler.expire(moment)
        for job_id in changed:
            view = self.scheduler.status(job_id)
            if view is None or view.state is not JobState.TIMED_OUT:
                continue
            try:
                self.backend.cancel(job_id)
            except Exception:
                pass
        return changed

    def reconcile(
        self, job_id: str, *, completed: bool,
        output: BackendOutput | None = None,
        now: float | None = None,
    ) -> InferenceResult | None:
        moment = self._now(now)
        view = self.scheduler.status(job_id)
        if view is None:
            raise KeyError("unknown inference job")
        result = None
        if completed:
            if output is None:
                raise ValueError("completed reconciliation requires backend output")
            result = InferenceResult.build(view.request, output)
        self.scheduler.reconcile(job_id, moment, completed=completed)
        if view.state in {JobState.OUTCOME_UNCERTAIN, JobState.TIMED_OUT}:
            self._safe_end_generation(moment)
        return result

    def preload(self, now: float | None = None) -> PreloadDecision:
        moment = self._now(now)
        snapshot = self.capacity.snapshot(moment)
        idle = verified_idle(snapshot, moment)
        if not self.gaming.preload_allowed(snapshot.activity, verified_idle=idle):
            return PreloadDecision(
                False, "background model preload is disabled or not verified idle",
            )
        if not self.residency.is_installed(self.model):
            return PreloadDecision(
                False, "exact model is not installed; downloads are not permitted",
            )
        try:
            self.residency.ensure_loaded(
                self.model, self.footprint, snapshot, moment,
                allow_load=True,
                keep_alive_seconds=self.keep_alive_seconds,
            )
        except (CapacityDenied, ModelResidencyError, ModelNotInstalled) as exc:
            return PreloadDecision(False, str(exc))
        return PreloadDecision(True, None)

    def reclaim(self, now: float | None = None) -> tuple[ModelIdentity, ...]:
        return self.residency.reclaim(self._now(now))

    def telemetry(self) -> AdapterTelemetry:
        return AdapterTelemetry(
            self.model,
            self.footprint,
            self.scheduler.snapshot(),
            self.residency.telemetry(),
            self._backend_calls,
            self._capacity_denials,
            self._last_capacity,
        )
