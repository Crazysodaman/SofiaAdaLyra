"""Fair scheduling, budget, queue-pressure and cancellation regressions."""
import pytest

from sofia.platform.inference import (
    BudgetLedger, BudgetWindow, CancelOutcome,
    FairInferenceScheduler, InferenceBudgetPolicy, JobState, ModelResidencyError,
    QueuePressureError, SchedulerLimits, WorkloadClass,
)
from sofia.platform.ops.activity import ActivityMode
from test._shared_inference_support import (
    FakeBackend, build_adapter, budgets, core, request,
)


def test_foreground_owner_priority_beats_earlier_background_social() -> None:
    scheduler = FairInferenceScheduler()
    owner = core(1)
    scheduler.enqueue(
        request(request_id="social", owner=owner,
                workload=WorkloadClass.CORE_SOCIAL), 1_000.0,
    )
    scheduler.enqueue(
        request(request_id="owner", owner=owner,
                workload=WorkloadClass.FOREGROUND_OWNER), 1_000.0,
    )
    claim = scheduler.claim_next(1_000.0, ActivityMode.IDLE)
    assert claim is not None and claim.request.request_id == "owner"
    scheduler.complete(claim.job_id, 1_000.0)
    second = scheduler.claim_next(1_000.0, ActivityMode.IDLE)
    assert second is not None and second.request.request_id == "social"


def test_same_class_work_fairly_round_robins_across_cores() -> None:
    scheduler = FairInferenceScheduler(
        SchedulerLimits(max_queue_per_core=10, max_pending_per_conversation=10),
    )
    first, second = core(1), core(2)
    for index in range(3):
        scheduler.enqueue(
            request(request_id=f"a{index}", owner=first), 1_000.0,
        )
        scheduler.enqueue(
            request(request_id=f"b{index}", owner=second), 1_000.0,
        )
    order = []
    for _ in range(6):
        claim = scheduler.claim_next(1_000.0, ActivityMode.IDLE)
        assert claim is not None
        order.append(claim.request.core.core_id)
        scheduler.complete(claim.job_id, 1_000.0)
    assert order == [
        first.core_id, second.core_id, first.core_id,
        second.core_id, first.core_id, second.core_id,
    ]


def test_per_core_and_per_conversation_request_budgets_are_enforced() -> None:
    ledger = BudgetLedger(InferenceBudgetPolicy(
        BudgetWindow(2, 10_000, 60.0), BudgetWindow(10, 10_000, 60.0),
    ))
    owner = core(1)
    assert ledger.consume(owner, "conv:a", 10, 1_000.0).allowed
    assert ledger.consume(owner, "conv:b", 10, 1_000.0).allowed
    denied = ledger.consume(owner, "conv:c", 10, 1_000.0)
    assert denied.allowed is False
    assert denied.reason == "request budget exhausted"


def test_conversation_output_token_budget_is_enforced() -> None:
    ledger = BudgetLedger(InferenceBudgetPolicy(
        BudgetWindow(10, 10_000, 60.0), BudgetWindow(10, 100, 60.0),
    ))
    owner = core(1)
    assert ledger.consume(owner, "conv:a", 60, 1_000.0).allowed
    denied = ledger.consume(owner, "conv:a", 60, 1_000.0)
    assert denied.allowed is False
    assert denied.reason == "output token budget exhausted"


def test_adapter_returns_budget_denial_instead_of_queueing() -> None:
    adapter = build_adapter(ledger=budgets(core_requests=1))
    accepted = adapter.submit(
        request_id="one", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=request(request_id="unused").messages, max_output_tokens=10,
    )
    denied = adapter.submit(
        request_id="two", core=core(1), conversation_id="conv:other",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=request(request_id="unused").messages, max_output_tokens=10,
    )
    assert accepted.accepted is True
    assert denied.accepted is False
    assert denied.reason == "request budget exhausted"


def test_queue_pressure_is_bounded_per_core_and_conversation() -> None:
    per_core = FairInferenceScheduler(
        SchedulerLimits(max_queue_per_core=1, max_pending_per_conversation=10),
    )
    per_core.enqueue(request(request_id="one", conversation_id="conv:a"), 1_000.0)
    with pytest.raises(QueuePressureError, match="per-Core"):
        per_core.enqueue(
            request(request_id="two", conversation_id="conv:b"), 1_000.0,
        )

    per_conversation = FairInferenceScheduler(
        SchedulerLimits(max_queue_per_core=10, max_pending_per_conversation=1),
    )
    per_conversation.enqueue(
        request(request_id="one", conversation_id="conv:a"), 1_000.0,
    )
    with pytest.raises(QueuePressureError, match="per-conversation"):
        per_conversation.enqueue(
            request(request_id="two", conversation_id="conv:a"), 1_000.0,
        )


def test_queued_deadline_expires_without_dispatch() -> None:
    backend = FakeBackend()
    adapter = build_adapter(backend=backend)
    assert adapter.submit(
        request_id="slow", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=request(request_id="unused").messages,
        max_output_tokens=10, timeout_seconds=10.0,
    ).accepted
    assert adapter.timeouts(now=1_011.0) == ("slow",)
    assert adapter.scheduler.status("slow").state is JobState.EXPIRED
    assert adapter.dispatch_next(now=1_011.0).result is None
    assert backend.calls == []


def test_in_flight_timeout_is_uncertain_and_requires_reconciliation() -> None:
    scheduler = FairInferenceScheduler()
    scheduler.enqueue(request(request_id="inflight", timeout=10.0), 1_000.0)
    claim = scheduler.claim_next(1_000.0, ActivityMode.IDLE)
    assert claim is not None
    assert scheduler.expire(1_011.0) == ("inflight",)
    view = scheduler.status("inflight")
    assert view.state is JobState.TIMED_OUT
    assert view.result_uncertain is True
    assert scheduler.snapshot().active == 1
    reconciled = scheduler.reconcile("inflight", 1_011.0, completed=True)
    assert reconciled.state is JobState.COMPLETED
    assert scheduler.snapshot().active == 0


def test_queued_cancellation_is_verified_immediately() -> None:
    scheduler = FairInferenceScheduler()
    scheduler.enqueue(request(request_id="queued"), 1_000.0)
    assert scheduler.cancel("queued", 1_000.0) is CancelOutcome.CANCELLED
    assert scheduler.status("queued").state is JobState.CANCELLED


def test_unconfirmed_in_flight_cancellation_holds_slot_until_reconciled() -> None:
    scheduler = FairInferenceScheduler()
    scheduler.enqueue(request(request_id="active"), 1_000.0)
    claim = scheduler.claim_next(1_000.0, ActivityMode.IDLE)
    assert claim is not None
    assert scheduler.cancel(
        "active", 1_000.0, backend_confirmed=False,
    ) is CancelOutcome.OUTCOME_UNCERTAIN
    view = scheduler.status("active")
    assert view.state is JobState.OUTCOME_UNCERTAIN
    assert view.result_uncertain is True
    assert scheduler.snapshot().active == 1
    assert scheduler.reconcile(
        "active", 1_000.0, completed=False,
    ).state is JobState.FAILED
    assert scheduler.snapshot().active == 0


def test_confirmed_in_flight_cancellation_releases_the_slot() -> None:
    scheduler = FairInferenceScheduler()
    scheduler.enqueue(request(request_id="active"), 1_000.0)
    assert scheduler.claim_next(1_000.0, ActivityMode.IDLE) is not None
    assert scheduler.cancel(
        "active", 1_000.0, backend_confirmed=True,
    ) is CancelOutcome.CANCELLED
    assert scheduler.status("active").state is JobState.CANCELLED
    assert scheduler.snapshot().active == 0


def test_adapter_cancel_before_dispatch_does_not_contact_backend() -> None:
    backend = FakeBackend()
    adapter = build_adapter(backend=backend)
    adapter.submit(
        request_id="queued", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.CORE_SOCIAL,
        messages=request(request_id="unused").messages, max_output_tokens=10,
    )
    result = adapter.cancel("queued", now=1_000.0)
    assert result.outcome is CancelOutcome.CANCELLED
    assert result.job_state is JobState.CANCELLED
    assert backend.cancelled == []


def test_background_deferral_resumes_when_gaming_ends() -> None:
    scheduler = FairInferenceScheduler()
    scheduler.enqueue(
        request(request_id="social", workload=WorkloadClass.CORE_SOCIAL),
        1_000.0,
    )
    assert scheduler.claim_next(1_000.0, ActivityMode.GAMING) is None
    assert scheduler.status("social").state is JobState.DEFERRED
    claim = scheduler.claim_next(1_000.0, ActivityMode.NORMAL)
    assert claim is not None and claim.request.request_id == "social"


def test_backend_failure_is_uncertain_until_reconciled() -> None:
    backend = FakeBackend(fail=True)
    adapter = build_adapter(backend=backend)
    adapter.submit(
        request_id="uncertain", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=request(request_id="unused").messages, max_output_tokens=10,
    )
    with pytest.raises(ModelResidencyError, match="uncertain"):
        adapter.dispatch_next(now=1_000.0)
    snapshot = adapter.scheduler.snapshot()
    assert snapshot.outcome_uncertain == 1
    assert snapshot.active == 1
    adapter.reconcile("uncertain", completed=False, now=1_000.0)
    assert adapter.scheduler.status("uncertain").state is JobState.FAILED
    assert adapter.scheduler.snapshot().active == 0
