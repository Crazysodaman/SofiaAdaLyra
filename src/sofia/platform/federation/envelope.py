"""Authenticated Platform-to-Platform envelope for social messages.

The envelope binds an immutable :class:`~sofia.platform.social.contracts.ChatMessage`
to exact source/destination Platforms, Core identities and writer generations.
Transport authentication is supplied separately by the peer channel; the
envelope itself is inert data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sofia.platform.social.contracts import (
    SOCIAL_CONTRACT_VERSION,
    ChatMessage,
    message_digest,
)
from sofia.platform.social.contracts import _bounded_identifier, _exact, _timestamp, _utc, _uuid, _uuid_text
from sofia.sdk.contracts import ProtocolVersion


ENVELOPE_SCHEMA = "aegis.platform.peer.envelope.v1"


@dataclass(frozen=True, slots=True)
class PeerEnvelope:
    message: ChatMessage
    source_platform_id: str
    source_core_id: UUID
    source_generation: int
    destination_platform_id: str
    destination_core_id: UUID
    destination_generation: int
    idempotency_key: str
    sent_at: datetime
    expires_at: datetime
    payload_digest: str
    protocol_version: str = "1.0"
    content_type: str = SOCIAL_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.message, ChatMessage):
            raise TypeError("message must be ChatMessage")
        _bounded_identifier(self.source_platform_id, "source_platform_id")
        _uuid(self.source_core_id, "source_core_id")
        _uuid(self.destination_core_id, "destination_core_id")
        _bounded_identifier(self.destination_platform_id, "destination_platform_id")
        for label in ("source_generation", "destination_generation"):
            value = getattr(self, label)
            if type(value) is not int or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        _bounded_identifier(self.idempotency_key, "idempotency_key")
        sent = _utc(self.sent_at, "sent_at")
        expires = _utc(self.expires_at, "expires_at")
        object.__setattr__(self, "sent_at", sent)
        object.__setattr__(self, "expires_at", expires)
        if expires <= sent:
            raise ValueError("expires_at must follow sent_at")
        if self.message.sender_core_id != self.source_core_id:
            raise ValueError("envelope source Core must match the message sender")
        if self.message.created_at > sent:
            raise ValueError("message creation cannot follow its envelope send time")
        if self.payload_digest != message_digest(self.message):
            raise ValueError("payload digest does not match the message")
        try:
            ProtocolVersion.parse(self.protocol_version)
        except ValueError as exc:
            raise ValueError("protocol_version must use MAJOR.MINOR") from exc
        _bounded_identifier(self.content_type, "content_type")

    @property
    def message_id(self) -> UUID:
        return self.message.message_id

    @property
    def room_id(self):
        return self.message.room_id

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": ENVELOPE_SCHEMA,
            "protocol_version": self.protocol_version,
            "content_type": self.content_type,
            "source_platform_id": self.source_platform_id,
            "source_core_id": str(self.source_core_id),
            "source_generation": self.source_generation,
            "destination_platform_id": self.destination_platform_id,
            "destination_core_id": str(self.destination_core_id),
            "destination_generation": self.destination_generation,
            "idempotency_key": self.idempotency_key,
            "sent_at": self.sent_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "payload_digest": self.payload_digest,
            "message": self.message.to_payload(),
        }

    @classmethod
    def from_payload(cls, document: object) -> "PeerEnvelope":
        payload = _exact(
            document,
            frozenset({
                "schema", "protocol_version", "content_type", "source_platform_id",
                "source_core_id", "source_generation", "destination_platform_id",
                "destination_core_id", "destination_generation", "idempotency_key",
                "sent_at", "expires_at", "payload_digest", "message",
            }),
            ENVELOPE_SCHEMA,
        )
        if payload["schema"] != ENVELOPE_SCHEMA:
            raise ValueError("unsupported peer envelope schema")
        return cls(
            message=ChatMessage.from_payload(payload["message"]),
            source_platform_id=payload["source_platform_id"],
            source_core_id=_uuid_text(payload["source_core_id"], "source_core_id"),
            source_generation=payload["source_generation"],
            destination_platform_id=payload["destination_platform_id"],
            destination_core_id=_uuid_text(payload["destination_core_id"], "destination_core_id"),
            destination_generation=payload["destination_generation"],
            idempotency_key=payload["idempotency_key"],
            sent_at=_timestamp(payload["sent_at"], "sent_at"),
            expires_at=_timestamp(payload["expires_at"], "expires_at"),
            payload_digest=payload["payload_digest"],
            protocol_version=payload["protocol_version"],
            content_type=payload["content_type"],
        )


def build_envelope(
    message: ChatMessage,
    *,
    source_platform_id: str,
    source_generation: int,
    destination_platform_id: str,
    destination_core_id: UUID,
    destination_generation: int,
    idempotency_key: str,
    sent_at: datetime,
    expires_at: datetime,
    protocol_version: str = "1.0",
    content_type: str = SOCIAL_CONTRACT_VERSION,
) -> PeerEnvelope:
    """Build an envelope with the canonical message digest."""
    if not isinstance(message, ChatMessage):
        raise TypeError("message must be ChatMessage")
    return PeerEnvelope(
        message=message,
        source_platform_id=source_platform_id,
        source_core_id=message.sender_core_id,
        source_generation=source_generation,
        destination_platform_id=destination_platform_id,
        destination_core_id=destination_core_id,
        destination_generation=destination_generation,
        idempotency_key=idempotency_key,
        sent_at=sent_at,
        expires_at=expires_at,
        payload_digest=message_digest(message),
        protocol_version=protocol_version,
        content_type=content_type,
    )


__all__ = ["ENVELOPE_SCHEMA", "PeerEnvelope", "build_envelope"]
