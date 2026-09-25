from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.durable import DurableRemoteAuthorization


def test_revoke_node_disables_all_grants_and_survives_restart(tmp_path):
    path=tmp_path/"auth.db"; node=uuid4(); other=uuid4(); now=datetime.now(timezone.utc)
    auth=DurableRemoteAuthorization(path)
    grants=[RemoteGrant(uuid4(),node,"system.inspect","read","Sparks",now+timedelta(hours=1)),
            RemoteGrant(uuid4(),node,"service.inspect","read","Sparks",now+timedelta(hours=1)),
            RemoteGrant(uuid4(),other,"system.inspect","read","Sparks",now+timedelta(hours=1))]
    for g in grants: auth.add_approved_grant(g)
    assert auth.revoke_node(node)==2
    auth.close(); auth=DurableRemoteAuthorization(path)
    assert not auth.permits(grants[0].grant_id,node_id=node,capability="system.inspect",operation="read",now=now)
    assert auth.permits(grants[2].grant_id,node_id=other,capability="system.inspect",operation="read",now=now)
    auth.close()
