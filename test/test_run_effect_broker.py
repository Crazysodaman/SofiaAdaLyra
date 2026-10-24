from datetime import datetime, timedelta, timezone
from threading import Event

import pytest

from sofia.platform.capability import Capability, CapabilityGateway, CapabilityProposal, CapabilitySystem
from sofia.platform.run import (
    DurableWorkStore,
    EffectBroker,
    EffectRequest,
    EffectStatus,
    WorkStatus,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.core.social.model import AudienceKind, PrincipalContext


NOW = datetime.now(timezone.utc)
OWNER = PrincipalContext(
    "principal:sparks", "audience:desktop-private", AudienceKind.PRIVATE,
)


def make_broker(path, handler, *, principal_ok=True, effect_verifier=None):
    system = CapabilitySystem(authorization_checker=lambda request: True)
    system.register(Capability("test.effect", "test effect"), handler)
    broker = EffectBroker(
        state_path=path,
        work_store=DurableWorkStore(path),
        gateway=CapabilityGateway(system),
        operator_stop=OperatorStopStore(path),
        principal_verifier=lambda principal, ref, now: principal_ok and ref == "session:valid",
        effect_verifier=effect_verifier,
    )
    return broker


def request(*, key="key-1", value="one", request_id="request:1"):
    return EffectRequest(
        request_id=request_id,
        idempotency_key=key,
        principal=OWNER,
        principal_attestation_ref="session:valid",
        proposal=CapabilityProposal(
            "test.effect", {"value": value}, "test exact effect",
            requested_scope={"target": "fixture"},
        ),
        expected_effect="fixture updated",
        expires_at=NOW + timedelta(hours=1),
        correlation_id="correlation:1",
        risk="isolated_change",
    )


def test_idempotent_submission_returns_one_canonical_run_job(canonical_state_path):
    broker = make_broker(canonical_state_path, lambda request: {"ok": True})
    first = broker.submit(request(), now=NOW)
    second = broker.submit(request(), now=NOW + timedelta(seconds=1))
    assert first.job_id == second.job_id
    assert len(broker.work_store.list()) == 1


def test_reused_idempotency_key_cannot_change_effect(canonical_state_path):
    broker = make_broker(canonical_state_path, lambda request: {"ok": True})
    broker.submit(request(), now=NOW)
    with pytest.raises(RuntimeError, match="idempotency"):
        broker.submit(
            request(value="different", request_id="request:2"),
            now=NOW + timedelta(seconds=1),
        )
    assert len(broker.work_store.list()) == 1


def test_principal_is_reverified_immediately_before_execution(canonical_state_path):
    called = []
    broker = make_broker(
        canonical_state_path, lambda capability_request: called.append(True),
        principal_ok=False,
    )
    job = broker.submit(request(), now=NOW)
    result = broker.handler(job, Event())
    assert result.status is WorkStatus.FAILED
    assert called == []
    assert broker.inspect("request:1").status is EffectStatus.DENIED


def test_operator_stop_denies_before_capability_dispatch(canonical_state_path):
    called = []
    broker = make_broker(
        canonical_state_path, lambda capability_request: called.append(True),
    )
    broker.operator_stop.set(
        active=True, updated_by="Sparks", reason="test stop", at=NOW,
    )
    job = broker.submit(request(), now=NOW)
    broker.handler(job, Event())
    assert called == []
    receipt = broker.inspect("request:1")
    assert receipt.status is EffectStatus.DENIED
    assert receipt.error_class == "operator_stop"


def test_reported_success_is_not_verified_without_independent_check(canonical_state_path):
    broker = make_broker(canonical_state_path, lambda capability_request: {"ok": True})
    job = broker.submit(request(), now=NOW)
    result = broker.handler(job, Event())
    assert result.status is WorkStatus.FAILED
    assert broker.inspect("request:1").status is EffectStatus.SUCCEEDED_REPORTED_UNVERIFIED


def test_independent_effect_verification_completes_job(canonical_state_path):
    broker = make_broker(
        canonical_state_path,
        lambda capability_request: {"receipt": "actual"},
        effect_verifier=lambda effect_request, evidence: (
            evidence == {"receipt": "actual"}, "evidence:actual",
        ),
    )
    job = broker.submit(request(), now=NOW)
    result = broker.handler(job, Event())
    receipt = broker.inspect("request:1")
    assert result.status is WorkStatus.COMPLETED
    assert receipt.status is EffectStatus.SUCCEEDED_VERIFIED
    assert receipt.evidence_ref == "evidence:actual"


def test_handler_failure_is_outcome_unknown_and_not_retry_safe(canonical_state_path):
    def fail(_request):
        raise RuntimeError("network failed after dispatch")

    broker = make_broker(canonical_state_path, fail)
    job = broker.submit(request(), now=NOW)
    result = broker.handler(job, Event())
    receipt = broker.inspect("request:1")
    assert result.status is WorkStatus.UNCERTAIN
    assert receipt.status is EffectStatus.OUTCOME_UNKNOWN
    assert receipt.retry_safe is False


def test_cancellation_before_dispatch_is_definitive_and_has_no_effect(
    canonical_state_path,
):
    called = []
    broker = make_broker(
        canonical_state_path, lambda capability_request: called.append(True),
    )
    job = broker.submit(request(), now=NOW)
    cancel = Event()
    cancel.set()
    result = broker.handler(job, cancel)
    assert result.status is WorkStatus.FAILED
    assert broker.inspect("request:1").status is EffectStatus.CANCELLED
    assert called == []


def test_cancellation_after_dispatch_is_unknown_not_cancelled(canonical_state_path):
    cancel = Event()
    def effect(_request):
        cancel.set()
        return {"reported": True}
    broker = make_broker(canonical_state_path, effect)
    job = broker.submit(request(), now=NOW)
    result = broker.handler(job, cancel)
    receipt = broker.inspect("request:1")
    assert result.status is WorkStatus.UNCERTAIN
    assert receipt.status is EffectStatus.OUTCOME_UNKNOWN
    assert receipt.retry_safe is False


def test_restart_reconciliation_records_unknown_without_replay(canonical_state_path):
    called = []
    broker = make_broker(
        canonical_state_path, lambda capability_request: called.append(True),
    )
    job = broker.submit(request(), now=NOW)
    broker.work_store.transition(
        job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.RUNNING,
        reason="dispatched", now=NOW, increment_attempt=True,
    )
    assert broker.reconcile(now=NOW + timedelta(seconds=1)) == 1
    receipt = broker.inspect("request:1")
    assert receipt.status is EffectStatus.OUTCOME_UNKNOWN
    assert receipt.retry_safe is False
    assert called == []
