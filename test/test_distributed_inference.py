from uuid import uuid4

import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.config.model import ProviderConfiguration
from sofia.distributed.inference import (
    MAX_CONTENT_BYTES,
    MAX_MESSAGES,
    RemoteInferenceContractError,
    RemoteInferenceRequest,
    RemoteInferenceResponse,
)


def _request():
    tool=CognitiveToolDefinition(
        name="inspect_system",
        description="Inspect verified host system state.",
        parameters={
            "type":"object",
            "properties":{"detail":{"type":"string"}},
            "additionalProperties":False,
        },
    )
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="Canonical context.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Check the host.",
            ),
        ),
        tools=(tool,),
        allow_tools=True,
    )


def test_remote_inference_request_round_trip_preserves_arbitrary_configured_model():
    original=RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=uuid4(),
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model="owner/vendor-model:any-size",
            temperature=0.2,
            seed=7,
            context_size=12000,
            thinking="high",
        ),
        request=_request(),
    )

    restored=RemoteInferenceRequest.from_payload(original.to_payload())

    assert restored==original
    assert restored.provider.model=="owner/vendor-model:any-size"
    assert restored.request.tools[0].name=="inspect_system"
    assert restored.request.allow_tools is True


def test_remote_inference_response_returns_tool_calls_as_data_only():
    call=CognitiveToolCall(
        name="inspect_system",
        arguments={"detail":"summary"},
        call_id="call-1",
    )
    original=RemoteInferenceResponse(
        request_id=uuid4(),
        node_id=uuid4(),
        response=CognitiveResponse(
            content="",
            tool_calls=(call,),
        ),
    )

    restored=RemoteInferenceResponse.from_payload(original.to_payload())

    assert restored==original
    assert restored.response.tool_calls==(call,)


def test_tool_history_round_trip_preserves_assistant_calls_and_tool_result_ids():
    call=CognitiveToolCall(
        name="inspect_system",
        arguments={"detail":"summary"},
        call_id="call-9",
    )
    cognitive=CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content="",
                tool_calls=(call,),
            ),
            CognitiveMessage(
                role=CognitiveRole.TOOL,
                content='{"status":"ok"}',
                tool_call_id="call-9",
            ),
        ),
        tools=(),
        allow_tools=False,
    )
    original=RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=uuid4(),
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model="vendor/model:custom",
        ),
        request=cognitive,
    )

    assert RemoteInferenceRequest.from_payload(
        original.to_payload()
    )==original


def test_request_rejects_oversized_message_before_transport():
    with pytest.raises(RemoteInferenceContractError, match="message content"):
        RemoteInferenceRequest(
            request_id=uuid4(),
            node_id=uuid4(),
            grant_id=uuid4(),
            provider=ProviderConfiguration(
                provider="ollama",
                model="vendor/model:custom",
            ),
            request=CognitiveRequest(
                messages=(
                    CognitiveMessage(
                        role=CognitiveRole.USER,
                        content="x"*(MAX_CONTENT_BYTES+1),
                    ),
                ),
            ),
        )


def test_request_rejects_too_many_messages():
    messages=tuple(
        CognitiveMessage(
            role=CognitiveRole.USER,
            content=str(index),
        )
        for index in range(MAX_MESSAGES+1)
    )
    with pytest.raises(RemoteInferenceContractError, match="messages"):
        RemoteInferenceRequest(
            request_id=uuid4(),
            node_id=uuid4(),
            grant_id=uuid4(),
            provider=ProviderConfiguration(
                provider="ollama",
                model="vendor/model:custom",
            ),
            request=CognitiveRequest(messages=messages),
        )


def test_unknown_wire_fields_are_rejected():
    original=RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=uuid4(),
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model="vendor/model:custom",
        ),
        request=CognitiveRequest(messages=()),
    )
    payload=original.to_payload()
    payload["surprise"]="nope"

    with pytest.raises(
        RemoteInferenceContractError,
        match="unsupported fields",
    ):
        RemoteInferenceRequest.from_payload(payload)


def test_non_json_tool_arguments_are_rejected_before_transport():
    call=CognitiveToolCall(
        name="inspect_system",
        arguments={"bad":object()},
    )
    with pytest.raises(RemoteInferenceContractError, match="non-JSON"):
        RemoteInferenceResponse(
            request_id=uuid4(),
            node_id=uuid4(),
            response=CognitiveResponse(
                content="",
                tool_calls=(call,),
            ),
        )


def test_nonfinite_tool_arguments_are_rejected_before_transport():
    call=CognitiveToolCall(
        name="inspect_system",
        arguments={"bad":float("nan")},
    )
    with pytest.raises(RemoteInferenceContractError, match="nonfinite"):
        RemoteInferenceResponse(
            request_id=uuid4(),
            node_id=uuid4(),
            response=CognitiveResponse(
                content="",
                tool_calls=(call,),
            ),
        )
