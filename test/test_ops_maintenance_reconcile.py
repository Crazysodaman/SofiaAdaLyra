from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.ops.fleet import FleetRegistry
from sofia.ops.maintenance import (
    MaintenanceOperation,
    MaintenancePolicy,
    MaintenanceRequest,
)
from sofia.ops.model import FleetHost, HostLifecycle
from sofia.ops.reconcile import (
    MaintenanceExecutionResult,
    MaintenanceReceiptOutcome,
    MaintenanceReceiptStore,
    MaintenanceReconcileError,
    MaintenanceReconciler,
    MaintenanceReplayDenied,
    MaintenanceVerification,
)


NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


def registry() -> FleetRegistry:
    result = FleetRegistry()
    result.register_candidate(
        FleetHost(
            host_id="artemis",
            platform="windows",
            architecture="amd64",
            lifecycle=HostLifecycle.CANDIDATE,
            trusted=False,
        )
    )
    result.authenticate_candidate("artemis", __import__("uuid").uuid4())
    result.transition("artemis", HostLifecycle.ENROLLED)
    result.transition("artemis", HostLifecycle.HEALTHY)
    return result


class Backend:
    def __init__(self, *, success=True, raises=False):
        self.success = success
        self.raises = raises
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        if self.raises:
            raise RuntimeError("transport outcome unknown")
        return MaintenanceExecutionResult(
            request_id=request.request_id,
            reported_success=self.success,
            execution_ref=f"remote:{request.request_id}",
            message="reported success" if self.success else "reported failure",
        )


class Verifier:
    def __init__(self, *, verified=True):
        self.verified = verified
        self.calls = []

    def verify(self, request):
        self.calls.append(request)
        return MaintenanceVerification(
            request_id=request.request_id,
            verified=self.verified,
            evidence_ref=f"verify:{request.request_id}",
            observed=(
                "target state observed"
                if self.verified
                else "target state not observed"
            ),
        )


def request(*, request_id="maint-1", authorized=True):
    return MaintenanceRequest(
        request_id=request_id,
        host_id="artemis",
        operation=MaintenanceOperation.SERVICE_RESTART,
        target="SofiaAdaLyra",
        authorized=authorized,
    )


def reconciler(tmp_path, *, backend=None, verifier=None):
    reg = registry()
    receipts = MaintenanceReceiptStore(tmp_path / "sofia.db")
    return (
        MaintenanceReconciler(
            policy=MaintenancePolicy(reg),
            backend=backend or Backend(),
            verifier=verifier or Verifier(),
            receipts=receipts,
        ),
        receipts,
    )


def test_authorized_maintenance_requires_independent_verification(tmp_path):
    service, receipts = reconciler(tmp_path)

    receipt = service.reconcile(request(), now=NOW)

    assert receipt.outcome is MaintenanceReceiptOutcome.VERIFIED
    assert receipt.execution_ref == "remote:maint-1"
    assert receipt.verification_ref == "verify:maint-1"
    assert receipts.get("maint-1") == receipt


def test_backend_reported_failure_is_receipted_without_verification(tmp_path):
    backend = Backend(success=False)
    verifier = Verifier()
    service, receipts = reconciler(
        tmp_path,
        backend=backend,
        verifier=verifier,
    )

    receipt = service.reconcile(request(), now=NOW)

    assert receipt.outcome is MaintenanceReceiptOutcome.EXECUTION_FAILED
    assert verifier.calls == []
    assert receipts.get("maint-1") == receipt


def test_verification_failure_never_becomes_success(tmp_path):
    verifier = Verifier(verified=False)
    service, receipts = reconciler(tmp_path, verifier=verifier)

    receipt = service.reconcile(request(), now=NOW)

    assert receipt.outcome is MaintenanceReceiptOutcome.VERIFICATION_FAILED
    assert "not observed" in receipt.observed
    assert receipts.get("maint-1") == receipt


def test_uncertain_execution_is_receipted_and_cannot_retry(tmp_path):
    backend = Backend(raises=True)
    service, receipts = reconciler(tmp_path, backend=backend)

    with pytest.raises(MaintenanceReconcileError, match="do not retry"):
        service.reconcile(request(), now=NOW)

    saved = receipts.get("maint-1")
    assert saved is not None
    assert saved.outcome is MaintenanceReceiptOutcome.UNCERTAIN

    with pytest.raises(MaintenanceReplayDenied):
        service.reconcile(request(), now=NOW)
    assert len(backend.calls) == 1


def test_unauthorized_request_fails_before_execution_or_receipt(tmp_path):
    backend = Backend()
    service, receipts = reconciler(tmp_path, backend=backend)

    with pytest.raises(PermissionError, match="explicit authority"):
        service.reconcile(request(authorized=False), now=NOW)

    assert backend.calls == []
    assert receipts.get("maint-1") is None
