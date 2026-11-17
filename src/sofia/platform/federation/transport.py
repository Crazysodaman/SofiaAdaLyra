"""Bounded authenticated peer transport interfaces.

The transport is the only source of the peer's authenticated identity.  In
production this is a pinned mutual-TLS channel with an exact enrolled endpoint,
key epoch and revocation state.  The in-process implementation here is a real
local transport for tests, not a claim of deployed networking.
"""
from __future__ import annotations

from typing import Protocol

from sofia.platform.federation.envelope import PeerEnvelope
from sofia.platform.federation.models import (
    AuthenticatedPeer,
    TransportOutcome,
    TransportReceipt,
)


class FederationTransport(Protocol):
    def deliver(
        self, envelope: PeerEnvelope, authenticated: AuthenticatedPeer,
    ) -> TransportReceipt:
        """Deliver one envelope and return at-least-once transport status."""
        ...


class InProcessTransport:
    """Local bounded transport used to prove cross-Core behavior in tests.

    Delivery is at-least-once.  A destination may be marked offline to return
    an uncertain outcome, modeling a network partition or a crash after send.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, object] = {}
        self._offline: set[str] = set()

    def register(self, platform_id: str, node: object) -> None:
        if not isinstance(platform_id, str) or not platform_id.strip():
            raise ValueError("platform_id is required")
        if not hasattr(node, "receive"):
            raise TypeError("node must expose receive()")
        self._nodes[platform_id] = node

    def unregister(self, platform_id: str) -> None:
        self._nodes.pop(platform_id, None)
        self._offline.discard(platform_id)

    def set_offline(self, platform_id: str, offline: bool = True) -> None:
        if offline:
            self._offline.add(platform_id)
        else:
            self._offline.discard(platform_id)

    def deliver(
        self, envelope: PeerEnvelope, authenticated: AuthenticatedPeer,
    ) -> TransportReceipt:
        if not isinstance(envelope, PeerEnvelope):
            raise TypeError("envelope must be PeerEnvelope")
        if not isinstance(authenticated, AuthenticatedPeer):
            raise TypeError("authenticated peer identity is required")
        destination = self._nodes.get(envelope.destination_platform_id)
        if envelope.destination_platform_id in self._offline:
            return TransportReceipt(TransportOutcome.UNCERTAIN, "destination partitioned")
        if destination is None:
            return TransportReceipt(TransportOutcome.REJECTED, "destination is not registered")
        return destination.receive(envelope, authenticated)


__all__ = ["FederationTransport", "InProcessTransport"]
