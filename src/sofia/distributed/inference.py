"""Bounded wire contracts for remote cognitive inference over trusted Fleet links.

This module serializes cognition only. It cannot execute tools, grant authority,
open sockets, choose a Fleet node, or authenticate a peer. Remote tool calls are
returned as data for the authoritative Sofía runtime to evaluate locally.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from typing import Any, Mapping
from uuid import UUID

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.config.model import ProviderConfiguration


WIRE_VERSION = 1
MAX_MESSAGES = 128
MAX_TOOLS = 64
MAX_TOOL_CALLS = 32
MAX_CONTENT_BYTES = 131_072
MAX_DESCRIPTION_BYTES = 16_384
MAX_JSON_DEPTH = 16
MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 262_144


class RemoteInferenceContractError(ValueError):
    """A remote inference payload is malformed or exceeds its bounded contract."""


def _bounded_text(
    value: Any,
    label: str,
    *,
    maximum: int,
    allow_empty: bool = True,
) -> str:
    if not isinstance(value, str):
        raise RemoteInferenceContractError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise RemoteInferenceContractError(f"{label} must be nonempty")
    if len(value.encode("utf-8")) > maximum:
        raise RemoteInferenceContractError(f"{label} exceeds {maximum} bytes")
    if "\x00" in value:
        raise RemoteInferenceContractError(f"{label} contains a NUL byte")
    return value


def _json_value(value: Any, *, label: str, depth: int = 0) -> Any:
    if depth > MAX_JSON_DEPTH:
        raise RemoteInferenceContractError(
            f"{label} exceeds maximum JSON nesting depth"
        )
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not isfinite(value):
            raise RemoteInferenceContractError(f"{label} contains nonfinite float")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _json_value(item, label=label, depth=depth + 1)
            for item in value
        ]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise RemoteInferenceContractError(
                    f"{label} object keys must be nonempty strings"
                )
            result[key] = _json_value(
                item,
                label=label,
                depth=depth + 1,
            )
        return result
    raise RemoteInferenceContractError(
        f"{label} contains a non-JSON value"
    )


def _encoded_size(payload: Any, *, label: str, maximum: int) -> None:
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RemoteInferenceContractError(
            f"{label} is not valid JSON"
        ) from exc
    if len(raw) > maximum:
        raise RemoteInferenceContractError(
            f"{label} exceeds {maximum} bytes"
        )


def _exact_keys(
    payload: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    label: str,
) -> None:
    keys = frozenset(payload)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise RemoteInferenceContractError(
            f"{label} is missing: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RemoteInferenceContractError(
            f"{label} has unsupported fields: {', '.join(sorted(unknown))}"
        )


def _tool_call_to_payload(call: CognitiveToolCall) -> dict[str, Any]:
    return {
        "name": _bounded_text(
            call.name,
            "tool call name",
            maximum=256,
            allow_empty=False,
        ),
        "arguments": _json_value(
            call.arguments,
            label="tool call arguments",
        ),
        "call_id": (
            None
            if call.call_id is None
            else _bounded_text(
                call.call_id,
                "tool call id",
                maximum=512,
                allow_empty=False,
            )
        ),
    }


def _tool_call_from_payload(payload: Any) -> CognitiveToolCall:
    if not isinstance(payload, Mapping):
        raise RemoteInferenceContractError("tool call must be an object")
    _exact_keys(
        payload,
        required=frozenset({"name", "arguments", "call_id"}),
        label="tool call",
    )
    name = _bounded_text(
        payload["name"],
        "tool call name",
        maximum=256,
        allow_empty=False,
    )
    arguments = _json_value(
        payload["arguments"],
        label="tool call arguments",
    )
    if not isinstance(arguments, dict):
        raise RemoteInferenceContractError(
            "tool call arguments must be an object"
        )
    call_id = payload["call_id"]
    if call_id is not None:
        call_id = _bounded_text(
            call_id,
            "tool call id",
            maximum=512,
            allow_empty=False,
        )
    return CognitiveToolCall(
        name=name,
        arguments=arguments,
        call_id=call_id,
    )


def _message_to_payload(message: CognitiveMessage) -> dict[str, Any]:
    if len(message.tool_calls) > MAX_TOOL_CALLS:
        raise RemoteInferenceContractError(
            f"message has more than {MAX_TOOL_CALLS} tool calls"
        )
    return {
        "role": message.role.value,
        "content": _bounded_text(
            message.content,
            "message content",
            maximum=MAX_CONTENT_BYTES,
        ),
        "tool_calls": [
            _tool_call_to_payload(call)
            for call in message.tool_calls
        ],
        "tool_call_id": (
            None
            if message.tool_call_id is None
            else _bounded_text(
                message.tool_call_id,
                "tool_call_id",
                maximum=512,
                allow_empty=False,
            )
        ),
    }


def _message_from_payload(payload: Any) -> CognitiveMessage:
    if not isinstance(payload, Mapping):
        raise RemoteInferenceContractError("message must be an object")
    _exact_keys(
        payload,
        required=frozenset(
            {"role", "content", "tool_calls", "tool_call_id"}
        ),
        label="message",
    )
    try:
        role = CognitiveRole(str(payload["role"]))
    except ValueError as exc:
        raise RemoteInferenceContractError(
            "message role is unsupported"
        ) from exc
    content = _bounded_text(
        payload["content"],
        "message content",
        maximum=MAX_CONTENT_BYTES,
    )
    raw_calls = payload["tool_calls"]
    if not isinstance(raw_calls, list) or len(raw_calls) > MAX_TOOL_CALLS:
        raise RemoteInferenceContractError(
            f"message tool_calls must be a list of at most {MAX_TOOL_CALLS}"
        )
    calls = tuple(_tool_call_from_payload(item) for item in raw_calls)
    tool_call_id = payload["tool_call_id"]
    if tool_call_id is not None:
        tool_call_id = _bounded_text(
            tool_call_id,
            "tool_call_id",
            maximum=512,
            allow_empty=False,
        )
    try:
        return CognitiveMessage(
            role=role,
            content=content,
            tool_calls=calls,
            tool_call_id=tool_call_id,
        )
    except (TypeError, ValueError) as exc:
        raise RemoteInferenceContractError(
            "message violates cognitive message rules"
        ) from exc


def _tool_definition_to_payload(
    tool: CognitiveToolDefinition,
) -> dict[str, Any]:
    return {
        "name": _bounded_text(
            tool.name,
            "tool definition name",
            maximum=256,
            allow_empty=False,
        ),
        "description": _bounded_text(
            tool.description,
            "tool definition description",
            maximum=MAX_DESCRIPTION_BYTES,
            allow_empty=False,
        ),
        "parameters": _json_value(
            tool.parameters,
            label="tool definition parameters",
        ),
    }


def _tool_definition_from_payload(payload: Any) -> CognitiveToolDefinition:
    if not isinstance(payload, Mapping):
        raise RemoteInferenceContractError(
            "tool definition must be an object"
        )
    _exact_keys(
        payload,
        required=frozenset({"name", "description", "parameters"}),
        label="tool definition",
    )
    parameters = _json_value(
        payload["parameters"],
        label="tool definition parameters",
    )
    if not isinstance(parameters, dict):
        raise RemoteInferenceContractError(
            "tool definition parameters must be an object"
        )
    try:
        return CognitiveToolDefinition(
            name=_bounded_text(
                payload["name"],
                "tool definition name",
                maximum=256,
                allow_empty=False,
            ),
            description=_bounded_text(
                payload["description"],
                "tool definition description",
                maximum=MAX_DESCRIPTION_BYTES,
                allow_empty=False,
            ),
            parameters=parameters,
        )
    except (TypeError, ValueError) as exc:
        raise RemoteInferenceContractError(
            "tool definition violates cognitive tool rules"
        ) from exc


def _provider_to_payload(
    provider: ProviderConfiguration,
) -> dict[str, Any]:
    return {
        "provider": _bounded_text(
            provider.provider,
            "provider name",
            maximum=128,
            allow_empty=False,
        ),
        "model": _bounded_text(
            provider.model,
            "model name",
            maximum=512,
            allow_empty=False,
        ),
        "temperature": provider.temperature,
        "seed": provider.seed,
        "context_size": provider.context_size,
        "thinking": provider.thinking,
    }


def _provider_from_payload(payload: Any) -> ProviderConfiguration:
    if not isinstance(payload, Mapping):
        raise RemoteInferenceContractError("provider must be an object")
    _exact_keys(
        payload,
        required=frozenset(
            {
                "provider",
                "model",
                "temperature",
                "seed",
                "context_size",
                "thinking",
            }
        ),
        label="provider",
    )
    try:
        return ProviderConfiguration(
            provider=_bounded_text(
                payload["provider"],
                "provider name",
                maximum=128,
                allow_empty=False,
            ),
            model=_bounded_text(
                payload["model"],
                "model name",
                maximum=512,
                allow_empty=False,
            ),
            temperature=payload["temperature"],
            seed=payload["seed"],
            context_size=payload["context_size"],
            thinking=payload["thinking"],
        )
    except (TypeError, ValueError) as exc:
        raise RemoteInferenceContractError(
            "provider configuration is invalid"
        ) from exc


@dataclass(frozen=True, slots=True)
class RemoteInferenceRequest:
    request_id: UUID
    node_id: UUID
    grant_id: UUID
    provider: ProviderConfiguration
    request: CognitiveRequest

    def __post_init__(self) -> None:
        for value, label in (
            (self.request_id, "request_id"),
            (self.node_id, "node_id"),
            (self.grant_id, "grant_id"),
        ):
            if not isinstance(value, UUID):
                raise TypeError(f"{label} must be a UUID")
        if not isinstance(self.provider, ProviderConfiguration):
            raise TypeError("provider must be ProviderConfiguration")
        if not isinstance(self.request, CognitiveRequest):
            raise TypeError("request must be CognitiveRequest")
        if len(self.request.messages) > MAX_MESSAGES:
            raise RemoteInferenceContractError(
                f"request has more than {MAX_MESSAGES} messages"
            )
        if len(self.request.tools) > MAX_TOOLS:
            raise RemoteInferenceContractError(
                f"request has more than {MAX_TOOLS} tools"
            )
        _encoded_size(
            self.to_payload(check_size=False),
            label="remote inference request",
            maximum=MAX_REQUEST_BYTES,
        )

    def to_payload(
        self,
        *,
        check_size: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "version": WIRE_VERSION,
            "request_id": str(self.request_id),
            "node_id": str(self.node_id),
            "grant_id": str(self.grant_id),
            "provider": _provider_to_payload(self.provider),
            "request": {
                "messages": [
                    _message_to_payload(message)
                    for message in self.request.messages
                ],
                "tools": [
                    _tool_definition_to_payload(tool)
                    for tool in self.request.tools
                ],
                "allow_tools": self.request.allow_tools,
            },
        }
        if check_size:
            _encoded_size(
                payload,
                label="remote inference request",
                maximum=MAX_REQUEST_BYTES,
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        payload: Any,
    ) -> "RemoteInferenceRequest":
        if not isinstance(payload, Mapping):
            raise RemoteInferenceContractError(
                "remote inference request must be an object"
            )
        _exact_keys(
            payload,
            required=frozenset(
                {
                    "version",
                    "request_id",
                    "node_id",
                    "grant_id",
                    "provider",
                    "request",
                }
            ),
            label="remote inference request",
        )
        if payload["version"] != WIRE_VERSION:
            raise RemoteInferenceContractError(
                "unsupported remote inference wire version"
            )
        raw_request = payload["request"]
        if not isinstance(raw_request, Mapping):
            raise RemoteInferenceContractError(
                "request field must be an object"
            )
        _exact_keys(
            raw_request,
            required=frozenset(
                {"messages", "tools", "allow_tools"}
            ),
            label="cognitive request",
        )
        messages = raw_request["messages"]
        tools = raw_request["tools"]
        allow_tools = raw_request["allow_tools"]
        if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
            raise RemoteInferenceContractError(
                f"messages must be a list of at most {MAX_MESSAGES}"
            )
        if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
            raise RemoteInferenceContractError(
                f"tools must be a list of at most {MAX_TOOLS}"
            )
        if type(allow_tools) is not bool:
            raise RemoteInferenceContractError(
                "allow_tools must be a boolean"
            )
        try:
            request_id = UUID(str(payload["request_id"]))
            node_id = UUID(str(payload["node_id"]))
            grant_id = UUID(str(payload["grant_id"]))
        except (TypeError, ValueError) as exc:
            raise RemoteInferenceContractError(
                "remote inference IDs must be UUIDs"
            ) from exc
        request = CognitiveRequest(
            messages=tuple(
                _message_from_payload(item)
                for item in messages
            ),
            tools=tuple(
                _tool_definition_from_payload(item)
                for item in tools
            ),
            allow_tools=allow_tools,
        )
        result = cls(
            request_id=request_id,
            node_id=node_id,
            grant_id=grant_id,
            provider=_provider_from_payload(payload["provider"]),
            request=request,
        )
        _encoded_size(
            result.to_payload(check_size=False),
            label="remote inference request",
            maximum=MAX_REQUEST_BYTES,
        )
        return result


@dataclass(frozen=True, slots=True)
class RemoteInferenceResponse:
    request_id: UUID
    node_id: UUID
    response: CognitiveResponse

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise TypeError("request_id must be a UUID")
        if not isinstance(self.node_id, UUID):
            raise TypeError("node_id must be a UUID")
        if not isinstance(self.response, CognitiveResponse):
            raise TypeError("response must be CognitiveResponse")
        if len(self.response.tool_calls) > MAX_TOOL_CALLS:
            raise RemoteInferenceContractError(
                f"response has more than {MAX_TOOL_CALLS} tool calls"
            )
        _encoded_size(
            self.to_payload(check_size=False),
            label="remote inference response",
            maximum=MAX_RESPONSE_BYTES,
        )

    def to_payload(
        self,
        *,
        check_size: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "version": WIRE_VERSION,
            "request_id": str(self.request_id),
            "node_id": str(self.node_id),
            "response": {
                "content": _bounded_text(
                    self.response.content,
                    "response content",
                    maximum=MAX_CONTENT_BYTES,
                ),
                "tool_calls": [
                    _tool_call_to_payload(call)
                    for call in self.response.tool_calls
                ],
            },
        }
        if check_size:
            _encoded_size(
                payload,
                label="remote inference response",
                maximum=MAX_RESPONSE_BYTES,
            )
        return payload

    @classmethod
    def from_payload(
        cls,
        payload: Any,
    ) -> "RemoteInferenceResponse":
        if not isinstance(payload, Mapping):
            raise RemoteInferenceContractError(
                "remote inference response must be an object"
            )
        _exact_keys(
            payload,
            required=frozenset(
                {"version", "request_id", "node_id", "response"}
            ),
            label="remote inference response",
        )
        if payload["version"] != WIRE_VERSION:
            raise RemoteInferenceContractError(
                "unsupported remote inference wire version"
            )
        raw_response = payload["response"]
        if not isinstance(raw_response, Mapping):
            raise RemoteInferenceContractError(
                "response field must be an object"
            )
        _exact_keys(
            raw_response,
            required=frozenset({"content", "tool_calls"}),
            label="cognitive response",
        )
        raw_calls = raw_response["tool_calls"]
        if not isinstance(raw_calls, list) or len(raw_calls) > MAX_TOOL_CALLS:
            raise RemoteInferenceContractError(
                f"response tool_calls must be a list of at most {MAX_TOOL_CALLS}"
            )
        try:
            request_id = UUID(str(payload["request_id"]))
            node_id = UUID(str(payload["node_id"]))
        except (TypeError, ValueError) as exc:
            raise RemoteInferenceContractError(
                "remote inference response IDs must be UUIDs"
            ) from exc
        result = cls(
            request_id=request_id,
            node_id=node_id,
            response=CognitiveResponse(
                content=_bounded_text(
                    raw_response["content"],
                    "response content",
                    maximum=MAX_CONTENT_BYTES,
                ),
                tool_calls=tuple(
                    _tool_call_from_payload(item)
                    for item in raw_calls
                ),
            ),
        )
        _encoded_size(
            result.to_payload(check_size=False),
            label="remote inference response",
            maximum=MAX_RESPONSE_BYTES,
        )
        return result
