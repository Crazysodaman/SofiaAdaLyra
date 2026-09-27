from __future__ import annotations

from abc import ABC, abstractmethod

from sofia.state.model import StateKey, StateRecord


class StatePlaneConflictError(RuntimeError):
    """Raised when optimistic revision checks fail."""


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
    def list_namespace(
        self,
        namespace: str,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[StateRecord, ...]:
        raise NotImplementedError
