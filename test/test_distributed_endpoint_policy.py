from uuid import uuid4

import pytest

from sofia.distributed.endpoint_policy import ApprovedEndpoint, EndpointPolicy
from sofia.distributed.model import NodeEndpoint, NodeTransport


def endpoint(host="artemis.local", port=443, transport=NodeTransport.HTTPS):
    return NodeEndpoint(hostname=host, port=port, transport=transport)


def test_default_deny():
    assert EndpointPolicy().permits(uuid4(), endpoint()) is False


def test_exact_approved_endpoint_only():
    node = uuid4()
    policy = EndpointPolicy()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))

    assert policy.permits(node, endpoint()) is True
    assert policy.permits(node, endpoint("other.local")) is False
    assert policy.permits(node, endpoint(port=8443)) is False
    assert policy.permits(node, endpoint(transport=NodeTransport.SSH, port=22)) is False


def test_approval_is_node_scoped():
    node = uuid4()
    other = uuid4()
    policy = EndpointPolicy()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    assert policy.permits(other, endpoint()) is False


def test_revoke_returns_to_default_deny():
    node = uuid4()
    policy = EndpointPolicy()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    policy.revoke(node)
    assert policy.permits(node, endpoint()) is False


def test_replacement_requires_explicit_revoke():
    node = uuid4()
    policy = EndpointPolicy()
    policy.approve(ApprovedEndpoint(node, endpoint(), "Sparks"))
    with pytest.raises(ValueError):
        policy.approve(ApprovedEndpoint(node, endpoint("new.local"), "Sparks"))


@pytest.mark.parametrize("approver", ["", "   ", None])
def test_human_approver_required(approver):
    with pytest.raises((TypeError, ValueError)):
        ApprovedEndpoint(uuid4(), endpoint(), approver)
