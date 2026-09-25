from datetime import datetime, timezone
from uuid import uuid4
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.retirement import NodeRetirementCoordinator


def test_retirement_disables_identity_and_endpoint(tmp_path):
    node=DistributedNode(uuid4(),"Artemis")
    enrollment=NodeEnrollment(node,fingerprint_public_key(b"k"),datetime.now(timezone.utc),"Sparks")
    endpoint=NodeEndpoint("artemis.local",443,NodeTransport.HTTPS)
    ids=DurableNodeIdentityRegistry(tmp_path/"id.db"); eps=DurableEndpointPolicy(tmp_path/"ep.db")
    ids.enroll(enrollment); eps.approve(ApprovedEndpoint(node.node_id,endpoint,"Sparks"))
    NodeRetirementCoordinator(ids,eps).retire(node.node_id)
    assert ids.get(node.node_id) is None
    assert eps.permits(node.node_id,endpoint) is False
    ids.close(); eps.close()
