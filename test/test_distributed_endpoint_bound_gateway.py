from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capabilities import CapabilityInventory, RemoteCapability
from sofia.distributed.durable import DurableRemoteAuthorization, DurableRemoteLedger
from sofia.distributed.endpoint_bound_gateway import EndpointBoundDurableGateway
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.operations import (
    RemoteOperationDenied,
    RemoteOperationRequest,
    RemoteOperationResult,
    RemoteOutcome,
    RemoteTransport,
)


NOW = datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc)


class FakeTransport(RemoteTransport):
    def __init__(self, inventory):
        self.inventory = inventory
        self.executions = 0

    def authenticate(self, enrollment):
        return True

    def discover(self, enrollment):
        return self.inventory

    def execute(self, enrollment, request):
        self.executions += 1
        return RemoteOperationResult(request.request_id, request.node_id, RemoteOutcome.REPORTED_SUCCESS, "ok")


def setup(tmp_path):
    node = DistributedNode(uuid4(), "Artemis")
    endpoint = NodeEndpoint("artemis.local", 443, NodeTransport.HTTPS)
    enrollment = NodeEnrollment(
        node=node,
        public_key_sha256=fingerprint_public_key(b"public"),
        provisioned_at=NOW,
        recorded_by="Sparks",
    )
    inventory = CapabilityInventory(
        node_id=node.node_id,
        observed_at=NOW,
        capabilities=(RemoteCapability("system.inspect", ("read",)),),
    )
    transport = FakeTransport(inventory)
    auth = DurableRemoteAuthorization(tmp_path / "auth.db")
    ledger = DurableRemoteLedger(tmp_path / "ledger.db")
    policy = DurableEndpointPolicy(tmp_path / "endpoint.db")
    grant = RemoteGrant(uuid4(), node.node_id, "system.inspect", "read", "Sparks", NOW + timedelta(hours=1))
    auth.add_approved_grant(grant)
    request = RemoteOperationRequest(uuid4(), node.node_id, grant.grant_id, "system.inspect", "read", {})
    gateway = EndpointBoundDurableGateway(
        transport, auth, ledger, policy, max_inventory_age=timedelta(minutes=5)
    )
    return node, endpoint, enrollment, transport, auth, ledger, policy, request, gateway


def test_denies_unapproved_endpoint_before_transport(tmp_path):
    node, endpoint, enrollment, transport, auth, ledger, policy, request, gateway = setup(tmp_path)
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, endpoint, request, now=NOW)
    assert transport.executions == 0
    auth.close(); ledger.close(); policy.close()


def test_allows_exact_approved_endpoint(tmp_path):
    node, endpoint, enrollment, transport, auth, ledger, policy, request, gateway = setup(tmp_path)
    policy.approve(ApprovedEndpoint(node.node_id, endpoint, "Sparks"))
    result = gateway.invoke(enrollment, endpoint, request, now=NOW)
    assert result.outcome is RemoteOutcome.REPORTED_SUCCESS
    assert transport.executions == 1
    auth.close(); ledger.close(); policy.close()


def test_endpoint_drift_denied_even_with_valid_grant(tmp_path):
    node, endpoint, enrollment, transport, auth, ledger, policy, request, gateway = setup(tmp_path)
    policy.approve(ApprovedEndpoint(node.node_id, endpoint, "Sparks"))
    drifted = NodeEndpoint("other.local", 443, NodeTransport.HTTPS)
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, drifted, request, now=NOW)
    assert transport.executions == 0
    auth.close(); ledger.close(); policy.close()


def test_revocation_blocks_future_calls(tmp_path):
    node, endpoint, enrollment, transport, auth, ledger, policy, request, gateway = setup(tmp_path)
    policy.approve(ApprovedEndpoint(node.node_id, endpoint, "Sparks"))
    policy.revoke(node.node_id)
    with pytest.raises(RemoteOperationDenied):
        gateway.invoke(enrollment, endpoint, request, now=NOW)
    assert transport.executions == 0
    auth.close(); ledger.close(); policy.close()
