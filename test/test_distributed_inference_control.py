from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.config.model import ProviderConfiguration
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capabilities import (
    CapabilityInventory,
    RemoteCapability,
)
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.inference import RemoteInferenceResponse
from sofia.distributed.inference_control import (
    DurableRemoteInferenceControl,
    RemoteInferenceDenied,
    RemoteInferenceUncertain,
)
from sofia.distributed.model import (
    DistributedNode,
    NodeEndpoint,
    NodeTransport,
)


NOW=datetime(2026,9,29,19,0,tzinfo=timezone.utc)


class Transport:
    def __init__(self,node_id):
        self.node_id=node_id
        self.calls=[]
        self.authenticated=True
        self.advertise=True
        self.failure=None
        self.mismatch=False

    def authenticate(self,enrollment):
        self.calls.append("authenticate")
        return self.authenticated

    def discover(self,enrollment):
        self.calls.append("discover")
        capabilities=(
            (RemoteCapability("llm.inference",("chat",)),)
            if self.advertise else ()
        )
        return CapabilityInventory(
            self.node_id,
            NOW,
            capabilities,
            "authenticated-test",
            "1.0",
        )

    def infer(self,enrollment,request):
        self.calls.append("infer")
        if self.failure is not None:
            raise self.failure
        return RemoteInferenceResponse(
            uuid4() if self.mismatch else request.request_id,
            request.node_id,
            CognitiveResponse(content="remote answer"),
        )


def _setup(tmp_path, *, grant=True):
    node=DistributedNode(uuid4(),"Worker")
    transport=Transport(node.node_id)
    ctl=DurableRemoteInferenceControl(
        transport=transport,
        identity_path=tmp_path/"identity.db",
        endpoint_path=tmp_path/"endpoint.db",
        authorization_path=tmp_path/"grants.db",
        ledger_path=tmp_path/"inference-ledger.db",
        max_inventory_age=timedelta(minutes=5),
    )
    enrollment=NodeEnrollment(
        node,
        fingerprint_public_key(b"worker-key"),
        NOW,
        "Sparks",
    )
    ctl.identities.enroll(enrollment)
    ctl.endpoints.approve(
        ApprovedEndpoint(
            node.node_id,
            NodeEndpoint("worker.local",7443,NodeTransport.HTTPS),
            "Sparks",
        )
    )
    if grant:
        ctl.authorization.add_approved_grant(
            RemoteGrant(
                uuid4(),
                node.node_id,
                "llm.inference",
                "chat",
                "Sparks",
                NOW+timedelta(hours=1),
            )
        )
    return node,transport,ctl


def _request():
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="answer this",
            ),
        ),
    )


def _provider():
    return ProviderConfiguration(
        provider="ollama",
        model="vendor/remote-model:any",
        context_size=8192,
    )


def test_remote_inference_requires_full_admission_chain(tmp_path):
    node,transport,ctl=_setup(tmp_path)

    result=ctl.infer(
        node_id=node.node_id,
        provider=_provider(),
        request=_request(),
        now=NOW,
    )

    assert result.content=="remote answer"
    assert transport.calls==["authenticate","discover","infer"]
    ctl.close()


def test_remote_inference_without_grant_never_contacts_peer(tmp_path):
    node,transport,ctl=_setup(tmp_path,grant=False)

    with pytest.raises(RemoteInferenceDenied,match="grant"):
        ctl.infer(
            node_id=node.node_id,
            provider=_provider(),
            request=_request(),
            now=NOW,
        )

    assert transport.calls==[]
    ctl.close()


def test_remote_inference_requires_fresh_advertised_capability(tmp_path):
    node,transport,ctl=_setup(tmp_path)
    transport.advertise=False
    request_id=uuid4()

    with pytest.raises(RemoteInferenceDenied,match="inventory"):
        ctl.infer(
            node_id=node.node_id,
            provider=_provider(),
            request=_request(),
            now=NOW,
            request_id=request_id,
        )

    assert transport.calls==["authenticate","discover"]
    assert ctl.ledger.status(request_id)=="denied_after_reserve"
    ctl.close()


def test_remote_inference_transport_failure_is_durably_uncertain(tmp_path):
    node,transport,ctl=_setup(tmp_path)
    transport.failure=TimeoutError("synthetic")
    request_id=uuid4()

    with pytest.raises(RemoteInferenceUncertain,match="unknown"):
        ctl.infer(
            node_id=node.node_id,
            provider=_provider(),
            request=_request(),
            now=NOW,
            request_id=request_id,
        )

    assert ctl.ledger.status(request_id)=="uncertain"
    ctl.close()


def test_remote_inference_mismatched_response_is_durably_uncertain(tmp_path):
    node,transport,ctl=_setup(tmp_path)
    transport.mismatch=True
    request_id=uuid4()

    with pytest.raises(RemoteInferenceUncertain,match="mismatched"):
        ctl.infer(
            node_id=node.node_id,
            provider=_provider(),
            request=_request(),
            now=NOW,
            request_id=request_id,
        )

    assert ctl.ledger.status(request_id)=="uncertain"
    ctl.close()


def test_inference_ledger_never_stores_prompt_or_response_content(tmp_path):
    node,transport,ctl=_setup(tmp_path)
    ctl.infer(
        node_id=node.node_id,
        provider=_provider(),
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="SENSITIVE-PROMPT-SENTINEL",
                ),
            ),
        ),
        now=NOW,
    )
    ctl.close()

    with sqlite3.connect(tmp_path/"inference-ledger.db") as db:
        rows=db.execute(
            "SELECT request_id,node_id,grant_id,provider,model,observed_at,status "
            "FROM remote_inference_ledger"
        ).fetchall()
        schema=db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='remote_inference_ledger'"
        ).fetchone()[0]

    combined=repr(rows)+schema
    assert "SENSITIVE-PROMPT-SENTINEL" not in combined
    assert "remote answer" not in combined
