"""Compatibility adapters between the shared social contract and domain packages.

The social contract is the canonical wire vocabulary.  Chat, federation,
autonomy, inference and remote clients keep narrow local projections; these
adapters are the only explicit conversion boundary between them.  Conversion
is deliberately inert: it authenticates nothing, grants no membership and
carries no authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID

from sofia.platform.social import contracts as social

if TYPE_CHECKING:
    from sofia.platform.chat import contracts as chat
    from sofia.platform.chat_clients import contracts as clients
    from sofia.platform.federation.envelope import PeerEnvelope as FederationEnvelope
    from sofia.platform.inference.identity import CoreIdentity as InferenceIdentity

SOCIAL_ADAPTER_VERSION = "aegis.social.integration.v1"

_ROOM_KIND = {
    social.RoomKind.GENERAL: "general",
    social.RoomKind.DIRECT: "direct",
    social.RoomKind.PRIVATE_GROUP: "private_group",
}


def _chat_room_kind(kind: social.RoomKind):
    from sofia.platform.chat.contracts import RoomKind

    return RoomKind(_ROOM_KIND[kind])


def _social_room_kind(kind) -> social.RoomKind:
    return social.RoomKind(getattr(kind, "value", str(kind)))


def social_identity_from_chat(identity: "chat.CoreIdentity") -> social.CoreIdentity:
    return social.CoreIdentity(
        core_id=identity.core_id,
        platform_id=identity.platform_id,
        generation=identity.generation,
        display_name=identity.display_name,
    )


def chat_identity_from_social(identity: social.CoreIdentity) -> "chat.CoreIdentity":
    from sofia.platform.chat.contracts import CoreIdentity

    return CoreIdentity(
        core_id=identity.core_id,
        platform_id=identity.platform_id,
        generation=identity.generation,
        display_name=identity.display_name,
    )


def client_identity_from_social(
    identity: social.CoreIdentity,
) -> "clients.CoreIdentity":
    from sofia.platform.chat_clients.contracts import CoreIdentity

    return CoreIdentity(
        core_id=str(identity.core_id),
        platform_id=identity.platform_id,
        generation=identity.generation,
        display_name=identity.display_name,
    )


def inference_identity_from_social(
    identity: social.CoreIdentity,
) -> "InferenceIdentity":
    from sofia.platform.inference.identity import CoreIdentity

    return CoreIdentity(
        core_id=identity.core_id,
        platform_id=identity.platform_id,
        generation=identity.generation,
        display_name=identity.display_name,
    )


def _chat_audience(
    message: "chat.ChatMessage",
) -> social.Audience:
    room_id = social.RoomId(message.room_id)
    kind = _social_room_kind(message.audience.kind)
    recipients: tuple[UUID, ...] = ()
    if kind is social.RoomKind.DIRECT:
        recipients = tuple(
            UUID(member_id)
            for member_id in message.audience.member_ids
            if member_id != message.sender_core_id
        )
        if len(recipients) != 1:
            raise ValueError("direct chat audience must identify exactly one peer")
    return social.Audience(
        audience_id=f"audience:{message.room_id}",
        kind=social.AudienceKind(kind.value),
        room_id=room_id,
        recipient_core_ids=recipients,
    )


def _chat_origin(message: "chat.ChatMessage") -> social.MessageOrigin:
    from sofia.platform.chat.contracts import MessageOrigin

    if message.origin is MessageOrigin.PEER_CORE:
        return social.MessageOrigin.AUTHENTICATED_PEER
    return social.MessageOrigin.LOCAL


def _chat_provenance(message: "chat.ChatMessage") -> social.Provenance:
    digest = sha256(
        "|".join((
            message.message_id,
            message.room_id,
            message.created_at.isoformat(),
            message.body,
        )).encode("utf-8")
    ).hexdigest()
    return social.Provenance(
        origin_platform_id=message.provenance.source_platform_id,
        origin_core_id=(
            UUID(message.sender_core_id)
            if message.sender_core_id is not None
            else None
        ),
        envelope_digest=digest,
        authenticity=(
            social.ProvenanceAuthenticity.AUTHENTICATED
            if message.provenance.transport_verified
            else social.ProvenanceAuthenticity.UNVERIFIED
        ),
        received_at=message.provenance.received_at,
    )


def social_message_from_chat(message: "chat.ChatMessage") -> social.ChatMessage:
    """Project one canonical chat message into the shared wire contract."""
    return social.ChatMessage(
        message_id=UUID(message.message_id),
        room_id=social.RoomId(message.room_id),
        sender_core_id=UUID(message.sender_core_id),
        audience=_chat_audience(message),
        body=message.body,
        created_at=message.created_at,
        reply_to=None if message.reply_to is None else UUID(message.reply_to),
        origin=_chat_origin(message),
        sequence=message.sequence,
        provenance=_chat_provenance(message),
    )


def chat_peer_envelope_from_federation(
    envelope: "FederationEnvelope",
) -> "chat.PeerEnvelope":
    """Project an authenticated federation envelope into chat receiver input."""
    from sofia.platform.chat.contracts import PeerEnvelope

    return PeerEnvelope(
        message_id=str(envelope.message.message_id),
        source_core_id=str(envelope.source_core_id),
        source_platform_id=envelope.source_platform_id,
        source_generation=envelope.source_generation,
        room_id=envelope.message.room_id.value,
        body=envelope.message.body,
        created_at=envelope.message.created_at,
        reply_to=(
            None
            if envelope.message.reply_to is None
            else str(envelope.message.reply_to)
        ),
        idempotency_key=envelope.idempotency_key,
    )


def chat_room_kind_from_social(kind: social.RoomKind):
    return _chat_room_kind(kind)


def social_room_kind_from_chat(kind) -> social.RoomKind:
    return _social_room_kind(kind)
class FederationChatBridge:
    """Explicit bridge between canonical chat state and authenticated federation.

    Local chat remains the single writer of chat history.  Federation owns
    peer authentication and durable delivery.  The bridge copies one already
    committed local chat message to each authorized remote peer and projects
    an authenticated inbound envelope back into chat.  It never mints identity,
    membership or authority.
    """

    def __init__(self, chat, federation, peer_identities):
        self._chat = chat
        self._federation = federation
        self._peer_identities = dict(peer_identities)

    def send(self, actor, room_id, body, *, recipient_ids, **kwargs):
        message = self._chat.send(actor, room_id, body, **kwargs)
        shared = social_message_from_chat(message)
        idempotency_key = (
            message.provenance.idempotency_key or f"message:{message.message_id}"
        )
        for recipient_id in recipient_ids:
            self._federation.send_message(
                recipient_id,
                shared.room_id,
                shared.body,
                message_id=shared.message_id,
                created_at=shared.created_at,
                reply_to=shared.reply_to,
                idempotency_key=idempotency_key,
            )
        return shared

    def receive(self, envelope):
        identity = self._peer_identities.get(envelope.source_core_id)
        if identity is None:
            raise PermissionError("federated sender is not an enrolled chat peer")
        return self._chat.receive_peer_message(
            chat_identity_from_social(identity),
            chat_peer_envelope_from_federation(envelope),
        )
