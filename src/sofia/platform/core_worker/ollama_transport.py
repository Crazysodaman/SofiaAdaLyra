"""Generic bounded Ollama transport; no individual Core response policy."""
from __future__ import annotations

import json
import math
from time import perf_counter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ollama import Client

from sofia.sdk.cognition_model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.platform.cognition_budget import model_token_budget
from sofia.platform.state.performance import (
    emit_performance, model_call_finished, model_call_started, ollama_metric,
)
from sofia.sdk.cognition_engine import LLMProvider, LLMProviderError
from sofia.platform.config.model import ProviderConfiguration
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.platform.config.inference_endpoint import (
    configured_ollama_endpoint,
    validate_ollama_endpoint,
)


# Provider-supplied JSON is not an authority grant. Bound resource use at the
# adapter before its tool candidates reach the governed dispatcher.
# This is the HTTP client's per-I/O timeout, not an overall turn deadline.
# With one permitted personal quality retry, nominal 2 x 45s is below the
# default 120s Core worker response deadline; Team 1 owns final lease fencing.
# Custom shorter worker deadlines still require explicit compatibility QA.
OLLAMA_IO_TIMEOUT_SECONDS = 45.0

_MAX_TOOL_CALLS = 16
_MAX_TOOL_ARGUMENT_BYTES = 64 * 1024
_MAX_TOOL_ARGUMENT_NODES = 4096
_MAX_TOOL_ARGUMENT_DEPTH = 16


def _validate_tool_arguments(arguments: dict) -> None:
    """Require bounded, serializable JSON data without executing model content."""
    if type(arguments) is not dict:
        raise LLMProviderError("Ollama returned tool arguments that are not an object.")
    stack = [(arguments, 0)]
    visited = 0
    while stack:
        value, depth = stack.pop()
        visited += 1
        if depth > _MAX_TOOL_ARGUMENT_DEPTH or visited > _MAX_TOOL_ARGUMENT_NODES:
            raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
        if type(value) is dict:
            if len(value) > _MAX_TOOL_ARGUMENT_NODES:
                raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
            for key, child in value.items():
                if type(key) is not str or len(key) > _MAX_TOOL_ARGUMENT_BYTES:
                    raise LLMProviderError("Ollama returned invalid JSON tool arguments.")
                stack.append((child, depth + 1))
        elif type(value) is list:
            if len(value) > _MAX_TOOL_ARGUMENT_NODES:
                raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
            stack.extend((child, depth + 1) for child in value)
        elif type(value) is float:
            if not math.isfinite(value):
                raise LLMProviderError("Ollama returned invalid JSON tool arguments.")
        elif type(value) is str:
            if len(value) > _MAX_TOOL_ARGUMENT_BYTES:
                raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
        elif value is not None and type(value) not in (int, bool):
            raise LLMProviderError("Ollama returned invalid JSON tool arguments.")
    try:
        encoded = json.dumps(
            arguments, allow_nan=False, ensure_ascii=False, separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > _MAX_TOOL_ARGUMENT_BYTES:
            raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise LLMProviderError("Ollama returned invalid JSON tool arguments.") from exc


class GenericOllamaProvider(LLMProvider):
    """Translate Ollama generation options, messages and tool calls."""

    def __init__(
        self,
        configuration: ProviderConfiguration,
        client: Client | None = None,
        *,
        keep_alive: str | None = None,
        endpoint: str | None = None,
    ):
        self.configuration = configuration
        self.endpoint = (
            configured_ollama_endpoint()
            if endpoint is None else validate_ollama_endpoint(endpoint)
        )
        self.client = client if client is not None else self._new_client(self.endpoint)
        if keep_alive is not None and (
            not isinstance(keep_alive, str) or not keep_alive.strip()
        ):
            raise ValueError("keep_alive must be a nonempty string or None")
        self.keep_alive = keep_alive

    @staticmethod
    def _new_client(endpoint: str):
        from ollama import Client

        return Client(host=endpoint, timeout=OLLAMA_IO_TIMEOUT_SECONDS)

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        return self._respond_once(request)

    def _respond_once(self, request: CognitiveRequest) -> CognitiveResponse:
        from ollama import ResponseError

        messages = [self._message_to_ollama(message) for message in request.messages]
        # An explicit no-tools request must never advertise executable tools
        # to the model, even if a caller supplies stale tool definitions.
        tools = (
            [self._tool_to_ollama(tool) for tool in request.tools]
            if request.allow_tools else []
        )
        kwargs = self._build_chat_kwargs(request=request, messages=messages, tools=tools)
        started = perf_counter()
        model_call_started()
        try:
            response = self.client.chat(**kwargs)
        except ResponseError as exc:
            emit_performance("ollama", elapsed_ms=(perf_counter() - started) * 1000)
            raise LLMProviderError("Ollama failed to process the cognitive request.") from exc
        except Exception as exc:
            emit_performance("ollama", elapsed_ms=(perf_counter() - started) * 1000)
            raise LLMProviderError("Ollama provider failed to process the cognitive request.") from exc
        finally:
            model_call_finished()

        elapsed_ms = (perf_counter() - started) * 1000
        budget = model_token_budget(
            request.route_hint,
            configured_context=self.configuration.context_size,
            configured_output=self.configuration.max_output_tokens,
        )
        emit_performance(
            "ollama",
            elapsed_ms=elapsed_ms,
            load_ms=ollama_metric(response, "load_duration", duration=True),
            prompt_eval_ms=ollama_metric(response, "prompt_eval_duration", duration=True),
            generation_ms=ollama_metric(response, "eval_duration", duration=True),
            provider_total_ms=ollama_metric(response, "total_duration", duration=True),
            prompt_tokens=ollama_metric(response, "prompt_eval_count"),
            generated_tokens=ollama_metric(response, "eval_count"),
            context_tokens=budget.context_tokens,
            context_budget=budget.context_tokens,
            output_budget=budget.output_tokens,
        )
        # A malformed provider payload is an outage, not an assistant answer.
        # Keep provider internals out of user-facing errors and never execute
        # partially decoded tool calls.
        try:
            parsed = self._response_from_ollama(response)
            if parsed.tool_calls and not request.allow_tools:
                raise LLMProviderError(
                    "Ollama returned tool calls for a text-only request."
                )
            return parsed
        except LLMProviderError:
            raise
        except (AttributeError, TypeError, ValueError, KeyError) as exc:
            raise LLMProviderError(
                "Ollama returned a malformed cognitive response."
            ) from exc

    def _build_chat_kwargs(
        self, *, request: CognitiveRequest, messages: list[dict], tools: list[dict],
    ) -> dict:
        kwargs = {"model": self.configuration.model, "messages": messages}
        if self.keep_alive is not None:
            kwargs["keep_alive"] = self.keep_alive
        if tools:
            kwargs["tools"] = tools
        options = self._build_generation_options(request=request)
        if options:
            kwargs["options"] = options
        if self.configuration.thinking is not None:
            kwargs["think"] = self.configuration.thinking
        return kwargs

    def _build_generation_options(self, *, request: CognitiveRequest) -> dict:
        options: dict[str, int | float] = {}
        if self.configuration.temperature is not None:
            options["temperature"] = self.configuration.temperature
        if self.configuration.seed is not None:
            options["seed"] = self.configuration.seed
        budget = model_token_budget(
            request.route_hint,
            configured_context=self.configuration.context_size,
            configured_output=self.configuration.max_output_tokens,
        )
        if budget.context_tokens is not None:
            options["num_ctx"] = budget.context_tokens
        if budget.output_tokens is not None:
            options["num_predict"] = budget.output_tokens
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
        # Ollama's ChatResponse always has a message. Treat a missing or
        # structurally incomplete payload as an outage, not a legitimate
        # empty assistant answer that quality repair might substitute.
        if message is None or not hasattr(message, "content"):
            raise LLMProviderError("Ollama returned a missing message payload.")
        content = message.content
        if content is None:
            content = ""
        # Reject invalid content before quality-repair or persistence paths.
        if not isinstance(content, str):
            raise LLMProviderError("Ollama returned non-text response content.")
        try:
            # SQLite, IPC and Ollama transports require serializable UTF-8.
            # A lone surrogate is not a safe persisted model response.
            content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise LLMProviderError("Ollama returned invalid Unicode response content.") from exc
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls is None:
            raw_tool_calls = ()
        if not isinstance(raw_tool_calls, (list, tuple)):
            raise LLMProviderError("Ollama returned malformed tool calls.")
        if len(raw_tool_calls) > _MAX_TOOL_CALLS:
            raise LLMProviderError("Ollama returned too many tool calls.")
        tool_calls = tuple(cls._tool_call_from_ollama(call) for call in raw_tool_calls)
        # A response with neither usable text nor a tool proposal is not a
        # generated assistant turn. In particular, a blank or thinking-only
        # completion must not enter personal quality repair, which could turn
        # a failed provider call into a canned-looking conversation.
        if not content.strip() and not tool_calls:
            raise LLMProviderError("Ollama returned an empty cognitive response.")
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
            if len(arguments) > _MAX_TOOL_ARGUMENT_BYTES:
                raise LLMProviderError("Ollama returned tool arguments exceeding safety limits.")
            try:
                arguments = loads_strict_model_json(arguments)
            except (json.JSONDecodeError, ValueError) as exc:
                raise LLMProviderError("Ollama returned invalid JSON tool arguments.") from exc
        _validate_tool_arguments(arguments)
        return CognitiveToolCall(
            name=name,
            arguments=arguments,
            call_id=getattr(tool_call, "id", None),
        )
