"""Fail-closed federation errors.

Every rejection is explicit.  None of these exceptions grants authority or
implies that an unobserved peer resource does not exist.
"""
from __future__ import annotations


class FederationError(RuntimeError):
    """Base class for a bounded federation contract violation."""


class FederationDenied(FederationError):
    """An operation was refused because authorization was absent or stale."""


class FederationIdentityError(FederationDenied):
    """Core/Platform identity, generation or writer binding did not match."""


class FederationPeerError(FederationDenied):
    """The peer is not enrolled, blocked, revoked, expired or scoped away."""


class FederationRoomError(FederationDenied):
    """Room, membership, epoch or audience authorization failed."""


class FederationReplay(FederationError):
    """A replayed, stale or conflicting message identity was refused."""


class FederationSchemaMismatch(FederationError):
    """The offered social contract or protocol version is unsupported."""


class FederationConflict(FederationError):
    """A durable identity or idempotency conflict was refused."""


class FederationStopped(FederationDenied):
    """Local STOP suspends all federation traffic."""


__all__ = [
    "FederationError",
    "FederationDenied",
    "FederationIdentityError",
    "FederationPeerError",
    "FederationRoomError",
    "FederationReplay",
    "FederationSchemaMismatch",
    "FederationConflict",
    "FederationStopped",
]
