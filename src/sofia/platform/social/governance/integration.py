"""Narrow adapter seams between governance and chat/STOP/authorization.

The governance engine never imports chat internals.  Hosts supply a small
admission object, a STOP probe and an optional room-kind guard.  This keeps one
authenticated Core UUID as the only vote identity while leaving consequential
Platform authority in the existing SAFE/RUN/Platform owners.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable
from uuid import UUID

from sofia.platform.social.governance.contracts import (
    GovernanceDenied,
    GovernanceGroup,
    Resolution,
)


@runtime_checkable
class CoreAdmission(Protocol):
    """Authenticated Core registration and revision facts supplied by a host."""

    def is_active_approved(self, core_id: UUID) -> bool:
        ...

    def generation(self, core_id: UUID) -> int | None:
        ...

    def federation_generation(self, core_id: UUID) -> int | None:
        ...


@runtime_checkable
class StopSeam(Protocol):
    def is_operator_stopped(self) -> bool:
        ...


@runtime_checkable
class RoomKindSource(Protocol):
    def room_kind(self, room_id: str) -> str | None:
        ...


class DenyAllAdmission:
    """Fail-closed default when no host admission seam is configured."""

    def is_active_approved(self, core_id: UUID) -> bool:
        return False

    def generation(self, core_id: UUID) -> int | None:
        return None

    def federation_generation(self, core_id: UUID) -> int | None:
        return None


class NotStopped:
    def is_operator_stopped(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class StaticAdmission:
    """Small explicit registry for disposable source tests and fixtures."""

    active_core_ids: frozenset[UUID]
    generations: Mapping[UUID, int]
    federation_generations: Mapping[UUID, int]

    def __init__(
        self,
        active_core_ids,
        *,
        generations: Mapping[UUID, int] | None = None,
        federation_generations: Mapping[UUID, int] | None = None,
    ) -> None:
        object.__setattr__(self, "active_core_ids", frozenset(active_core_ids))
        object.__setattr__(self, "generations", dict(generations or {}))
        object.__setattr__(
            self, "federation_generations", dict(federation_generations or {})
        )

    def is_active_approved(self, core_id: UUID) -> bool:
        return core_id in self.active_core_ids

    def generation(self, core_id: UUID) -> int | None:
        return self.generations.get(core_id)

    def federation_generation(self, core_id: UUID) -> int | None:
        return self.federation_generations.get(core_id)


@dataclass(frozen=True, slots=True)
class StaticRoomKindSource:
    """Room-kind facts, usually projected from the chat room registry."""

    kinds: Mapping[str, str]

    def room_kind(self, room_id: str) -> str | None:
        return self.kinds.get(room_id)


@dataclass(frozen=True, slots=True)
class ProjectedDecision:
    """Redacted decision metadata safe for a private group room only."""

    group_id: UUID
    proposal_id: UUID
    resolution_id: UUID
    outcome: str
    summary: str


def project_resolution(
    *,
    resolution: Resolution,
    group: GovernanceGroup,
    destination_room_id: str,
    rooms: RoomKindSource,
) -> ProjectedDecision:
    """Project a readable decision without leaking ballot identities.

    General/public rooms and rooms outside the group's declared private rooms
    are denied.  This is a projection guard, not an authority grant.
    """
    if not isinstance(resolution, Resolution):
        raise TypeError("resolution must be Resolution")
    if not isinstance(group, GovernanceGroup):
        raise TypeError("group must be GovernanceGroup")
    if resolution.group_id != group.group_id:
        raise GovernanceDenied("resolution does not belong to this group")
    if destination_room_id not in group.room_ids:
        raise GovernanceDenied("destination room is outside the group audience")
    if rooms.room_kind(destination_room_id) != "private_group":
        raise GovernanceDenied(
            "group decisions cannot be broadcast into a general or public room"
        )
    return ProjectedDecision(
        group_id=group.group_id,
        proposal_id=resolution.proposal_id,
        resolution_id=resolution.resolution_id,
        outcome=resolution.outcome.value,
        summary=f"{resolution.outcome.value}; quorum {resolution.tally.quorum}; "
        f"submitted {resolution.tally.submitted}",
    )


class ChatGovernanceAdapter:
    """Use only public chat-engine identity reads for admission facts.

    The adapter intentionally exposes no room mutation, message send or
    administrative capability.  It is not a second writer and never edits chat
    state.
    """

    def __init__(self, chat) -> None:
        self._chat = chat

    def is_active_approved(self, core_id: UUID) -> bool:
        identity = self._chat.core_identity(str(core_id))
        if identity is None:
            return False
        return any(
            item.core_id == core_id for item in self._chat.core_identities()
        )

    def generation(self, core_id: UUID) -> int | None:
        identity = self._chat.core_identity(str(core_id))
        return None if identity is None else identity.generation

    def federation_generation(self, core_id: UUID) -> int | None:
        # Local chat rows do not carry a federation trust generation.  Absence
        # is reported honestly rather than fabricated.
        return None


class CallableStop:
    """Adapt an existing STOP callable without owning STOP state."""

    def __init__(self, stopped) -> None:
        if not callable(stopped):
            raise TypeError("stopped must be callable")
        self._stopped = stopped

    def is_operator_stopped(self) -> bool:
        return bool(self._stopped())


__all__ = [
    "CallableStop",
    "ChatGovernanceAdapter",
    "CoreAdmission",
    "DenyAllAdmission",
    "NotStopped",
    "ProjectedDecision",
    "RoomKindSource",
    "StaticAdmission",
    "StaticRoomKindSource",
    "StopSeam",
    "project_resolution",
]
