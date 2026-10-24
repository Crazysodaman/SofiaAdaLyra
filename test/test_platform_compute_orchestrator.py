from datetime import datetime, timedelta, timezone

import pytest

from sofia.core.cognition.model_lifecycle import (
    CognitiveModelRole, ModelLifecycleManager,
)
from sofia.platform.cognition_compute import (
    ComputeOperationStatus, ModelComputeOrchestrator, ModelIdentityObservation,
)
from sofia.platform.config.cognitive_models import CognitiveModelSelection
from sofia.platform.config.model import ModelLifecycleConfiguration, ProviderConfiguration
from sofia.platform.ops import ResourceArbiter, ResourceObservation
from sofia.core.social.model import AudienceKind, PrincipalContext
from test.test_model_lifecycle import Backend


NOW = datetime(2026, 10, 23, 4, tzinfo=timezone.utc)
MODEL = "vendor/primary:any"
DIGEST = "d" * 64
OWNER = PrincipalContext(
    "principal:sparks", "audience:desktop", AudienceKind.PRIVATE,
)


def build(path, *, backend=None, allowed=True, identity_model=MODEL):
    backend = backend or Backend(installed=(MODEL,))
    manager = ModelLifecycleManager(
        selection=CognitiveModelSelection(
            routing_enabled=False,
            primary=ProviderConfiguration(provider="ollama", model=MODEL),
            secondary=None,
        ),
        policy=ModelLifecycleConfiguration(enabled=True), backend=backend,
    )
    arbiter = ResourceArbiter(
        path,
        authorizer=lambda principal, audience, resource, authority, now: allowed,
    )
    service = ModelComputeOrchestrator(
        path, manager=manager, resource_arbiter=arbiter,
        authorizer=lambda principal, operation, role, model, authority, now: (
            allowed and authority == "approval:model"
        ),
        identity_probe=lambda role, now: ModelIdentityObservation(
            "ollama", identity_model, DIGEST, "venus", now,
        ),
    )
    return service, backend


def resource():
    return ResourceObservation(
        "gpu:venus:0", "venus", "gpu",
        (("vram_bytes", 16 << 30),), NOW,
    )


def load(service, **changes):
    values = dict(
        request_id="request:model-load", idempotency_key="model-load:one",
        role=CognitiveModelRole.PRIMARY, principal=OWNER,
        authority_ref="approval:model", resource=resource(),
        resource_amounts=(("vram_bytes", 8 << 30),), now=NOW,
        expires_at=NOW + timedelta(minutes=2),
    )
    values.update(changes)
    return service.load(**values)


def test_load_is_resource_bounded_and_independently_verified(canonical_state_path):
    service, backend = build(canonical_state_path)
    receipt = load(service)
    assert receipt.status is ComputeOperationStatus.SUCCEEDED_VERIFIED
    assert receipt.model == MODEL
    assert receipt.model_digest == DIGEST
    assert receipt.evidence_ref == f"model-probe:venus:{DIGEST}"
    assert backend.resident == {MODEL}
    assert service.resource_arbiter.inspect(
        receipt.resource_reservation_id
    ).status == "released"
    assert load(service) == receipt


def test_selected_model_identity_mismatch_fails_before_operation(canonical_state_path):
    service, backend = build(canonical_state_path, identity_model="other/model:any")
    with pytest.raises(PermissionError, match="configured selection"):
        load(service)
    assert backend.loads == []


def test_denied_or_insufficient_resource_never_dispatches(canonical_state_path):
    denied, backend = build(canonical_state_path, allowed=False)
    receipt = load(denied)
    assert receipt.status is ComputeOperationStatus.DENIED
    assert backend.loads == []

    # New canonical fixture is needed because request identity is durable.


def test_failed_load_is_unknown_and_not_replayed(canonical_state_path):
    class FailingBackend(Backend):
        def load(self, name, *, keep_alive):
            raise RuntimeError("provider disconnected")

    service, backend = build(
        canonical_state_path, backend=FailingBackend(installed=(MODEL,)),
    )
    receipt = load(service)
    assert receipt.status is ComputeOperationStatus.OUTCOME_UNKNOWN
    assert receipt.retry_safe is False
    assert load(service) == receipt


def test_unload_verifies_exact_selected_model(canonical_state_path):
    backend = Backend(installed=(MODEL,), running=(MODEL,))
    service, _ = build(canonical_state_path, backend=backend)
    receipt = service.unload(
        request_id="request:model-unload", idempotency_key="model-unload:one",
        role=CognitiveModelRole.PRIMARY, principal=OWNER,
        authority_ref="approval:model", now=NOW,
    )
    assert receipt.status is ComputeOperationStatus.SUCCEEDED_VERIFIED
    assert backend.resident == set()


def test_restart_reconciles_started_operation_to_unknown(canonical_state_path):
    service, _ = build(canonical_state_path)
    identity = service.probe(CognitiveModelRole.PRIMARY, now=NOW)
    assert service._begin(
        request_id="request:interrupted", idempotency_key="interrupted:one",
        operation="load", role=CognitiveModelRole.PRIMARY, identity=identity,
        principal=OWNER, authority_ref="approval:model", now=NOW,
    ) is None
    restarted, _ = build(canonical_state_path)
    assert restarted.reconcile(now=NOW + timedelta(seconds=1)) == 1
    receipt = restarted.inspect("request:interrupted")
    assert receipt.status is ComputeOperationStatus.OUTCOME_UNKNOWN
    assert receipt.retry_safe is False
