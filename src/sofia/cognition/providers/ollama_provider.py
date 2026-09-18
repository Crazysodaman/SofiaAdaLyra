import json

from ollama import Client
from ollama import ResponseError

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.cognition.provider import (
    LLMProvider,
    LLMProviderError,
)
from sofia.config.model import ProviderConfiguration


class OllamaProvider(LLMProvider):
    """
    LLM provider adapter for Ollama.

    Ollama-specific tool-call structures are translated into the
    provider-neutral cognitive model at this boundary.
    """

    def __init__(
        self,
        configuration: ProviderConfiguration,
        client: Client | None = None,
    ):
        self.configuration = configuration
        self.client = client if client is not None else Client()

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        messages = [
            self._message_to_ollama(message)
            for message in request.messages
        ]

        tools = [
            self._tool_to_ollama(tool)
            for tool in request.tools
        ]

        try:
            if tools:
                response = self.client.chat(
                    model=self.configuration.model,
                    messages=messages,
                    tools=tools,
                )
            else:
                response = self.client.chat(
                    model=self.configuration.model,
                    messages=messages,
                )

        except ResponseError as exc:
            raise LLMProviderError(
                "Ollama failed to process the cognitive request."
            ) from exc

        except Exception as exc:
            raise LLMProviderError(
                "Ollama provider failed to process the cognitive request."
            ) from exc

        return self._response_from_ollama(response)

    @staticmethod
    def _message_to_ollama(
        message: CognitiveMessage,
    ) -> dict:
        result = {
            "role": message.role.value,
            "content": message.content,
        }

        if message.role is CognitiveRole.ASSISTANT:
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ]

        if message.role is CognitiveRole.TOOL:
            if message.tool_call_id is not None:
                result["tool_call_id"] = message.tool_call_id

        return result

    @staticmethod
    def _tool_to_ollama(
        tool: CognitiveToolDefinition,
    ) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @classmethod
    def _response_from_ollama(
        cls,
        response,
    ) -> CognitiveResponse:
        message = response.message

        content = getattr(
            message,
            "content",
            "",
        )

        if content is None:
            content = ""

        raw_tool_calls = getattr(
            message,
            "tool_calls",
            None,
        )

        if raw_tool_calls is None:
            raw_tool_calls = ()

        tool_calls = tuple(
            cls._tool_call_from_ollama(
                tool_call
            )
            for tool_call in raw_tool_calls
        )

        return CognitiveResponse(
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _tool_call_from_ollama(
        tool_call,
    ) -> CognitiveToolCall:
        function = getattr(
            tool_call,
            "function",
            None,
        )

        if function is None:
            raise LLMProviderError(
                "Ollama returned a tool call without a function payload."
            )

        name = getattr(
            function,
            "name",
            None,
        )

        if not isinstance(name, str) or not name.strip():
            raise LLMProviderError(
                "Ollama returned a tool call without a valid function name."
            )

        arguments = getattr(
            function,
            "arguments",
            {},
        )

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise LLMProviderError(
                    "Ollama returned invalid JSON tool arguments."
                ) from exc

        if not isinstance(arguments, dict):
            raise LLMProviderError(
                "Ollama returned tool arguments that are not an object."
            )

        call_id = getattr(
            tool_call,
            "id",
            None,
        )

        return CognitiveToolCall(
            name=name,
            arguments=arguments,
            call_id=call_id,
        )