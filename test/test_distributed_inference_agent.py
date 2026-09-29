from uuid import uuid4

import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.config.model import ProviderConfiguration
from sofia.distributed.agent import (
    AgentInferenceEndpoint,
    AgentRequestLedger,
    RemoteInferenceReplayDenied,
)
from sofia.distributed.inference import (
    RemoteInferenceRequest,
    RemoteInferenceResponse,
)
from sofia.distributed.operations import RemoteOutcome


def _request(node_id):
    return RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=node_id,
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model="vendor/custom:any",
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


def test_agent_inference_endpoint_is_one_shot_and_records_success(tmp_path):
    node_id=uuid4()
    ledger=AgentRequestLedger(tmp_path/"ledger.db")
    calls=[]
    def handler(request):
        calls.append(request)
        return RemoteInferenceResponse(
            request.request_id,
            request.node_id,
            CognitiveResponse(content="remote hello"),
        )
    endpoint=AgentInferenceEndpoint(
        node_id=node_id,
        ledger=ledger,
        handler=handler,
    )
    request=_request(node_id)

    result=endpoint.execute(request.to_payload())

    assert result.response.content=="remote hello"
    assert calls==[request]
    assert ledger.status(request.request_id)==RemoteOutcome.REPORTED_SUCCESS.value

    with pytest.raises(RemoteInferenceReplayDenied):
        endpoint.execute(request.to_payload())
    assert calls==[request]
    ledger.close()


def test_agent_inference_endpoint_rejects_wrong_node_before_handler(tmp_path):
    node_id=uuid4()
    ledger=AgentRequestLedger(tmp_path/"ledger.db")
    calls=[]
    endpoint=AgentInferenceEndpoint(
        node_id=node_id,
        ledger=ledger,
        handler=lambda request:calls.append(request),
    )
    request=_request(uuid4())

    with pytest.raises(PermissionError,match="different node"):
        endpoint.execute(request.to_payload())

    assert calls==[]
    assert ledger.status(request.request_id) is None
    ledger.close()


def test_agent_inference_endpoint_records_handler_failure(tmp_path):
    node_id=uuid4()
    ledger=AgentRequestLedger(tmp_path/"ledger.db")
    def fail(request):
        raise RuntimeError("synthetic inference failure")
    endpoint=AgentInferenceEndpoint(
        node_id=node_id,
        ledger=ledger,
        handler=fail,
    )
    request=_request(node_id)

    with pytest.raises(RuntimeError,match="synthetic"):
        endpoint.execute(request.to_payload())

    assert ledger.status(request.request_id)==RemoteOutcome.REPORTED_FAILURE.value
    ledger.close()


def test_agent_inference_endpoint_rejects_mismatched_response_identity(tmp_path):
    node_id=uuid4()
    ledger=AgentRequestLedger(tmp_path/"ledger.db")
    endpoint=AgentInferenceEndpoint(
        node_id=node_id,
        ledger=ledger,
        handler=lambda request:RemoteInferenceResponse(
            uuid4(),
            request.node_id,
            CognitiveResponse(content="wrong"),
        ),
    )
    request=_request(node_id)

    with pytest.raises(ValueError,match="identity"):
        endpoint.execute(request.to_payload())

    assert ledger.status(request.request_id)==RemoteOutcome.REPORTED_FAILURE.value
    ledger.close()
