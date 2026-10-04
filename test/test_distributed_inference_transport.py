from hashlib import sha256
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.config.model import ProviderConfiguration
from sofia.distributed.https_transport import (
    HttpsTransportError,
    PinnedHttpsRemoteTransport,
)
from sofia.distributed.model import NodeEnrollment
from sofia.distributed.inference import (
    RemoteInferenceRequest,
    RemoteInferenceResponse,
)
from sofia.distributed.model import DistributedNode


NOW=datetime(2026,9,29,tzinfo=timezone.utc)


def _fixture():
    node=DistributedNode(uuid4(),"Worker")
    enrollment=NodeEnrollment(
        node,
        sha256(b"worker-key").hexdigest(),
        NOW,
        "Sparks",
    )
    request=RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=node.node_id,
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model="vendor/worker:any",
        ),
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="hello",
                ),
            ),
        ),
    )
    return enrollment,request


def test_https_transport_posts_dedicated_inference_payload():
    enrollment,request=_fixture()
    expected=RemoteInferenceResponse(
        request.request_id,
        request.node_id,
        CognitiveResponse(content="remote response"),
    )
    calls=[]
    transport=object.__new__(PinnedHttpsRemoteTransport)
    def fake(enrollment_arg,method,path,payload=None):
        calls.append((enrollment_arg,method,path,payload))
        return expected.to_payload()
    transport._request=fake

    result=transport.infer(enrollment,request)

    assert result==expected
    assert calls==[(
        enrollment,
        "POST",
        "/v1/inference",
        request.to_payload(),
    )]


def test_https_transport_rejects_inference_for_wrong_enrollment():
    enrollment,request=_fixture()
    foreign=NodeEnrollment(
        DistributedNode(uuid4(),"Foreign"),
        sha256(b"foreign-key").hexdigest(),
        NOW,
        "Sparks",
    )
    transport=object.__new__(PinnedHttpsRemoteTransport)
    transport._request=lambda *args,**kwargs:pytest.fail("network call")

    with pytest.raises(HttpsTransportError,match="node"):
        transport.infer(foreign,request)


def test_https_transport_rejects_mismatched_inference_response():
    enrollment,request=_fixture()
    wrong=RemoteInferenceResponse(
        uuid4(),
        request.node_id,
        CognitiveResponse(content="wrong"),
    )
    transport=object.__new__(PinnedHttpsRemoteTransport)
    transport._request=lambda *args,**kwargs:wrong.to_payload()

    with pytest.raises(HttpsTransportError,match="identity"):
        transport.infer(enrollment,request)
