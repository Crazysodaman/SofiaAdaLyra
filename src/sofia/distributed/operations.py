"""Engineering 22G: default-deny, bounded remote operations via injected transport.

There is deliberately NO production transport implementation or socket here.
RemoteTransport.authenticate MUST establish cryptographic peer identity and
pin proof-of-possession itself, not trust a caller-supplied boolean or key hash.
A fake transport proves orchestration only; it is not proof of secure networking.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from json import dumps
from math import isfinite
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from sofia.distributed.authorization import RemoteAuthorization
from sofia.distributed.capabilities import (
    CapabilityInventory, _aware, _identifier, inventory_is_current,
)
from sofia.distributed.identity import NodeEnrollment

Scalar = str | int | float | bool | None
_FORBIDDEN = frozenset({"command", "commands", "cmd", "shell", "script",
                       "executable", "argv", "arguments", "password", "token",
                       "secret", "private_key"})


@dataclass(frozen=True)
class RemoteOperationRequest:
    request_id: UUID
    node_id: UUID
    grant_id: UUID
    capability: str
    operation: str
    parameters: Mapping[str, Scalar]

    def __post_init__(self) -> None:
        for value in (self.request_id, self.node_id, self.grant_id):
            if not isinstance(value, UUID):
                raise TypeError("Remote request IDs must be UUIDs.")
        _identifier(self.capability, "Request capability")
        _identifier(self.operation, "Request operation")
        if not isinstance(self.parameters, Mapping):
            raise TypeError("Parameters must be a mapping.")
        frozen: dict[str, Scalar] = {}
        for key, value in self.parameters.items():
            _identifier(key, "Parameter key")
            if key.lower() in _FORBIDDEN:
                raise ValueError("Arbitrary execution and secret parameters are forbidden.")
            if type(value) not in (str, int, float, bool, type(None)):
                raise TypeError("Only bounded JSON scalar parameter values are accepted.")
            if type(value) is float and not isfinite(value):
                raise ValueError("Nonfinite parameter values are forbidden.")
            frozen[key] = value
        if len(dumps(frozen, ensure_ascii=False).encode("utf-8")) > 4096:
            raise ValueError("Remote parameters exceed 4096 bytes.")
        object.__setattr__(self, "parameters", MappingProxyType(frozen))


class RemoteOutcome(str, Enum):
    REPORTED_SUCCESS = "reported_success"
    REPORTED_FAILURE = "reported_failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RemoteOperationResult:
    """Remote-reported result; a success claim is not local independent proof."""

    request_id: UUID
    node_id: UUID
    outcome: RemoteOutcome
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID) or not isinstance(self.node_id, UUID):
            raise TypeError("Result identifiers must be UUIDs.")
        if not isinstance(self.outcome, RemoteOutcome):
            raise TypeError("Result outcome must be a RemoteOutcome.")
        if not isinstance(self.message, str):
            raise TypeError("Result message must be a string.")


class RemoteTransport(ABC):
    """Trusted *implementation* boundary; no transport shipped by Batch 22."""

    @abstractmethod
    def authenticate(self, enrollment: NodeEnrollment) -> bool:
        """Prove peer possession of enrolled key over an authenticated channel."""
        raise NotImplementedError

    @abstractmethod
    def discover(self, enrollment: NodeEnrollment) -> CapabilityInventory:
        """Obtain claims through that authenticated channel."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, enrollment: NodeEnrollment,
                request: RemoteOperationRequest) -> RemoteOperationResult:
        """Invoke only the explicitly named remote operation."""
        raise NotImplementedError


class RemoteOperationDenied(Exception):
    """Denied before executing a remote operation."""


class RemoteOperationUncertain(Exception):
    """The remote operation may have run; NEVER automatically retry."""


class DistributedGateway:
    """Orchestrates one-shot calls; no default transport and no auto-retry.

    Audit is in-memory and must NOT be considered durable production auditing.
    The transport MUST enforce authentication and per-node trust at its boundary.
    """

    def __init__(self, transport: RemoteTransport, authorization: RemoteAuthorization,
                 *, max_inventory_age: timedelta) -> None:
        if not isinstance(transport, RemoteTransport):
            raise TypeError("transport must implement RemoteTransport.")
        if not isinstance(authorization, RemoteAuthorization):
            raise TypeError("authorization must be RemoteAuthorization.")
        if not isinstance(max_inventory_age, timedelta) or max_inventory_age <= timedelta(0):
            raise ValueError("max_inventory_age must be positive.")
        self._transport = transport
        self._authorization = authorization
        self._max_age = max_inventory_age
        self._attempted: set[UUID] = set()
        self._events: list[tuple[UUID, str]] = []

    @property
    def audit_events(self) -> tuple[tuple[UUID, str], ...]:
        return tuple(self._events)

    def invoke(self, enrollment: NodeEnrollment, request: RemoteOperationRequest,
               *, now: datetime) -> RemoteOperationResult:
        _aware(now, "now")
        if not isinstance(enrollment, NodeEnrollment):
            raise TypeError("enrollment must be NodeEnrollment.")
        if not isinstance(request, RemoteOperationRequest):
            raise TypeError("request must be RemoteOperationRequest.")
        if request.node_id != enrollment.node.node_id:
            raise RemoteOperationDenied("Request node does not match enrollment.")
        if request.request_id in self._attempted:
            raise RemoteOperationDenied("Duplicate request ID: never retry implicitly.")
        if not self._authorization.permits(request.grant_id, node_id=request.node_id,
                                           capability=request.capability,
                                           operation=request.operation, now=now):
            self._events.append((request.request_id, "denied:no_grant"))
            raise RemoteOperationDenied("No active exact-scope human grant.")
        # Mark before any external call, so failed/uncertain calls cannot retry.
        self._attempted.add(request.request_id)
        self._events.append((request.request_id, "attempted"))
        try:
            if self._transport.authenticate(enrollment) is not True:
                raise RemoteOperationDenied("Peer authentication failed.")
            inventory = self._transport.discover(enrollment)
            if not isinstance(inventory, CapabilityInventory):
                raise RemoteOperationDenied("Invalid capability inventory.")
            if inventory.node_id != request.node_id or not inventory_is_current(
                inventory, now=now, max_age=self._max_age
            ):
                raise RemoteOperationDenied("Wrong-node, stale, or future capability inventory.")
            if not inventory.advertises(request.capability, request.operation):
                raise RemoteOperationDenied("Capability/operation is not advertised.")
        except RemoteOperationDenied:
            self._events.append((request.request_id, "denied:pre_execute"))
            raise
        except Exception as exc:
            self._events.append((request.request_id, "failed:pre_execute"))
            raise RemoteOperationDenied("Peer authentication/discovery failed.") from exc

        # External execution can succeed before an error is returned. No retry.
        try:
            result = self._transport.execute(enrollment, request)
        except Exception as exc:
            self._events.append((request.request_id, "uncertain:transport_error"))
            raise RemoteOperationUncertain("Remote outcome unknown; do not retry.") from exc
        if not isinstance(result, RemoteOperationResult) or (
            result.request_id != request.request_id or result.node_id != request.node_id
        ):
            self._events.append((request.request_id, "uncertain:invalid_result"))
            raise RemoteOperationUncertain("Mismatched remote result; do not retry.")
        self._events.append((request.request_id, f"reported:{result.outcome.value}"))
        return result
