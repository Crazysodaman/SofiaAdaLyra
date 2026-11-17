"""Narrow adapters for host-owned STOP and delivery seams."""
from __future__ import annotations

from uuid import UUID

from sofia.platform.social.autonomy.contracts import (
    CoreIdentity,
    SocialAction,
    SocialDecision,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.social.autonomy.store import SocialAutonomyStore


class StoreProfileSource:
    """Default local read adapter; canonical owners can replace it."""

    def __init__(self, store: SocialAutonomyStore) -> None:
        if not isinstance(store, SocialAutonomyStore):
            raise TypeError("store must be SocialAutonomyStore")
        self._store = store

    def interests(self, *, core_id: UUID) -> tuple:
        return self._store.interests(core_id)

    def goals(self, *, core_id: UUID) -> tuple:
        return self._store.goals(core_id)

    def boundaries(self, *, core_id: UUID, peer_core_id: UUID | None) -> tuple:
        return self._store.boundaries(core_id, peer_core_id=peer_core_id)


class OperatorStopAdapter:
    """Expose the canonical SAFE operator STOP without copying its state."""

    def __init__(self, store: OperatorStopStore) -> None:
        if not isinstance(store, OperatorStopStore):
            raise TypeError("store must be OperatorStopStore")
        self._store = store

    def is_operator_stopped(self) -> bool:
        return self._store.current().active


class CallbackTransport:
    """Adapt an existing chat engine callable to the narrow transport seam."""

    def __init__(self, deliver) -> None:
        if not callable(deliver):
            raise TypeError("deliver must be callable")
        self._deliver = deliver

    def deliver(self, decision: SocialDecision) -> str | None:
        result = self._deliver(decision)
        return None if result is None else str(result)


class CallbackScheduler:
    """Adapt an existing event-driven inference scheduler to this seam."""

    def __init__(self, wake) -> None:
        if not callable(wake):
            raise TypeError("wake must be callable")
        self._wake = wake

    def wake(
        self,
        *,
        core_id: UUID,
        reason: str,
        due_at,
        event_id: str,
    ) -> None:
        self._wake(
            core_id=core_id,
            reason=reason,
            due_at=due_at,
            event_id=event_id,
        )


class AllowListAuthorization:
    """Minimal authorization adapter for tests and explicitly scoped hosts."""

    def __init__(
        self,
        allowed: set[tuple[UUID, SocialAction]] | None = None,
    ) -> None:
        self._allowed = allowed if allowed is not None else set()

    def authorize(
        self,
        *,
        core: CoreIdentity,
        action: SocialAction,
        room_id: str | None,
        target_core_id: UUID | None,
        audience: str | None,
    ) -> bool:
        return (core.core_id, action) in self._allowed
