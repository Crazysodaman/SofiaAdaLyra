"""Canonical module-lifecycle and Fleet mutation backends bound to the dispatcher."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.capability import CapabilitySystem
from sofia.platform.modules import ModuleLifecycle
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.run.management_mutation import (
    MANAGEMENT_MUTATION_CAPABILITY, ManagementMutationDispatcher,
    MutationRegistry,
)
from sofia.platform.run.management_mutation_backends import (
    FLEET_DECOMMISSION_OPERATION, FLEET_ENROLL_OPERATION, FLEET_SCOPE,
    MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE,
    fleet_mutation_registry, module_lifecycle_mutation_registry,
)
from sofia.platform.run.management_mutation_store import ManagementMutationReceiptStore
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    UntrustedManagementMutation, mutation_approval_parameters,
)
from test.fleet_state_fixture import register_fixture_candidate
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_module_lifecycle_v1 import verified_package
from test.test_ops_fleet_discovery_permissions import _ready_fleet_candidate

PLATFORM = "platform:alpha"
PEER = "unix:uid:1000:gid:1000"
OTHER_PEER = "unix:uid:2000:gid:2000"
GENERATION = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _request(
    operation: str,
    scope: str,
    payload: dict,
    *,
    now: datetime,
    idempotency_key: str,
    approval_id: str = "approval:pending",
    expected_generation: int = GENERATION,
    expected_revision: int = 0,
) -> dict:
    return {
        "schema": MANAGEMENT_MUTATION_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": "request:" + uuid4().hex,
        "correlation_id": "correlation:" + uuid4().hex,
        "idempotency_key": idempotency_key,
        "target_platform_id": PLATFORM,
        "operation": operation,
        "operation_scope": scope,
        "expected_generation": expected_generation,
        "expected_revision": expected_revision,
        "deadline": (now + timedelta(seconds=5)).isoformat().replace(
            "+00:00", "Z"
        ),
        "approval_id": approval_id,
        "payload": payload,
    }


def _record_exact_approval(
    state_path, *, capability: str, parameters: dict, now: datetime,
    approved_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> str:
    approved = approved_at or now
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=capability,
        request_fingerprint=execution_fingerprint(capability, parameters),
        approved_by="Sparks",
        approved_at=approved,
        expires_at=expires_at or (approved + timedelta(minutes=5)),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(state_path), approval,
    )
    return approval.approval_id


def _record_management_approval(
    state_path, document: dict, *, now: datetime, peer: str = PEER,
) -> str:
    typed = UntrustedManagementMutation.from_payload(document, now=now)
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        request_fingerprint=execution_fingerprint(
            MANAGEMENT_MUTATION_CAPABILITY,
            mutation_approval_parameters(typed, peer),
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(state_path), approval,
    )
    return approval.approval_id


def _status(stop: OperatorStopStore) -> dict:
    return {
        "platform_id": PLATFORM,
        "generation": GENERATION,
        "operator_stop": stop.current().active,
    }


def _dispatcher(
    state_path, registry: MutationRegistry, stop: OperatorStopStore,
) -> ManagementMutationDispatcher:
    return ManagementMutationDispatcher(
        current_status=lambda: _status(stop),
        registry=registry,
        approvals=ExecutionApprovalVerifier(state_path),
        receipts=ManagementMutationReceiptStore(state_path),
        clock=_now,
    )


def _wire(document: dict) -> bytes:
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


@pytest.fixture
def module_runtime(canonical_state_path, tmp_path):
    state = canonical_state_path
    stop = OperatorStopStore(state)
    service = ModuleLifecycleCommandService(
        state_path=state,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(
            authorization_checker=lambda request: True
        ),
    )
    package = verified_package(tmp_path)
    found = service.discover(package, now=_now())
    return state, stop, service, found


def _module_payload(found, *, operation: str, approval_ref: str,
                    expected_revision: int | None = None) -> dict:
    return {
        "operation": operation,
        "module_id": found.module_id,
        "expected_module_revision": (
            found.revision if expected_revision is None else expected_revision
        ),
        "package_digest": found.package_digest,
        "approval_ref": approval_ref,
    }


def _module_approval(state_path, found, *, operation: str, target,
                     now: datetime, approved_at: datetime | None = None,
                     expires_at: datetime | None = None) -> str:
    parameters = {
        "module_id": found.module_id,
        "version": found.version,
        "package_digest": found.package_digest,
        "expected_revision": found.revision,
        "target_lifecycle": target.value,
        "profile": None,
    }
    return _record_exact_approval(
        state_path, capability=f"module.{operation}",
        parameters=parameters, now=now,
        approved_at=approved_at, expires_at=expires_at,
    )


def test_authorized_module_mutation_approves_exact_record(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    approval_ref = _module_approval(
        state, found, operation="approve",
        target=ModuleLifecycle.APPROVED, now=now,
    )
    payload = _module_payload(
        found, operation="approve", approval_ref=approval_ref,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-approve",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "SUCCEEDED"
    assert reply["error_code"] is None
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.APPROVED


def test_unsupported_module_operation_fails_closed_as_denied(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="stage", approval_ref="approval:unused",
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-stage",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "UNSUPPORTED_OPERATION"
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED


def test_stale_module_revision_is_denied_before_owner_approval(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="approve", approval_ref="approval:unused",
        expected_revision=found.revision + 5,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-stale",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STALE_REVISION"
    assert service.describe(found.module_id).revision == found.revision


def test_missing_module_record_fails_closed_as_evidence_unavailable(
    module_runtime,
):
    state, stop, service, _found = module_runtime
    now = _now()
    payload = {
        "operation": "approve",
        "module_id": "org.example.missing",
        "expected_module_revision": 1,
        "package_digest": "0" * 64,
        "approval_ref": "approval:unused",
    }
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-missing-record",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "EVIDENCE_UNAVAILABLE"


def test_missing_module_approval_is_denied_without_effect(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="approve",
        approval_ref="approval:" + uuid4().hex,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-missing-approval",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED


def test_expired_module_approval_is_denied_without_effect(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    approval_ref = _module_approval(
        state, found, operation="approve",
        target=ModuleLifecycle.APPROVED, now=now,
        approved_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
    )
    payload = _module_payload(
        found, operation="approve", approval_ref=approval_ref,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-expired-approval",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED


def test_operator_stop_denies_module_mutation_before_consumption(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    approval_ref = _module_approval(
        state, found, operation="approve",
        target=ModuleLifecycle.APPROVED, now=now,
    )
    payload = _module_payload(
        found, operation="approve", approval_ref=approval_ref,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-stop",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    stop.set(
        active=True, updated_by="Sparks", reason="pause all mutations", at=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STOPPED"
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED
    typed = UntrustedManagementMutation.from_payload(document, now=now)
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=document["approval_id"],
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        parameters=mutation_approval_parameters(typed, PEER),
        now=now,
    )


@pytest.mark.parametrize("changes,expected", [
    ({"expected_generation": GENERATION - 1}, "STALE_GENERATION"),
    ({"expected_revision": 4}, "STALE_REVISION"),
])
def test_module_mutation_rejects_stale_platform_state(
    module_runtime, changes, expected,
):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="approve", approval_ref="approval:unused",
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-" + expected,
        **changes,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == expected
    assert service.describe(found.module_id).revision == found.revision


def test_wrong_peer_cannot_spend_module_mutation_approval(module_runtime):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="approve", approval_ref="approval:unused",
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-wrong-peer",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=OTHER_PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_MISMATCH"
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED


def test_unknown_wire_operation_is_denied(module_runtime):
    state, stop, service, _found = module_runtime
    now = _now()
    document = _request(
        "platform.module.unknown", MODULE_LIFECYCLE_SCOPE, {},
        now=now, idempotency_key="idempotency:module-unknown",
    )
    reply = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "UNKNOWN_OPERATION"


def test_module_mutation_replay_returns_the_durable_receipt(
    module_runtime,
):
    state, stop, service, found = module_runtime
    now = _now()
    approval_ref = _module_approval(
        state, found, operation="approve",
        target=ModuleLifecycle.APPROVED, now=now,
    )
    payload = _module_payload(
        found, operation="approve", approval_ref=approval_ref,
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-replay",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    dispatcher = _dispatcher(
        state, module_lifecycle_mutation_registry(service), stop,
    )
    wire = _wire(document)
    first = dispatcher.dispatch(wire, authenticated_peer=PEER, now=now)
    after_first = service.describe(found.module_id).revision
    replay = dispatcher.dispatch(wire, authenticated_peer=PEER, now=now)

    assert first["outcome"] == "SUCCEEDED"
    assert replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == first["receipt_id"]
    assert service.describe(found.module_id).revision == after_first
    assert replay["current_revision"] == first["current_revision"]


def test_module_handler_failure_is_outcome_unknown(
    module_runtime, monkeypatch,
):
    state, stop, service, found = module_runtime
    now = _now()
    payload = _module_payload(
        found, operation="approve", approval_ref="approval:unused",
    )
    document = _request(
        MODULE_LIFECYCLE_OPERATION, MODULE_LIFECYCLE_SCOPE, payload,
        now=now, idempotency_key="idempotency:module-handler-failure",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    registry = module_lifecycle_mutation_registry(service)
    monkeypatch.setattr(
        service, "approve",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated canonical handler crash")
        ),
    )
    reply = _dispatcher(state, registry, stop).dispatch(
        _wire(document), authenticated_peer=PEER, now=now,
    )

    assert reply["outcome"] == "OUTCOME_UNKNOWN"
    assert reply["error_code"] == "HANDLER_FAILED_UNKNOWN"
    assert reply["current_revision"] == 1


@pytest.fixture
def fleet_runtime(canonical_state_path):
    state = canonical_state_path
    service = OpsToolService(state)
    observed = _ready_fleet_candidate(service)
    stop = OperatorStopStore(state)
    return state, stop, service, observed


def _fleet_candidate(service) -> tuple[str, str]:
    evidence = service.enrollment_evidence("worker")
    assert evidence is not None and evidence["ready"] is True
    return evidence["node_id"], evidence["public_key_sha256"]


def _fleet_parameters(node_id, key: str) -> dict:
    return {
        "host_id": "worker",
        "node_id": str(node_id),
        "public_key_sha256": key,
        "endpoint_hostname": "worker.lan",
        "endpoint_port": 7443,
    }


def test_authorized_fleet_enroll_mutation_uses_canonical_evidence(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    parameters = _fleet_parameters(node_id, key)
    approval_ref = _record_exact_approval(
        state, capability="fleet.enroll", parameters=parameters, now=now,
    )
    payload = {**parameters, "approval_ref": approval_ref}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-enroll",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    dispatcher = _dispatcher(state, fleet_mutation_registry(service), stop)
    wire = _wire(document)
    reply = dispatcher.dispatch(wire, authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "SUCCEEDED"
    assert service.host("worker")["trusted"] is True
    assert service.host("worker")["lifecycle"] == HostLifecycle.ENROLLED.value

    replay = dispatcher.dispatch(wire, authenticated_peer=PEER, now=now)
    assert replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == reply["receipt_id"]


def test_fleet_enroll_rejects_self_asserted_peer_identity(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    forged = {**_fleet_parameters(node_id, key),
              "node_id": str(uuid4())}
    payload = {**forged, "approval_ref": "approval:unused"}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-forged-peer",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.host("worker")["trusted"] is False


def test_fleet_enroll_missing_approval_creates_no_trust(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    parameters = _fleet_parameters(node_id, key)
    payload = {**parameters, "approval_ref": "approval:" + uuid4().hex}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-missing-approval",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.host("worker")["trusted"] is False


def test_fleet_enroll_expired_approval_creates_no_trust(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    parameters = _fleet_parameters(node_id, key)
    approval_ref = _record_exact_approval(
        state, capability="fleet.enroll", parameters=parameters, now=now,
        approved_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
    )
    payload = {**parameters, "approval_ref": approval_ref}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-expired-approval",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.host("worker")["trusted"] is False


def test_fleet_enroll_revoked_owner_proof_creates_no_trust(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    parameters = _fleet_parameters(node_id, key)
    approval_ref = _record_exact_approval(
        state, capability="fleet.enroll", parameters=parameters, now=now,
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (now.isoformat(),),
        )
        db.commit()
    payload = {**parameters, "approval_ref": approval_ref}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-revoked-approval",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.host("worker")["trusted"] is False


def test_operator_stop_denies_fleet_enroll(fleet_runtime):
    state, stop, service, _observed = fleet_runtime
    now = _now()
    node_id, key = _fleet_candidate(service)
    parameters = _fleet_parameters(node_id, key)
    payload = {**parameters, "approval_ref": "approval:unused"}
    document = _request(
        FLEET_ENROLL_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-stop",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    stop.set(
        active=True, updated_by="Sparks", reason="pause all mutations", at=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STOPPED"
    assert service.host("worker")["trusted"] is False


@pytest.fixture
def removal_runtime(canonical_state_path):
    state = canonical_state_path
    service = OpsToolService(state)
    register_fixture_candidate(service.registry, FleetHost(
        "worker", "linux", "x86_64", HostLifecycle.CANDIDATE, True,
    ))
    for lifecycle in (
        HostLifecycle.ENROLLED, HostLifecycle.HEALTHY, HostLifecycle.DRAINING,
    ):
        service.registry.transition("worker", lifecycle)
    stop = OperatorStopStore(state)
    return state, stop, service


def test_authorized_fleet_decommission_uses_canonical_removal_authority(
    removal_runtime,
):
    state, stop, service = removal_runtime
    now = _now()
    parameters = service.registry.removal_parameters(
        "worker", proposal_revision="proposal:one",
    )
    approval_ref = _record_exact_approval(
        state, capability="fleet.decommission", parameters=parameters, now=now,
    )
    payload = {
        "host_id": "worker",
        "proposal_revision": "proposal:one",
        "approval_ref": approval_ref,
    }
    document = _request(
        FLEET_DECOMMISSION_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-decommission",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "SUCCEEDED"
    removed = service.registry.host("worker")
    assert removed.lifecycle is HostLifecycle.DECOMMISSIONED
    assert removed.trusted is False


def test_fleet_decommission_missing_approval_preserves_membership(
    removal_runtime,
):
    state, stop, service = removal_runtime
    now = _now()
    payload = {
        "host_id": "worker",
        "proposal_revision": "proposal:one",
        "approval_ref": "approval:" + uuid4().hex,
    }
    document = _request(
        FLEET_DECOMMISSION_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-decommission-missing",
    )
    document["approval_id"] = _record_management_approval(
        state, document, now=now,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "NOT_PERMITTED"
    assert service.registry.host("worker").lifecycle is HostLifecycle.DRAINING


@pytest.mark.parametrize("changes,expected", [
    ({"expected_generation": GENERATION - 1}, "STALE_GENERATION"),
    ({"expected_revision": 3}, "STALE_REVISION"),
])
def test_fleet_decommission_rejects_stale_platform_state(
    removal_runtime, changes, expected,
):
    state, stop, service = removal_runtime
    now = _now()
    payload = {
        "host_id": "worker",
        "proposal_revision": "proposal:one",
        "approval_ref": "approval:unused",
    }
    document = _request(
        FLEET_DECOMMISSION_OPERATION, FLEET_SCOPE, payload,
        now=now, idempotency_key="idempotency:fleet-" + expected,
        **changes,
    )
    reply = _dispatcher(
        state, fleet_mutation_registry(service), stop,
    ).dispatch(_wire(document), authenticated_peer=PEER, now=now)

    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == expected
    assert service.registry.host("worker").lifecycle is HostLifecycle.DRAINING
