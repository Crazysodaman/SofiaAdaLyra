from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sofia.platform.state.model import StateKey, StateRecord


class StatePlaneConflictError(RuntimeError):
    """Raised when optimistic revision checks fail."""


@dataclass(frozen=True, slots=True)
class StateWrite:
    """One compare-and-swap mutation in an atomic State Plane transaction."""

    record: StateRecord
    expected_revision: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.record, StateRecord):
            raise TypeError("record must be StateRecord")
        if self.expected_revision is not None and (
            type(self.expected_revision) is not int
            or self.expected_revision < 1
        ):
            raise ValueError(
                "expected_revision must be None or a positive integer"
            )


class StatePlane(ABC):
    """
    Backend-neutral boundary for authoritative Sofía state.

    Implementations may use SQLite, PostgreSQL, or another reviewed backend,
    but callers address logical records rather than backend-specific tables.
    """

    @abstractmethod
    def read(self, key: StateKey) -> StateRecord | None:
        raise NotImplementedError

    @abstractmethod
    def write(
        self,
        record: StateRecord,
        *,
        expected_revision: int | None,
    ) -> StateRecord:
        """
        Persist with optimistic revision control.

        expected_revision=None means the caller expects the key not to exist.
        Existing records must never be overwritten silently.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        key: StateKey,
        *,
        expected_revision: int,
    ) -> None:
        """Delete exactly one known revision or fail on concurrent change."""
        raise NotImplementedError

    @abstractmethod
    def list_namespace(
        self,
        namespace: str,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[StateRecord, ...]:
        raise NotImplementedError

    def list_scopes(self, namespace: str) -> tuple[tuple[str | None, str | None], ...]:
        """Privileged content-free partition enumeration for host maintenance.

        Backends that cannot support administrative scope enumeration must
        fail closed. This method returns scope identifiers, never record data.
        """
        raise NotImplementedError("State Plane backend does not enumerate scopes")

    def write_transaction(
        self, writes: tuple[StateWrite, ...],
    ) -> tuple[StateRecord, ...]:
        """Atomically apply related CAS writes when the backend supports it."""
        raise NotImplementedError(
            "State Plane backend does not support atomic batches"
        )
