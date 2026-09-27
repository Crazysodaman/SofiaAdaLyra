"""Typed records shared by State Plane backends and package adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class StateClass(str, Enum):
    SHARED_AUTHORITATIVE = "shared_authoritative"
    PROTECTED = "protected"
    SECRET_REFERENCE = "secret_reference"
    IMMUTABLE_ARTIFACT = "immutable_artifact"
    LOCAL_EPHEMERAL = "local_ephemeral"


class StateScope(str, Enum):
    GLOBAL = "global"
    PRINCIPAL = "principal"
    AUDIENCE = "audience"
    HOST = "host"


@dataclass(frozen=True, slots=True)
class StateKey:
    namespace: str
    name: str

    def __post_init__(self) -> None:
        _identifier(self.namespace, "namespace")
        _identifier(self.name, "name")

    @property
    def canonical(self) -> str:
        return f"{self.namespace}:{self.name}"


@dataclass(frozen=True, slots=True)
class StateRecord:
    """One versioned opaque record in the logical State Plane.

    Backends store bytes rather than Python objects so serialization, schema
    revision, ownership and compatibility stay explicit at package boundaries.
    """

    key: StateKey
    state_class: StateClass
    owner_package: str
    scope: StateScope
    revision: int
    schema_revision: int
    payload: bytes
    content_type: str = "application/json"
    principal_id: str | None = None
    audience_id: str | None = None
    host_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, StateKey):
            raise TypeError("key must be a StateKey")
        if not isinstance(self.state_class, StateClass):
            raise TypeError("state_class must be a StateClass")
        _identifier(self.owner_package, "owner_package")
        if not isinstance(self.scope, StateScope):
            raise TypeError("scope must be a StateScope")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if type(self.schema_revision) is not int or self.schema_revision < 1:
            raise ValueError("schema_revision must be a positive integer")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        if not isinstance(self.content_type, str) or not self.content_type.strip():
            raise ValueError("content_type must be non-empty")

        for label, value in (
            ("principal_id", self.principal_id),
            ("audience_id", self.audience_id),
            ("host_id", self.host_id),
        ):
            if value is not None:
                _identifier(value, label)

        if self.scope is StateScope.PRINCIPAL and self.principal_id is None:
            raise ValueError("principal-scoped state requires principal_id")
        if self.scope is StateScope.AUDIENCE and self.audience_id is None:
            raise ValueError("audience-scoped state requires audience_id")
        if self.scope is StateScope.HOST and self.host_id is None:
            raise ValueError("host-scoped state requires host_id")

        if self.state_class is StateClass.LOCAL_EPHEMERAL and (
            self.scope is not StateScope.HOST or self.host_id is None
        ):
            raise ValueError(
                "local ephemeral state must be explicitly host-scoped"
            )

    @property
    def payload_digest(self) -> str:
        return sha256(self.payload).hexdigest()
