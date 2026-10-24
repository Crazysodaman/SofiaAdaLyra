"""Least-privilege state facades exposed by Platform to isolated workers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .contracts import AuthorityProjection, ComponentEndpoint


@dataclass(frozen=True, slots=True)
class StateProjection:
    namespace: str
    key: str
    revision: int
    value_digest: str
    value: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.namespace or len(self.namespace) > 128:
            raise ValueError("namespace must be bounded")
        if not self.key or len(self.key) > 256:
            raise ValueError("key must be bounded")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        if len(self.value_digest) != 64 or any(
            char not in "0123456789abcdef" for char in self.value_digest
        ):
            raise ValueError("value_digest must be SHA-256")
        if not isinstance(self.value, Mapping):
            raise TypeError("value must be a mapping")


class StateReadFacade(Protocol):
    """Read projections only; implementations never expose SQLite handles."""

    def read_projection(
        self,
        *,
        worker: ComponentEndpoint,
        authority: AuthorityProjection,
        namespace: str,
        key: str,
    ) -> StateProjection | None: ...


class StateWriteFacade(Protocol):
    """Platform-owned CAS request; the worker never becomes a state writer."""

    def compare_and_set(
        self,
        *,
        worker: ComponentEndpoint,
        authority: AuthorityProjection,
        namespace: str,
        key: str,
        expected_revision: int | None,
        value: Mapping[str, object],
    ) -> StateProjection: ...
