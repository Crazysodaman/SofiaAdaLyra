"""Storage boundary for one logical authoritative Sofía State Plane."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sofia.state_plane.model import StateKey, StateRecord


class StatePlaneError(RuntimeError):
    """Base error for State Plane operations."""


class StateConflictError(StatePlaneError):
    """The caller's expected revision no longer matches authoritative state."""


class StatePlane(ABC):
    """Backend-neutral compare-and-set State Plane interface.

    Package code owns serialization and schema meaning. A backend owns atomic
    version checks and durability. No generic method exposes raw database
    credentials, arbitrary SQL, or unscoped delete authority.
    """

    @abstractmethod
    def get(self, key: StateKey) -> StateRecord | None:
        raise NotImplementedError

    @abstractmethod
    def compare_and_set(
        self,
        record: StateRecord,
        *,
        expected_revision: int | None,
    ) -> StateRecord:
        """Store a new revision atomically.

        expected_revision=None means the key must not already exist. Otherwise
        it must exactly match the currently authoritative revision.
        """
        raise NotImplementedError

    @abstractmethod
    def list_namespace(
        self,
        namespace: str,
    ) -> tuple[StateRecord, ...]:
        raise NotImplementedError
