"""Bounded provider-neutral cognition payloads for the Core worker SDK."""
from __future__ import annotations

import json
from math import isfinite
from typing import Mapping

from sofia.sdk.cognition_model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)


MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 262_144
MAX_MESSAGES = 128
MAX_TOOLS = 64
MAX_TOOL_CALLS = 32


def _json(value: object, depth: int = 0) -> object:
    if depth > 16:
        raise ValueError("cognition JSON exceeds nesting limit")
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not isfinite(value):
            raise ValueError("cognition JSON contains nonfinite number")
        return value
    if isinstance(value, (list, tuple)):
        return [_json(item, depth + 1) for item in value]
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("cognition JSON keys must be nonempty strings")
            result[key] = _json(item, depth + 1)
        return result
    raise ValueError("cognition payload contains a non-JSON value")


def _encode(document: Mapping[str, object], maximum: int) -> bytes:
    try:
        value = json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("cognition payload is not canonical JSON") from exc
    if len(value) > maximum:
        raise ValueError("cognition payload exceeds size limit")
    return value


def _decode(payload: bytes, maximum: int) -> Mapping[str, object]:
    if not isinstance(payload, bytes) or len(payload) > maximum:
        raise ValueError("cognition payload exceeds size limit")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cognition payload is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("cognition payload must be an object")
    return value


def encode_request(request: CognitiveRequest) -> bytes:
    if not isinstance(request, CognitiveRequest):
        raise TypeError("request must be CognitiveRequest")
    if len(request.messages) > MAX_MESSAGES or len(request.tools) > MAX_TOOLS:
        raise ValueError("cognition request exceeds item limits")
    return _encode({
        "schema": "sofia.core.cognition.request.v1",
        "messages": [{
            "role": item.role.value, "content": item.content,
            "tool_calls": [{"name": call.name, "arguments": _json(call.arguments),
                            "call_id": call.call_id} for call in item.tool_calls],
            "tool_call_id": item.tool_call_id,
        } for item in request.messages],
        "tools": [{"name": item.name, "description": item.description,
                   "parameters": _json(item.parameters)} for item in request.tools],
        "allow_tools": request.allow_tools,
        "capability_allowlist": (
            None if request.capability_allowlist is None
            else list(request.capability_allowlist)
        ),
        "route_hint": request.route_hint,
    }, MAX_REQUEST_BYTES)


def decode_request(payload: bytes) -> CognitiveRequest:
    value = _decode(payload, MAX_REQUEST_BYTES)
    required = {"schema", "messages", "tools", "allow_tools",
                "capability_allowlist", "route_hint"}
    if set(value) != required or value["schema"] != "sofia.core.cognition.request.v1":
        raise ValueError("unsupported cognition request schema")
    messages = value["messages"]
    tools = value["tools"]
    allowlist = value["capability_allowlist"]
    if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
        raise ValueError("invalid cognition messages")
    if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
        raise ValueError("invalid cognition tools")
    if allowlist is not None and not isinstance(allowlist, list):
        raise ValueError("invalid capability allowlist")
    def call(item: object) -> CognitiveToolCall:
        if not isinstance(item, dict) or set(item) != {"name", "arguments", "call_id"}:
            raise ValueError("invalid cognitive tool call")
        return CognitiveToolCall(item["name"], item["arguments"], item["call_id"])
    def message(item: object) -> CognitiveMessage:
        if not isinstance(item, dict) or set(item) != {
            "role", "content", "tool_calls", "tool_call_id"
        } or not isinstance(item["tool_calls"], list):
            raise ValueError("invalid cognitive message")
        return CognitiveMessage(
            CognitiveRole(item["role"]), item["content"],
            tuple(call(raw) for raw in item["tool_calls"]), item["tool_call_id"],
        )
    def tool(item: object) -> CognitiveToolDefinition:
        if not isinstance(item, dict) or set(item) != {"name", "description", "parameters"}:
            raise ValueError("invalid cognitive tool definition")
        return CognitiveToolDefinition(item["name"], item["description"], item["parameters"])
    return CognitiveRequest(
        messages=tuple(message(item) for item in messages),
        tools=tuple(tool(item) for item in tools),
        allow_tools=value["allow_tools"],
        capability_allowlist=(None if allowlist is None else tuple(allowlist)),
        route_hint=value["route_hint"],
    )


def encode_response(response: CognitiveResponse) -> bytes:
    if not isinstance(response, CognitiveResponse):
        raise TypeError("response must be CognitiveResponse")
    if len(response.tool_calls) > MAX_TOOL_CALLS:
        raise ValueError("cognition response exceeds tool-call limit")
    return _encode({
        "schema": "sofia.core.cognition.response.v1",
        "content": response.content,
        "tool_calls": [{"name": item.name, "arguments": _json(item.arguments),
                        "call_id": item.call_id} for item in response.tool_calls],
        "evidence_refs": list(response.evidence_refs),
    }, MAX_RESPONSE_BYTES)


def decode_response(payload: bytes) -> CognitiveResponse:
    value = _decode(payload, MAX_RESPONSE_BYTES)
    if set(value) != {"schema", "content", "tool_calls", "evidence_refs"} or (
        value["schema"] != "sofia.core.cognition.response.v1"
    ):
        raise ValueError("unsupported cognition response schema")
    calls = value["tool_calls"]
    evidence = value["evidence_refs"]
    if not isinstance(calls, list) or len(calls) > MAX_TOOL_CALLS or not isinstance(evidence, list):
        raise ValueError("invalid cognition response")
    result: list[CognitiveToolCall] = []
    for item in calls:
        if not isinstance(item, dict) or set(item) != {"name", "arguments", "call_id"}:
            raise ValueError("invalid cognitive response tool call")
        result.append(CognitiveToolCall(item["name"], item["arguments"], item["call_id"]))
    return CognitiveResponse(value["content"], tuple(result), tuple(evidence))
