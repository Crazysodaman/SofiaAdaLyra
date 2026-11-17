"""Authenticated Core-to-Core federation for independent Platform instances."""
from sofia.platform.federation.envelope import ENVELOPE_SCHEMA, PeerEnvelope, build_envelope
from sofia.platform.federation.errors import (
    FederationConflict,
    FederationDenied,
    FederationError,
    FederationIdentityError,
    FederationPeerError,
    FederationReplay,
    FederationRoomError,
    FederationSchemaMismatch,
    FederationStopped,
)
from sofia.platform.federation.models import (
    AudienceProjection,
    AuthenticatedPeer,
    ContactDirection,
    DeliveryStatus,
    InboundMessage,
    InboxRecord,
    OutboxRecord,
    PeerAcknowledgment,
    PeerRecord,
    PeerState,
    TransportOutcome,
    TransportReceipt,
)
from sofia.platform.federation.node import FederationNode, SendResult
from sofia.platform.federation.store import FederationState
from sofia.platform.federation.transport import FederationTransport, InProcessTransport

__all__ = [
    "ENVELOPE_SCHEMA",
    "PeerEnvelope",
    "build_envelope",
    "FederationError",
    "FederationDenied",
    "FederationIdentityError",
    "FederationPeerError",
    "FederationRoomError",
    "FederationReplay",
    "FederationSchemaMismatch",
    "FederationConflict",
    "FederationStopped",
    "AudienceProjection",
    "AuthenticatedPeer",
    "ContactDirection",
    "DeliveryStatus",
    "InboundMessage",
    "InboxRecord",
    "OutboxRecord",
    "PeerAcknowledgment",
    "PeerRecord",
    "PeerState",
    "TransportOutcome",
    "TransportReceipt",
    "FederationNode",
    "SendResult",
    "FederationState",
    "FederationTransport",
    "InProcessTransport",
]
