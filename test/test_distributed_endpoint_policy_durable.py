from uuid import uuid4

import pytest

from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.model import NodeEndpoint, NodeTransport


def endpoint(host="artemis.local", port=443):
    return NodeEndpoint(host, port, NodeTransport.HTTPS)


def test_approval_survives_restart(tmp_path):
    path = tmp_path / "net.db"
    node = uuid4()
    first = DurableEndpointPolicy(path)
    first.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    first.close()

    reopened = DurableEndpointPolicy(path)
    assert reopened.permits(node, endpoint()) is True
    reopened.close()


def test_revocation_survives_restart(tmp_path):
    path = tmp_path / "net.db"
    node = uuid4()
    first = DurableEndpointPolicy(path)
    first.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    first.revoke(node)
    first.close()

    reopened = DurableEndpointPolicy(path)
    assert reopened.permits(node, endpoint()) is False
    reopened.close()


def test_endpoint_drift_is_denied(tmp_path):
    policy = DurableEndpointPolicy(tmp_path / "net.db")
    node = uuid4()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    assert policy.permits(node, endpoint("other.local")) is False
    assert policy.permits(node, endpoint(port=8443)) is False
    policy.close()


def test_revoked_node_id_cannot_be_silently_reapproved(tmp_path):
    policy = DurableEndpointPolicy(tmp_path / "net.db")
    node = uuid4()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    policy.revoke(node)
    with pytest.raises(ValueError):
        policy.approve(ApprovedEndpoint(node, endpoint("new.local"), "Sparks"))
    policy.close()


def test_memory_database_is_rejected():
    with pytest.raises(ValueError):
        DurableEndpointPolicy(":memory:")
