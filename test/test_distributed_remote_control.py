from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capabilities import CapabilityInventory, RemoteCapability
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.operations import RemoteOperationDenied, RemoteOperationRequest, RemoteOperationResult, RemoteOutcome, RemoteTransport
from sofia.distributed.remote_control import DurableRemoteControl


NOW=datetime(2026,9,24,tzinfo=timezone.utc)
class Transport(RemoteTransport):
    def __init__(self,node): self.node=node; self.executions=0
    def authenticate(self,enrollment): return True
    def discover(self,enrollment): return CapabilityInventory(self.node.node_id,NOW,(RemoteCapability("system.inspect",("read",)),),"authenticated-test")
    def execute(self,enrollment,request):
        self.executions+=1; return RemoteOperationResult(request.request_id,request.node_id,RemoteOutcome.REPORTED_SUCCESS,"ok")


def test_full_admission_chain_requires_durable_identity_endpoint_and_grant(tmp_path):
    node=DistributedNode(uuid4(),"Artemis"); transport=Transport(node)
    ctl=DurableRemoteControl(transport=transport,identity_path=tmp_path/"i.db",endpoint_path=tmp_path/"e.db",
        authorization_path=tmp_path/"a.db",ledger_path=tmp_path/"l.db",max_inventory_age=timedelta(minutes=5))
    enrollment=NodeEnrollment(node,fingerprint_public_key(b"k"),NOW,"Sparks")
    endpoint=NodeEndpoint("artemis.local",443,NodeTransport.HTTPS)
    grant=RemoteGrant(uuid4(),node.node_id,"system.inspect","read","Sparks",NOW+timedelta(hours=1))
    request=RemoteOperationRequest(uuid4(),node.node_id,grant.grant_id,"system.inspect","read",{})
    with pytest.raises(RemoteOperationDenied): ctl.invoke(enrollment,endpoint,request,now=NOW)
    ctl.identities.enroll(enrollment); ctl.endpoints.approve(ApprovedEndpoint(node.node_id,endpoint,"Sparks")); ctl.authorization.add_approved_grant(grant)
    result=ctl.invoke(enrollment,endpoint,request,now=NOW)
    assert result.outcome is RemoteOutcome.REPORTED_SUCCESS and transport.executions==1
    ctl.close()
