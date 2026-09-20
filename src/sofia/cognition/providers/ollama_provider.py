"""Ollama provider adapter with opt-in, content-free timing diagnostics."""
import json
from time import perf_counter

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
from sofia.cognition.performance import emit_performance, ollama_metric
from sofia.cognition.provider import LLMProvider, LLMProviderError
from sofia.config.model import ProviderConfiguration


class OllamaProvider(LLMProvider):
    """Translate Ollama generation options, messages and tool calls."""

    def __init__(self, configuration: ProviderConfiguration, client: Client | None = None):
        self.configuration = configuration
        self.client = client if client is not None else Client()

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        messages = [self._message_to_ollama(message) for message in request.messages]
        tools = [self._tool_to_ollama(tool) for tool in request.tools]
        kwargs = self._build_chat_kwargs(request=request, messages=messages, tools=tools)
        started = perf_counter()
        try:
            response = self.client.chat(**kwargs)
        except ResponseError as exc:
            emit_performance("ollama", elapsed_ms=(perf_counter() - started) * 1000)
            raise LLMProviderError("Ollama failed to process the cognitive request.") from exc
        except Exception as exc:
            emit_performance("ollama", elapsed_ms=(perf_counter() - started) * 1000)
            raise LLMProviderError("Ollama provider failed to process the cognitive request.") from exc

        elapsed_ms = (perf_counter() - started) * 1000
        emit_performance(
            "ollama",
            elapsed_ms=elapsed_ms,
            load_ms=ollama_metric(response, "load_duration", duration=True),
            prompt_eval_ms=ollama_metric(response, "prompt_eval_duration", duration=True),
            generation_ms=ollama_metric(response, "eval_duration", duration=True),
            provider_total_ms=ollama_metric(response, "total_duration", duration=True),
            prompt_tokens=ollama_metric(response, "prompt_eval_count"),
            generated_tokens=ollama_metric(response, "eval_count"),
            context_tokens=self.configuration.context_size,
        )
        return self._response_from_ollama(response)

    def _build_chat_kwargs(
        self, *, request: CognitiveRequest, messages: list[dict], tools: list[dict],
    ) -> dict:
        kwargs = {"model": self.configuration.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        options = self._build_generation_options()
        if options:
            kwargs["options"] = options
        if self.configuration.thinking is not None:
            kwargs["think"] = self.configuration.thinking
        return kwargs

    def _build_generation_options(self) -> dict:
        options: dict[str, int | float] = {}
        if self.configuration.temperature is not None:
            options["temperature"] = self.configuration.temperature
        if self.configuration.seed is not None:
            options["seed"] = self.configuration.seed
        if self.configuration.context_size is not None:
            options["num_ctx"] = self.configuration.context_size
        return options

    @staticmethod
    def _message_to_ollama(message: CognitiveMessage) -> dict:
        result = {"role": message.role.value, "content": message.content}
        if message.role is CognitiveRole.ASSISTANT:
            if message.tool_calls:
                result["tool_calls"] = [
                    {"type": "function", "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }} for tool_call in message.tool_calls
                ]
        if message.role is CognitiveRole.TOOL:
            if message.tool_call_id is not None:
                result["tool_call_id"] = message.tool_call_id
        return result

    @staticmethod
    def _tool_to_ollama(tool: CognitiveToolDefinition) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @classmethod
    def _response_from_ollama(cls, response) -> CognitiveResponse:
        message = response.message
        content = getattr(message, "content", "")
        if content is None:
            content = ""
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls is None:
            raw_tool_calls = ()
        tool_calls = tuple(cls._tool_call_from_ollama(call) for call in raw_tool_calls)
        return CognitiveResponse(content=content, tool_calls=tool_calls)

    @staticmethod
    def _tool_call_from_ollama(tool_call) -> CognitiveToolCall:
        function = getattr(tool_call, "function", None)
        if function is None:
            raise LLMProviderError("Ollama returned a tool call without a function payload.")
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise LLMProviderError("Ollama returned a tool call without a valid function name.")
        arguments = getattr(function, "arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise LLMProviderError("Ollama returned invalid JSON tool arguments.") from exc
        if not isinstance(arguments, dict):
            raise LLMProviderError("Ollama returned tool arguments that are not an object.")
        return CognitiveToolCall(
            name=name,
            arguments=arguments,
            call_id=getattr(tool_call, "id", None),
        )
