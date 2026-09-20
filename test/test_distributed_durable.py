"""22I offline persistence tests. Fake transport is NOT network authentication."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capabilities import CapabilityInventory, RemoteCapability
from sofia.distributed.durable import (
    DurableDistributedGateway, DurableRemoteAuthorization, DurableRemoteLedger,
)
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.model import DistributedNode
from sofia.distributed.operations import (
    RemoteOperationDenied, RemoteOperationRequest, RemoteOperationResult,
    RemoteOperationUncertain, RemoteOutcome, RemoteTransport,
)

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


class FakeTransport(RemoteTransport):
    """Strictly local mock; authenticate here is NOT peer-key possession."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.calls = []
        self.fail = False
        self.authenticated = True

    def authenticate(self, enrollment):
        self.calls.append("authenticate")
        return self.authenticated

    def discover(self, enrollment):
        self.calls.append("discover")
        return CapabilityInventory(
            self.node_id, NOW,
            (RemoteCapability("system.inspect", ("summary",)),), "mock only")

    def execute(self, enrollment, request):
        self.calls.append("execute")
        if self.fail:
            raise TimeoutError("execution outcome unknown")
        return RemoteOperationResult(
            request.request_id, request.node_id,
            RemoteOutcome.REPORTED_SUCCESS, "mock report")


def setup(tmp_path):
    database = tmp_path / "state.sqlite3"
    node = DistributedNode(uuid4(), "Artemis")
    enrollment = NodeEnrollment(
        node, fingerprint_public_key(b"fake-public-key"), NOW, "Sparks")
    request = RemoteOperationRequest(uuid4(), node.node_id, uuid4(),
                                     "system.inspect", "summary", {})
    authorization = DurableRemoteAuthorization(database)
    ledger = DurableRemoteLedger(database)
    transport = FakeTransport(node.node_id)
    gateway = DurableDistributedGateway(
        transport, authorization, ledger, max_inventory_age=timedelta(minutes=1))
    return database, enrollment, request, authorization, ledger, transport, gateway


def grant_for(request, *, expiry=NOW + timedelta(days=30)):
    return RemoteGrant(request.grant_id, request.node_id, request.capability,
                       request.operation, "Sparks", expiry)


def test_default_deny_is_durable_and_never_touches_transport(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    with pytest.raises(RemoteOperationDenied, match="grant"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls == []
    assert ledger.status(request.request_id) == "denied"
    auth.close()
    ledger.close()
    auth2 = DurableRemoteAuthorization(database)
    ledger2 = DurableRemoteLedger(database)
    assert not auth2.permits(request.grant_id, node_id=request.node_id,
                             capability=request.capability, operation=request.operation,
                             now=NOW)
    assert ledger2.status(request.request_id) == "denied"
    auth2.close()
    ledger2.close()


def test_standing_grant_survives_restart_and_exact_scope_is_required(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    auth.close()
    ledger.close()
    auth = DurableRemoteAuthorization(database)
    assert auth.permits(request.grant_id, node_id=request.node_id,
                        capability="system.inspect", operation="summary", now=NOW)
    assert not auth.permits(request.grant_id, node_id=request.node_id,
                            capability="system.inspect", operation="restart", now=NOW)
    assert not auth.permits(request.grant_id, node_id=uuid4(),
                            capability="system.inspect", operation="summary", now=NOW)
    assert not auth.permits(request.grant_id, node_id=request.node_id,
                            capability="system.inspect", operation="summary",
                            now=NOW + timedelta(days=31))
    with pytest.raises(ValueError, match="already exists"):
        auth.add_approved_grant(grant_for(request))
    auth.revoke(request.grant_id)
    auth.close()
    auth = DurableRemoteAuthorization(database)
    assert not auth.permits(request.grant_id, node_id=request.node_id,
                            capability="system.inspect", operation="summary", now=NOW)
    with pytest.raises(ValueError, match="already exists"):
        auth.add_approved_grant(grant_for(request))
    auth.close()


def test_authenticated_mock_report_persists_and_replay_denied_after_restart(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    assert gateway.invoke(enrollment, request, now=NOW).outcome is RemoteOutcome.REPORTED_SUCCESS
    assert ledger.status(request.request_id) == "reported_success"
    assert transport.calls == ["authenticate", "discover", "execute"]
    auth.close()
    ledger.close()
    auth = DurableRemoteAuthorization(database)
    ledger = DurableRemoteLedger(database)
    new_gateway = DurableDistributedGateway(
        transport, auth, ledger, max_inventory_age=timedelta(minutes=1))
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        new_gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == 1
    auth.close()
    ledger.close()


def test_expired_grant_denies_before_transport(tmp_path):
    _, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request, expiry=NOW))
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls == []
    assert ledger.status(request.request_id) == "denied"
    auth.close()
    ledger.close()


def test_failed_auth_denies_before_execution_and_reservation_is_permanent(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    transport.authenticated = False
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, request, now=NOW)
    assert "execute" not in transport.calls
    assert ledger.status(request.request_id) == "denied_after_reserve"
    auth.close()
    ledger.close()
    ledger2 = DurableRemoteLedger(database)
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        ledger2.reserve(request, now=NOW)
    ledger2.close()


def test_timeout_records_uncertainty_and_never_retries(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    transport.fail = True
    with pytest.raises(RemoteOperationUncertain, match="do not retry"):
        gateway.invoke(enrollment, request, now=NOW)
    assert ledger.status(request.request_id) == "uncertain"
    auth.close()
    ledger.close()
    ledger2 = DurableRemoteLedger(database)
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        ledger2.reserve(request, now=NOW)
    ledger2.close()


def test_crash_reserved_state_remains_unknown_and_not_reusable(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    ledger.reserve(request, now=NOW)
    ledger.close()
    reopened = DurableRemoteLedger(database)
    assert reopened.status(request.request_id) == "reserved"
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        reopened.reserve(request, now=NOW)
    reopened.close()
    auth.close()


def test_simultaneous_connections_cannot_reserve_same_id(tmp_path):
    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    another = DurableRemoteLedger(database)
    ledger.reserve(request, now=NOW)
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        another.reserve(request, now=NOW)
    another.close()
    ledger.close()
    auth.close()


def test_memory_database_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="in-memory"):
        DurableRemoteAuthorization(":memory:")
    with pytest.raises(ValueError, match="in-memory"):
        DurableRemoteLedger(":memory:")


def test_wrong_node_denies_without_contact_even_with_valid_grant(tmp_path):
    _, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    foreign = NodeEnrollment(
        DistributedNode(uuid4(), "Nyx"), fingerprint_public_key(b"foreign"),
        NOW, "Sparks")
    with pytest.raises(RemoteOperationDenied, match="Node mismatch"):
        gateway.invoke(foreign, request, now=NOW)
    assert transport.calls == []
    assert ledger.status(request.request_id) == "denied"
    auth.close()
    ledger.close()


def test_failed_durable_reservation_prevents_any_transport_contact(tmp_path):
    _, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    ledger.close()
    with pytest.raises(Exception):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls == []
    auth.close()


def test_final_status_cannot_be_rewritten(tmp_path):
    _, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    ledger.reserve(request, now=NOW)
    ledger.finalize(request.request_id, status="uncertain")
    with pytest.raises(RuntimeError, match="no pending"):
        ledger.finalize(request.request_id, status="reported_success")
    assert ledger.status(request.request_id) == "uncertain"
    auth.close()
    ledger.close()
