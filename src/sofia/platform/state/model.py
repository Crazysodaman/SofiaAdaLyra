from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class StateClass(Enum):
    """Persistence class used by the shared Sofía State Plane."""

    SHARED_AUTHORITATIVE = "shared_authoritative"
    PROTECTED = "protected"
    SECRET_REFERENCE = "secret_reference"
    IMMUTABLE_ARTIFACT = "immutable_artifact"
    LOCAL_EPHEMERAL = "local_ephemeral"


@dataclass(frozen=True, slots=True)
class StateKey:
    """Stable logical key for one State Plane record."""

    namespace: str
    key: str
    principal_id: str | None = None
    audience: str | None = None

    def __post_init__(self) -> None:
        for name, value in (("namespace", self.namespace), ("key", self.key)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")

        for name, value in (
            ("principal_id", self.principal_id),
            ("audience", self.audience),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{name} must be None or a nonempty string")


@dataclass(frozen=True, slots=True)
class StateRecord:
    """Backend-neutral immutable State Plane value envelope."""

    key: StateKey
    state_class: StateClass
    revision: int
    value: bytes
    updated_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, StateKey):
            raise TypeError("key must be a StateKey")
        if not isinstance(self.state_class, StateClass):
            raise TypeError("state_class must be a StateClass")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.value, bytes):
            raise TypeError("value must be bytes")
        if not isinstance(self.updated_at, datetime):
            raise TypeError("updated_at must be a datetime")
        if (
            self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a nonempty string")
