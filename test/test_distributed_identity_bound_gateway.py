from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.identity_bound_gateway import IdentityBoundGateway
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.operations import RemoteOperationDenied, RemoteOperationRequest


class StubGateway:
    pass


def record(node_id=None,key=b"k"):
    return NodeEnrollment(DistributedNode(node_id or uuid4(),"Artemis"),fingerprint_public_key(key),datetime.now(timezone.utc),"Sparks")


def test_constructor_requires_real_endpoint_gateway(tmp_path):
    ids=DurableNodeIdentityRegistry(tmp_path/"id.db")
    with pytest.raises(TypeError): IdentityBoundGateway(ids,StubGateway())
    ids.close()


def test_retired_identity_is_denied_before_gateway(tmp_path):
    from sofia.distributed.endpoint_bound_gateway import EndpointBoundDurableGateway
    # Contract is covered without constructing transport: invoke cannot pass identity boundary.
    ids=DurableNodeIdentityRegistry(tmp_path/"id.db")
    rec=record(); ids.enroll(rec); ids.retire(rec.node.node_id)
    gateway=object.__new__(EndpointBoundDurableGateway)
    bound=IdentityBoundGateway(ids,gateway)
    request=RemoteOperationRequest(uuid4(),rec.node.node_id,uuid4(),"system.inspect","read",{})
    with pytest.raises(RemoteOperationDenied,match="retired"):
        bound.invoke(rec,NodeEndpoint("artemis.local",443,NodeTransport.HTTPS),request,now=datetime.now(timezone.utc))
    ids.close()
