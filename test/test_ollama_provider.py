import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.cognition.provider import LLMProviderError
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration


class FakeOllamaFunction:
    def __init__(
        self,
        name: str,
        arguments,
    ):
        self.name = name
        self.arguments = arguments


class FakeOllamaToolCall:
    def __init__(
        self,
        name: str,
        arguments,
        call_id: str | None = None,
    ):
        self.function = FakeOllamaFunction(
            name=name,
            arguments=arguments,
        )
        self.id = call_id


class FakeOllamaMessage:
    def __init__(
        self,
        content: str,
        tool_calls=None,
    ):
        self.content = content
        self.tool_calls = tool_calls


class FakeOllamaResponse:
    def __init__(
        self,
        content: str,
        tool_calls=None,
    ):
        self.message = FakeOllamaMessage(
            content=content,
            tool_calls=tool_calls,
        )


class FakeOllamaClient:
    def __init__(
        self,
        response: FakeOllamaResponse | None = None,
        error: Exception | None = None,
    ):
        self.response = response
        self.error = error
        self.model = None
        self.messages = None
        self.tools = None

    def chat(
        self,
        model,
        messages,
        tools=None,
    ):
        self.model = model
        self.messages = messages
        self.tools = tools

        if self.error is not None:
            raise self.error

        return self.response


def create_configuration() -> ProviderConfiguration:
    return ProviderConfiguration(
        provider="ollama",
        model="test-model",
    )


def test_ollama_provider_translates_request_and_response():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Hello from Ollama."
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="You are Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    response = provider.respond(request)

    assert response.content == "Hello from Ollama."
    assert response.tool_calls == ()
    assert client.model == "test-model"
    assert client.messages == [
        {
            "role": "system",
            "content": "You are Sofía.",
        },
        {
            "role": "user",
            "content": "Hello.",
        },
    ]
    assert client.tools is None


def test_ollama_provider_preserves_assistant_messages():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Continuation."
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content="Hi, Sparks.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Continue.",
            ),
        ),
    )

    provider.respond(request)

    assert client.messages == [
        {
            "role": "user",
            "content": "Hello.",
        },
        {
            "role": "assistant",
            "content": "Hi, Sparks.",
        },
        {
            "role": "user",
            "content": "Continue.",
        },
    ]


def test_ollama_provider_sends_tool_definitions():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "I can use the tool."
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    tool = CognitiveToolDefinition(
        name="inspect_file",
        description="Read a file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                },
            },
            "required": ["path"],
        },
    )

    provider.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Read a file.",
                ),
            ),
            tools=(tool,),
        )
    )

    assert client.tools == [
        {
            "type": "function",
            "function": {
                "name": "inspect_file",
                "description": "Read a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                        },
                    },
                    "required": ["path"],
                },
            },
        }
    ]


def test_ollama_provider_translates_tool_call_response():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "",
            tool_calls=(
                FakeOllamaToolCall(
                    name="inspect_file",
                    arguments={
                        "path": "src/sofia/cognition/model.py",
                    },
                    call_id="call-1",
                ),
            ),
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    response = provider.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Read the cognitive model.",
                ),
            ),
            tools=(
                CognitiveToolDefinition(
                    name="inspect_file",
                    description="Read a file.",
                    parameters={
                        "type": "object",
                    },
                ),
            ),
        )
    )

    assert len(response.tool_calls) == 1

    tool_call = response.tool_calls[0]

    assert tool_call.name == "inspect_file"
    assert tool_call.arguments == {
        "path": "src/sofia/cognition/model.py",
    }
    assert tool_call.call_id == "call-1"


def test_ollama_provider_translates_json_string_tool_arguments():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "",
            tool_calls=(
                FakeOllamaToolCall(
                    name="inspect_file",
                    arguments='{"path": "test/test_cognition_tools.py"}',
                ),
            ),
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    response = provider.respond(
        CognitiveRequest(messages=())
    )

    assert response.tool_calls[0].arguments == {
        "path": "test/test_cognition_tools.py",
    }


def test_ollama_provider_rejects_invalid_tool_arguments():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "",
            tool_calls=(
                FakeOllamaToolCall(
                    name="inspect_file",
                    arguments="not-json",
                ),
            ),
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    with pytest.raises(
        LLMProviderError,
        match="invalid JSON tool arguments",
    ):
        provider.respond(
            CognitiveRequest(messages=())
        )


def test_ollama_provider_translates_response_error():
    original_error = Exception(
        "Ollama connection failed."
    )

    client = FakeOllamaClient(
        error=original_error,
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    with pytest.raises(
        LLMProviderError,
        match="Ollama provider failed to process the cognitive request.",
    ) as exc_info:
        provider.respond(
            CognitiveRequest(messages=()),
        )

    assert exc_info.value.__cause__ is original_error


def test_ollama_provider_requires_provider_configuration():
    configuration = create_configuration()

    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Response."
        ),
    )

    provider = OllamaProvider(
        configuration=configuration,
        client=client,
    )

    assert provider.configuration is configuration
    assert provider.client is client


def test_ollama_provider_translates_assistant_tool_call_message():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "done",
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    provider.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.ASSISTANT,
                    content="",
                    tool_calls=(
                        CognitiveToolCall(
                            name="inspect_file",
                            arguments={
                                "path": "src/sofia/cognition/model.py",
                            },
                            call_id="call-9",
                        ),
                    ),
                ),
                CognitiveMessage(
                    role=CognitiveRole.TOOL,
                    content="File content here.",
                    tool_call_id="call-9",
                ),
            ),
        )
    )

    assert client.messages == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "inspect_file",
                        "arguments": {
                            "path": "src/sofia/cognition/model.py",
                        },
                    },
                }
            ],
        },
        {
            "role": "tool",
            "content": "File content here.",
            "tool_call_id": "call-9",
        },
    ]