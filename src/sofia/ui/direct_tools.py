"""Authenticated owner-direct tool surface for the local desktop client.

Selecting a tool here replaces model tool *selection*.  It never replaces the
canonical capability gateway, permission policy, or exact approval verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sofia.capability.model import CapabilityResult
from sofia.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.cognition.tools import CognitiveToolDispatcher
from sofia.safe.permissions import (
    PermissionLevel,
    PrivacyClass,
    capability_permission_policy,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID, local_sparks_principal


@dataclass(frozen=True, slots=True)
class DirectToolSpec:
    tool_name: str
    capability_name: str
    description: str
    parameter_schema: dict[str, Any]
    permission_level: PermissionLevel
    privacy: PrivacyClass


@dataclass(frozen=True, slots=True)
class DirectToolOutcome:
    action_content: str
    result: CapabilityResult
    response: CognitiveResponse


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) in (int, float)
    if expected == "boolean":
        return type(value) is bool
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def validate_tool_parameters(
    parameters: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Validate the bounded JSON-schema subset used by Sofía tool bindings."""
    if not isinstance(parameters, dict):
        raise TypeError("tool parameters must be a JSON object")
    if not isinstance(schema, dict) or schema.get("type", "object") != "object":
        raise ValueError("tool binding must use an object parameter schema")
    properties = schema.get("properties", {})
    required = schema.get("required", ())
    if not isinstance(properties, dict) or not isinstance(required, (list, tuple)):
        raise ValueError("tool binding has an invalid parameter schema")
    missing = tuple(name for name in required if name not in parameters)
    if missing:
        raise ValueError("missing required parameter(s): " + ", ".join(missing))
    if schema.get("additionalProperties") is False:
        unknown = tuple(sorted(set(parameters) - set(properties)))
        if unknown:
            raise ValueError("unknown parameter(s): " + ", ".join(unknown))
    for name, value in parameters.items():
        rule = properties.get(name)
        if not isinstance(rule, dict):
            continue
        expected = rule.get("type")
        if isinstance(expected, str) and not _matches_type(value, expected):
            raise ValueError(f"parameter {name!r} must be {expected}")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"parameter {name!r} is not an allowed value")
        if type(value) in (int, float):
            if "minimum" in rule and value < rule["minimum"]:
                raise ValueError(f"parameter {name!r} is below its minimum")
            if "maximum" in rule and value > rule["maximum"]:
                raise ValueError(f"parameter {name!r} is above its maximum")
        if isinstance(value, list) and isinstance(rule.get("items"), dict):
            item_type = rule["items"].get("type")
            if isinstance(item_type, str) and any(
                not _matches_type(item, item_type) for item in value
            ):
                raise ValueError(
                    f"parameter {name!r} must contain only {item_type} values"
                )


class OwnerDirectToolService:
    """Run an explicitly selected tool for the authenticated local owner."""

    def __init__(self, application) -> None:
        runtime = getattr(application, "runtime", None)
        conversation = getattr(application, "conversation", None)
        dispatcher = getattr(
            getattr(runtime, "cognitive_system", None),
            "tool_dispatcher",
            None,
        )
        if not isinstance(dispatcher, CognitiveToolDispatcher):
            raise RuntimeError("application does not expose cognitive tools")
        if not callable(
            getattr(conversation, "respond_to_owner_tool_result", None)
        ):
            raise RuntimeError("application conversation lacks owner tool responses")
        self._dispatcher = dispatcher
        self._conversation = conversation
        self._principal = local_sparks_principal()

    def specs(self) -> tuple[DirectToolSpec, ...]:
        result = []
        for binding in self._dispatcher.bindings:
            policy = capability_permission_policy(binding.capability_name)
            result.append(
                DirectToolSpec(
                    tool_name=binding.definition.name,
                    capability_name=binding.capability_name,
                    description=binding.definition.description,
                    parameter_schema=binding.definition.parameters,
                    permission_level=policy.level,
                    privacy=policy.privacy,
                )
            )
        return tuple(sorted(result, key=lambda item: item.tool_name))

    def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        *,
        principal: PrincipalContext | None = None,
    ) -> DirectToolOutcome:
        selected_principal = self._principal if principal is None else principal
        if (
            selected_principal.principal_id != SPARKS_PRINCIPAL_ID
            or selected_principal.audience_kind is not AudienceKind.PRIVATE
        ):
            raise PermissionError(
                "owner-direct tools require authenticated Sparks private context"
            )
        binding = next(
            (
                item
                for item in self._dispatcher.bindings
                if item.definition.name == tool_name
            ),
            None,
        )
        if binding is None:
            raise KeyError(f"unknown tool: {tool_name}")
        validate_tool_parameters(parameters, binding.definition.parameters)
        call = CognitiveToolCall(
            name=tool_name,
            arguments=dict(parameters),
            call_id=f"owner-direct:{uuid4()}",
        )
        result = self._dispatcher.dispatch(call, principal=selected_principal)
        formatted = self._dispatcher.format_result(call, result)
        action_content = f"Owner-direct private tool: {tool_name}"
        response = self._conversation.respond_to_owner_tool_result(
            action_content=action_content,
            formatted_result=formatted,
            principal=selected_principal,
            channel="desktop",
        )
        return DirectToolOutcome(action_content, result, response)
