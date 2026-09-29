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
from sofia.cognition.provider import LLMProvider
from sofia.config.model import ProviderConfiguration
from sofia.distributed.inference import RemoteInferenceRequest
from sofia.distributed.inference_service import (
    LocalOllamaInferenceService,
    RemoteInferenceDenied,
    RemoteInferencePolicy,
)


class Provider(LLMProvider):
    def __init__(self, configuration, calls):
        self.configuration=configuration
        self.calls=calls

    def respond(self, request):
        self.calls.append((self.configuration,request))
        return CognitiveResponse(
            content="remote text",
            tool_calls=(
                CognitiveToolCall(
                    name="inspect_system",
                    arguments={"detail":"summary"},
                    call_id="remote-call-1",
                ),
            ),
        )


def _request(node_id, *, model="owner/custom:any", context_size=8192, tools=()):
    return RemoteInferenceRequest(
        request_id=uuid4(),
        node_id=node_id,
        grant_id=uuid4(),
        provider=ProviderConfiguration(
            provider="ollama",
            model=model,
            context_size=context_size,
        ),
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Inspect this.",
                ),
            ),
            tools=tools,
            allow_tools=bool(tools),
        ),
    )


def test_worker_returns_remote_tool_calls_without_executing_them():
    node_id=uuid4()
    calls=[]
    service=LocalOllamaInferenceService(
        node_id=node_id,
        policy=RemoteInferencePolicy(
            allowed_models=("owner/custom:any",),
        ),
        provider_factory=lambda config: Provider(config,calls),
    )
    tool=CognitiveToolDefinition(
        name="inspect_system",
        description="Inspect system state.",
        parameters={"type":"object"},
    )

    result=service.infer(_request(node_id,tools=(tool,)))

    assert result.response.content=="remote text"
    assert result.response.tool_calls[0].name=="inspect_system"
    assert len(calls)==1
    assert calls[0][1].tools==(tool,)


def test_worker_model_allowlist_is_configuration_data_not_code_identity():
    node_id=uuid4()
    service=LocalOllamaInferenceService(
        node_id=node_id,
        policy=RemoteInferencePolicy(
            allowed_models=("vendor/arbitrary-model:42b",),
        ),
        provider_factory=lambda config: Provider(config,[]),
    )

    with pytest.raises(RemoteInferenceDenied,match="allowlist"):
        service.infer(_request(node_id,model="other/model:1b"))


def test_worker_rejects_wrong_node_before_provider_creation():
    node_id=uuid4()
    created=[]
    service=LocalOllamaInferenceService(
        node_id=node_id,
        policy=RemoteInferencePolicy(
            allowed_models=("owner/custom:any",),
        ),
        provider_factory=lambda config: created.append(config),
    )

    with pytest.raises(RemoteInferenceDenied,match="different node"):
        service.infer(_request(uuid4()))

    assert created==[]


def test_worker_rejects_context_above_local_policy():
    node_id=uuid4()
    service=LocalOllamaInferenceService(
        node_id=node_id,
        policy=RemoteInferencePolicy(
            allowed_models=("owner/custom:any",),
            max_context_size=4096,
        ),
        provider_factory=lambda config: Provider(config,[]),
    )

    with pytest.raises(RemoteInferenceDenied,match="context"):
        service.infer(_request(node_id,context_size=8192))


def test_worker_can_disable_tool_schemas_without_affecting_text_inference():
    node_id=uuid4()
    calls=[]
    service=LocalOllamaInferenceService(
        node_id=node_id,
        policy=RemoteInferencePolicy(
            allowed_models=("owner/custom:any",),
            allow_tools=False,
        ),
        provider_factory=lambda config: Provider(config,calls),
    )
    text=service.infer(_request(node_id,tools=()))
    assert text.response.content=="remote text"

    tool=CognitiveToolDefinition(
        name="inspect_system",
        description="Inspect system state.",
        parameters={"type":"object"},
    )
    with pytest.raises(RemoteInferenceDenied,match="tool schemas"):
        service.infer(_request(node_id,tools=(tool,)))
