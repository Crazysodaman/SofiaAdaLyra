"""22G/H: one-shot local orchestration through explicitly injected fake transport.

These are NOT authenticated-network integration tests. No sockets or devices.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.authorization import RemoteAuthorization, RemoteGrant
from sofia.distributed.capabilities import CapabilityInventory, RemoteCapability
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.model import DistributedNode
from sofia.distributed.operations import (
    DistributedGateway, RemoteOperationDenied, RemoteOperationRequest,
    RemoteOperationResult, RemoteOperationUncertain, RemoteOutcome, RemoteTransport,
)

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


class FakeTransport(RemoteTransport):
    """Test stub ONLY; never use for an actual network connection."""

    def __init__(self):
        self.calls = []
        self.authenticated = True
        self.inventory = None
        self.failure = None
        self.result = None

    def authenticate(self, enrollment):
        self.calls.append("authenticate")
        return self.authenticated

    def discover(self, enrollment):
        self.calls.append("discover")
        return self.inventory

    def execute(self, enrollment, request):
        self.calls.append("execute")
        if self.failure:
            raise self.failure
        return self.result or RemoteOperationResult(
            request.request_id, request.node_id, RemoteOutcome.REPORTED_SUCCESS,
            "remote reported completion")


def fixture(*, grant=True):
    node = DistributedNode(uuid4(), "Eos")
    enrollment = NodeEnrollment(node, fingerprint_public_key(b"test-public-key"), NOW, "operator")
    request = RemoteOperationRequest(uuid4(), node.node_id, uuid4(),
                                     "hardware.inspect", "summary", {"detail": "short"})
    authorization = RemoteAuthorization()
    if grant:
        authorization.add_approved_grant(RemoteGrant(
            request.grant_id, node.node_id, request.capability,
            request.operation, "Sparks", NOW + timedelta(minutes=2)))
    transport = FakeTransport()
    transport.inventory = CapabilityInventory(
        node.node_id, NOW, (RemoteCapability("hardware.inspect", ("summary",)),),
        "test-fake")
    gateway = DistributedGateway(transport, authorization,
                                 max_inventory_age=timedelta(minutes=1))
    return enrollment, request, transport, gateway


def test_denial_prevents_even_network_authentication():
    enrollment, request, transport, gateway = fixture(grant=False)
    with pytest.raises(RemoteOperationDenied, match="grant"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls == []
    assert gateway.audit_events[-1][1] == "denied:no_grant"


def test_authorized_one_shot_remote_report_is_not_local_verification():
    enrollment, request, transport, gateway = fixture()
    result = gateway.invoke(enrollment, request, now=NOW)
    assert result.outcome is RemoteOutcome.REPORTED_SUCCESS
    assert transport.calls == ["authenticate", "discover", "execute"]
    assert gateway.audit_events[-1] == (request.request_id, "reported:reported_success")
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == 1


def test_wrong_node_fails_without_contact():
    enrollment, request, transport, gateway = fixture()
    foreign = NodeEnrollment(DistributedNode(uuid4(), "Nyx"),
                             fingerprint_public_key(b"other-key"), NOW, "operator")
    with pytest.raises(RemoteOperationDenied, match="node"):
        gateway.invoke(foreign, request, now=NOW)
    assert transport.calls == []


@pytest.mark.parametrize("mode", ["auth", "wrong_inventory", "stale_inventory", "missing_capability"])
def test_fails_closed_before_execute(mode):
    enrollment, request, transport, gateway = fixture()
    if mode == "auth":
        transport.authenticated = False
    elif mode == "wrong_inventory":
        transport.inventory = CapabilityInventory(uuid4(), NOW,
            (RemoteCapability("hardware.inspect", ("summary",)),), "test")
    elif mode == "stale_inventory":
        transport.inventory = CapabilityInventory(request.node_id, NOW - timedelta(minutes=2),
            (RemoteCapability("hardware.inspect", ("summary",)),), "test")
    else:
        transport.inventory = CapabilityInventory(request.node_id, NOW, (), "test")
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, request, now=NOW)
    assert "execute" not in transport.calls


def test_transport_error_is_uncertain_and_never_retried():
    enrollment, request, transport, gateway = fixture()
    transport.failure = TimeoutError("maybe executed")
    with pytest.raises(RemoteOperationUncertain, match="do not retry"):
        gateway.invoke(enrollment, request, now=NOW)
    assert gateway.audit_events[-1][1] == "uncertain:transport_error"
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == 1


def test_mismatched_result_is_uncertain():
    enrollment, request, transport, gateway = fixture()
    transport.result = RemoteOperationResult(uuid4(), request.node_id,
                                              RemoteOutcome.REPORTED_SUCCESS, "mismatched")
    with pytest.raises(RemoteOperationUncertain, match="Mismatched"):
        gateway.invoke(enrollment, request, now=NOW)


def test_remote_reported_failure_is_preserved_not_promoted_to_success():
    enrollment, request, transport, gateway = fixture()
    transport.result = RemoteOperationResult(request.request_id, request.node_id,
                                              RemoteOutcome.REPORTED_FAILURE, "failed")
    assert gateway.invoke(enrollment, request, now=NOW).outcome is RemoteOutcome.REPORTED_FAILURE


@pytest.mark.parametrize("params", [
    {"command": "whoami"}, {"script": "echo hi"}, {"token": "oops"},
    {"nested": {"exec": "oops"}}, {"huge": "x" * 5000}, {"invalid": float("nan")},
])
def test_arbitrary_commands_secrets_and_unbounded_parameters_rejected(params):
    with pytest.raises((TypeError, ValueError)):
        RemoteOperationRequest(uuid4(), uuid4(), uuid4(), "system.inspect", "summary", params)


def test_request_copies_parameters_and_does_not_store_mutable_inputs():
    data = {"detail": "short"}
    request = RemoteOperationRequest(uuid4(), uuid4(), uuid4(),
                                     "hardware.inspect", "summary", data)
    data["detail"] = "long"
    assert request.parameters["detail"] == "short"
    with pytest.raises(TypeError):
        request.parameters["detail"] = "override"
