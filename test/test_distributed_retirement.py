from hashlib import sha256
from datetime import datetime, timezone
from uuid import uuid4
from sofia.distributed.model import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.model import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.operator import retire_node


def test_retirement_disables_identity_and_endpoint(tmp_path):
    node=DistributedNode(uuid4(),"Artemis")
    enrollment=NodeEnrollment(node,sha256(b"k").hexdigest(),datetime.now(timezone.utc),"Sparks")
    endpoint=NodeEndpoint("artemis.local",443,NodeTransport.HTTPS)
    state_path=tmp_path/"sofia.db"
    ids=DurableNodeIdentityRegistry(state_path); eps=DurableEndpointPolicy(state_path)
    ids.enroll(enrollment); eps.approve(ApprovedEndpoint(node.node_id,endpoint,"Sparks"))
    retire_node(state_path,node.node_id)
    assert ids.get(node.node_id) is None
    assert eps.permits(node.node_id,endpoint) is False
    ids.close(); eps.close()
