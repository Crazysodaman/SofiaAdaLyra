"""Fair, priority-aware queue coordinator for one shared inference backend.

This is intentionally not a global scheduler.  Platform/Fleet admission remains
authoritative; this coordinator only orders already-authorized generation work
and enforces per-Core queue fairness, deadlines and explicit outcome states.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from threading import RLock
from uuid import UUID

from .contract import (
    DuplicateInferenceRequest, InferenceRequest, QueuePressureError,
)
from .gaming import GamingPolicy
from sofia.platform.ops.activity import ActivityMode


class JobState(str, Enum):
    QUEUED = "queued"
    DEFERRED = "deferred"
    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    OUTCOME_UNCERTAIN = "outcome_uncertain"
    EXPIRED = "expired"


class CancelOutcome(str, Enum):
    CANCELLED = "cancelled"
    OUTCOME_UNCERTAIN = "outcome_uncertain"
    ALREADY_COMPLETED = "already_completed"
    UNKNOWN_JOB = "unknown_job"


@dataclass(frozen=True, slots=True)
class SchedulerLimits:
    max_active: int = 1
    max_queue_per_core: int = 4
    max_pending_per_conversation: int = 2

    def __post_init__(self) -> None:
        for label in (
            "max_active", "max_queue_per_core", "max_pending_per_conversation",
        ):
            value = getattr(self, label)
            if type(value) is not int or value < 1:
                raise ValueError(f"{label} must be a positive integer")


@dataclass(frozen=True, slots=True)
class JobView:
    job_id: str
    state: JobState
    request: InferenceRequest
    submitted_at: float
    deadline_at: float
    result_uncertain: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Claim:
    job_id: str
    request: InferenceRequest
    deadline_at: float


@dataclass(frozen=True, slots=True)
class SchedulerSnapshot:
    active: int
    max_active: int
    queued: int
    deferred: int
    in_flight: int
    completed: int
    failed: int
    cancelled: int
    timed_out: int
    expired: int
    outcome_uncertain: int
    per_core_pending: tuple[tuple[UUID, int], ...]


@dataclass(slots=True)
class _Job:
    job_id: str
    request: InferenceRequest
    state: JobState
    submitted_at: float
    deadline_at: float
    sequence: int
    result_uncertain: bool = False
    holds_slot: bool = False
    reason: str | None = None

    def view(self) -> JobView:
        return JobView(
            self.job_id, self.state, self.request, self.submitted_at,
            self.deadline_at, self.result_uncertain, self.reason,
        )


def _now(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError("now must be a finite number")
    return float(value)


class FairInferenceScheduler:
    """One backend queue with class priority and per-Core fair share."""

    def __init__(self, limits: SchedulerLimits | None = None) -> None:
        self.limits = limits if limits is not None else SchedulerLimits()
        if not isinstance(self.limits, SchedulerLimits):
            raise TypeError("limits must be SchedulerLimits")
        self._max_active = self.limits.max_active
        self._lock = RLock()
        self._jobs: dict[str, _Job] = {}
        self._order: list[str] = []
        self._sequence = 0
        self._active = 0
        self._served: dict[UUID, int] = {}

    def _pending(self, *, core_id: UUID | None = None, conversation: tuple | None = None) -> int:
        total = 0
        for job in self._jobs.values():
            if job.state not in {JobState.QUEUED, JobState.DEFERRED}:
                continue
            if core_id is not None and job.request.core.core_id != core_id:
                continue
            if conversation is not None and (
                job.request.core.core_id,
                job.request.core.platform_id,
                job.request.core.generation,
                job.request.conversation_id,
            ) != conversation:
                continue
            total += 1
        return total

    def enqueue(self, request: InferenceRequest, now: float) -> JobView:
        if not isinstance(request, InferenceRequest):
            raise TypeError("request must be InferenceRequest")
        moment = _now(now)
        with self._lock:
            if request.request_id in self._jobs:
                raise DuplicateInferenceRequest(
                    "request_id already exists; reuse is not idempotent"
                )
            if self._pending(core_id=request.core.core_id) >= (
                self.limits.max_queue_per_core
            ):
                raise QueuePressureError("per-Core inference queue is full")
            conversation = (
                request.core.core_id,
                request.core.platform_id,
                request.core.generation,
                request.conversation_id,
            )
            if self._pending(conversation=conversation) >= (
                self.limits.max_pending_per_conversation
            ):
                raise QueuePressureError(
                    "per-conversation inference queue is full"
                )
            self._sequence += 1
            job = _Job(
                request.request_id, request, JobState.QUEUED, moment,
                moment + request.timeout_seconds, self._sequence,
            )
            self._jobs[job.job_id] = job
            self._order.append(job.job_id)
            return job.view()

    def set_active_limit(self, value: int) -> None:
        if type(value) is not int or not 1 <= value <= 8:
            raise ValueError("active limit must be in 1..8")
        with self._lock:
            self._max_active = value

    def _ordered(self) -> list[_Job]:
        jobs = [
            self._jobs[job_id] for job_id in self._order
            if job_id in self._jobs
            and self._jobs[job_id].state in {JobState.QUEUED, JobState.DEFERRED}
        ]
        return sorted(
            jobs,
            key=lambda job: (
                job.request.workload_class.priority,
                self._served.get(job.request.core.core_id, 0),
                job.submitted_at,
                job.sequence,
            ),
        )

    def claim_next(
        self, now: float, activity: ActivityMode,
        gaming: GamingPolicy | None = None,
    ) -> Claim | None:
        moment = _now(now)
        policy = gaming if gaming is not None else GamingPolicy()
        if not isinstance(policy, GamingPolicy):
            raise TypeError("gaming must be GamingPolicy")
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        with self._lock:
            self.expire(moment)
            if self._active >= self._max_active:
                return None
            for job in self._ordered():
                decision = policy.decision(job.request.workload_class, activity)
                if not decision.allowed:
                    job.state = JobState.DEFERRED
                    job.reason = decision.reason
                    continue
                job.state = JobState.IN_FLIGHT
                job.reason = None
                job.holds_slot = True
                job.result_uncertain = False
                self._active += 1
                core_id = job.request.core.core_id
                self._served[core_id] = self._served.get(core_id, 0) + 1
                return Claim(job.job_id, job.request, job.deadline_at)
            return None

    def status(self, job_id: str) -> JobView | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else job.view()

    def _release(self, job: _Job) -> None:
        if job.holds_slot:
            job.holds_slot = False
            self._active = max(0, self._active - 1)

    def expire(self, now: float) -> tuple[str, ...]:
        moment = _now(now)
        changed: list[str] = []
        with self._lock:
            for job_id in self._order:
                job = self._jobs.get(job_id)
                if job is None or job.deadline_at > moment:
                    continue
                if job.state in {JobState.QUEUED, JobState.DEFERRED}:
                    job.state = JobState.EXPIRED
                    job.reason = "queued request deadline expired"
                    changed.append(job_id)
                elif job.state is JobState.IN_FLIGHT:
                    job.state = JobState.TIMED_OUT
                    job.result_uncertain = True
                    job.reason = "in-flight request deadline expired"
                    # Keep the slot: the backend may still be producing.  An
                    # explicit reconciliation decides whether it completed.
                    changed.append(job_id)
        return tuple(changed)

    def complete(self, job_id: str, now: float) -> JobView:
        _ = _now(now)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError("unknown inference job")
            if job.state is not JobState.IN_FLIGHT:
                raise RuntimeError("only an in-flight job can complete")
            job.state = JobState.COMPLETED
            job.result_uncertain = False
            job.reason = None
            self._release(job)
            return job.view()

    def fail(self, job_id: str, now: float, *, uncertain: bool = False) -> JobView:
        _ = _now(now)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError("unknown inference job")
            if job.state not in {JobState.IN_FLIGHT, JobState.TIMED_OUT}:
                raise RuntimeError("only an in-flight or timed-out job can fail")
            if uncertain and job.state is not JobState.TIMED_OUT:
                job.state = JobState.OUTCOME_UNCERTAIN
                job.result_uncertain = True
                job.reason = "backend outcome is uncertain"
                # Keep the slot until an explicit reconciliation decides.
            else:
                job.state = JobState.FAILED
                job.result_uncertain = bool(uncertain)
                job.reason = "backend generation failed"
                self._release(job)
            return job.view()

    def requeue(self, claim: Claim, now: float, reason: str) -> JobView:
        _ = _now(now)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("requeue reason required")
        with self._lock:
            job = self._jobs.get(claim.job_id)
            if job is None or job.state is not JobState.IN_FLIGHT:
                raise RuntimeError("only an in-flight claim can be requeued")
            job.state = JobState.DEFERRED
            job.reason = reason
            self._release(job)
            core_id = job.request.core.core_id
            self._served[core_id] = max(0, self._served.get(core_id, 0) - 1)
            return job.view()

    def cancel(
        self, job_id: str, now: float, *,
        backend_confirmed: bool | None = None,
    ) -> CancelOutcome:
        _ = _now(now)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return CancelOutcome.UNKNOWN_JOB
            if job.state in {JobState.QUEUED, JobState.DEFERRED}:
                job.state = JobState.CANCELLED
                job.reason = "cancelled before dispatch"
                self._release(job)
                return CancelOutcome.CANCELLED
            if job.state is JobState.COMPLETED:
                return CancelOutcome.ALREADY_COMPLETED
            if job.state is JobState.CANCELLED:
                return CancelOutcome.CANCELLED
            if job.state is JobState.IN_FLIGHT:
                if backend_confirmed is True:
                    job.state = JobState.CANCELLED
                    job.reason = "in-flight generation cancellation verified"
                    job.result_uncertain = False
                    self._release(job)
                    return CancelOutcome.CANCELLED
                job.state = JobState.OUTCOME_UNCERTAIN
                job.result_uncertain = True
                job.reason = "in-flight cancellation is not verified"
                return CancelOutcome.OUTCOME_UNCERTAIN
            return CancelOutcome.OUTCOME_UNCERTAIN

    def reconcile(
        self, job_id: str, now: float, *, completed: bool,
    ) -> JobView:
        _ = _now(now)
        if type(completed) is not bool:
            raise TypeError("completed must be bool")
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError("unknown inference job")
            if job.state not in {
                JobState.OUTCOME_UNCERTAIN, JobState.TIMED_OUT,
            }:
                raise RuntimeError("job does not require reconciliation")
            job.state = JobState.COMPLETED if completed else JobState.FAILED
            job.result_uncertain = not completed
            job.reason = (
                "reconciled as completed" if completed
                else "reconciled as failed"
            )
            self._release(job)
            return job.view()

    def snapshot(self) -> SchedulerSnapshot:
        with self._lock:
            counts = {state: 0 for state in JobState}
            per_core: dict[UUID, int] = {}
            for job in self._jobs.values():
                counts[job.state] += 1
                if job.state in {JobState.QUEUED, JobState.DEFERRED}:
                    core_id = job.request.core.core_id
                    per_core[core_id] = per_core.get(core_id, 0) + 1
            return SchedulerSnapshot(
                active=self._active,
                max_active=self._max_active,
                queued=counts[JobState.QUEUED],
                deferred=counts[JobState.DEFERRED],
                in_flight=counts[JobState.IN_FLIGHT],
                completed=counts[JobState.COMPLETED],
                failed=counts[JobState.FAILED],
                cancelled=counts[JobState.CANCELLED],
                timed_out=counts[JobState.TIMED_OUT],
                expired=counts[JobState.EXPIRED],
                outcome_uncertain=counts[JobState.OUTCOME_UNCERTAIN],
                per_core_pending=tuple(sorted(per_core.items())),
            )
