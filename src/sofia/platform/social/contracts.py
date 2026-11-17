"""Versioned, authority-free social contracts shared by Platform and Core.

Every type in this module is immutable, strictly validated and safe to
serialize across an authenticated peer boundary.  Constructing, decoding or
transporting one of these values never authenticates a peer, allocates a
writer lease, grants a capability, expands an audience, or authorizes an
external effect.  Authority remains at the existing Platform SAFE/RUN/ACT
boundaries.

``SOCIAL_CONTRACT_VERSION`` names the additive contract family.  Payloads are
strictly decoded: unknown, missing or duplicate fields are rejected rather
than silently ignored.  A message body is opaque untrusted text.  It has no
field that can carry a permission, a principal, a role or an instruction with
platform authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID


SOCIAL_CONTRACT_VERSION = "aegis.social.contract.v1"
CORE_IDENTITY_SCHEMA = "aegis.social.core_identity.v1"
ROOM_ID_SCHEMA = "aegis.social.room_id.v1"
AUDIENCE_SCHEMA = "aegis.social.audience.v1"
PROVENANCE_SCHEMA = "aegis.social.provenance.v1"
CHAT_MESSAGE_SCHEMA = "aegis.social.chat_message.v1"
ROOM_MEMBERSHIP_SCHEMA = "aegis.social.room_membership.v1"
INFERENCE_WORKLOAD_SCHEMA = "aegis.social.inference_workload.v1"
INFERENCE_REQUEST_SCHEMA = "aegis.social.inference_request.v1"
RESOURCE_RESERVATION_SCHEMA = "aegis.social.resource_reservation.v1"

MAX_MESSAGE_BODY_BYTES = 256 * 1024
MAX_DISPLAY_NAME_CHARS = 128

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _bounded_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _display_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("display_name must be text")
    name = value.strip()
    if not 1 <= len(name) <= MAX_DISPLAY_NAME_CHARS:
        raise ValueError("display_name must be 1..128 characters")
    if any(ord(character) < 0x20 for character in name):
        raise ValueError("display_name cannot contain control characters")
    return name


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _uuid_text(value: object, label: str) -> UUID:
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError(f"{label} must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a canonical UUID string") from exc
    if str(parsed) != value:
        raise ValueError(f"{label} must be a lowercase canonical UUID string")
    return _uuid(parsed, label)


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _exact(document: object, keys: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(document, Mapping) or set(document) != keys:
        raise ValueError(f"{label} must contain exactly the reviewed fields")
    return document


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO timestamp")
    try:
        return _utc(datetime.fromisoformat(value), label)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Return the one canonical JSON encoding used for contract digests."""
    if not isinstance(payload, Mapping):
        raise TypeError("canonical JSON requires a mapping")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Hash a canonical contract payload; hashing is not authentication."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class RoomKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    PRIVATE_GROUP = "private_group"


class AudienceKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    PRIVATE_GROUP = "private_group"


class MembershipStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REVOKED = "revoked"
    BLOCKED = "blocked"


class MessageOrigin(str, Enum):
    LOCAL = "local"
    AUTHENTICATED_PEER = "authenticated_peer"
    RECOVERED = "recovered"


class ProvenanceAuthenticity(str, Enum):
    AUTHENTICATED = "authenticated"
    UNVERIFIED = "unverified"
    RECOVERED = "recovered"


@dataclass(frozen=True, slots=True)
class CoreIdentity:
    """A distinct Core UUID exactly bound to one enrolled Platform.

    ``generation`` fences the active writer/process revision for that identity.
    This object is an inert projection; it is not proof of identity ownership,
    writer authority or peer trust.
    """

    core_id: UUID
    platform_id: str
    generation: int
    display_name: str

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _bounded_identifier(self.platform_id, "platform_id")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        _display_name(self.display_name)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": CORE_IDENTITY_SCHEMA,
            "core_id": str(self.core_id),
            "platform_id": self.platform_id,
            "generation": self.generation,
            "display_name": self.display_name,
        }

    @classmethod
    def from_payload(cls, document: object) -> "CoreIdentity":
        payload = _exact(
            document,
            frozenset({"schema", "core_id", "platform_id", "generation", "display_name"}),
            CORE_IDENTITY_SCHEMA,
        )
        if payload["schema"] != CORE_IDENTITY_SCHEMA:
            raise ValueError("unsupported Core identity schema")
        if type(payload["generation"]) is not int:
            raise ValueError("generation must be an integer")
        return cls(
            core_id=_uuid_text(payload["core_id"], "core_id"),
            platform_id=payload["platform_id"],
            generation=payload["generation"],
            display_name=payload["display_name"],
        )


@dataclass(frozen=True, slots=True, order=True)
class RoomId:
    """Bounded opaque room identifier, independent of a display label."""

    value: str

    def __post_init__(self) -> None:
        _bounded_identifier(self.value, "room_id")

    def __str__(self) -> str:
        return self.value

    def to_payload(self) -> dict[str, object]:
        return {"schema": ROOM_ID_SCHEMA, "value": self.value}

    @classmethod
    def from_payload(cls, document: object) -> "RoomId":
        payload = _exact(document, frozenset({"schema", "value"}), ROOM_ID_SCHEMA)
        if payload["schema"] != ROOM_ID_SCHEMA:
            raise ValueError("unsupported room id schema")
        return cls(payload["value"])


@dataclass(frozen=True, slots=True)
class Audience:
    """Recipient scope carried by a message.

    Group audiences remain membership-gated by the receiving Platform; naming a
    group is never itself proof that a Core may read it.  A DIRECT audience
    names exactly one recipient Core.
    """

    audience_id: str
    kind: AudienceKind
    room_id: RoomId
    recipient_core_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        _bounded_identifier(self.audience_id, "audience_id")
        if not isinstance(self.kind, AudienceKind):
            raise TypeError("audience kind must be AudienceKind")
        if not isinstance(self.room_id, RoomId):
            raise TypeError("audience room_id must be RoomId")
        if not isinstance(self.recipient_core_ids, tuple):
            raise TypeError("recipient_core_ids must be a tuple")
        if len(self.recipient_core_ids) > 256:
            raise ValueError("recipient_core_ids exceeds the bounded recipient count")
        for core_id in self.recipient_core_ids:
            _uuid(core_id, "recipient core id")
        if len(set(self.recipient_core_ids)) != len(self.recipient_core_ids):
            raise ValueError("recipient_core_ids cannot contain duplicates")
        if self.kind is AudienceKind.DIRECT:
            if len(self.recipient_core_ids) != 1:
                raise ValueError("a direct audience requires exactly one recipient")
        elif self.recipient_core_ids:
            raise ValueError("group audiences do not embed an unrestricted recipient list")

    def direct_recipient(self) -> UUID | None:
        return self.recipient_core_ids[0] if self.kind is AudienceKind.DIRECT else None

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": AUDIENCE_SCHEMA,
            "audience_id": self.audience_id,
            "kind": self.kind.value,
            "room_id": self.room_id.to_payload(),
            "recipient_core_ids": [str(core_id) for core_id in self.recipient_core_ids],
        }

    @classmethod
    def from_payload(cls, document: object) -> "Audience":
        payload = _exact(
            document,
            frozenset({"schema", "audience_id", "kind", "room_id", "recipient_core_ids"}),
            AUDIENCE_SCHEMA,
        )
        if payload["schema"] != AUDIENCE_SCHEMA:
            raise ValueError("unsupported audience schema")
        recipients = payload["recipient_core_ids"]
        if not isinstance(recipients, list):
            raise ValueError("recipient_core_ids must be a JSON array")
        return cls(
            audience_id=payload["audience_id"],
            kind=AudienceKind(payload["kind"]),
            room_id=RoomId.from_payload(payload["room_id"]),
            recipient_core_ids=tuple(_uuid_text(value, "recipient core id") for value in recipients),
        )


@dataclass(frozen=True, slots=True)
class Provenance:
    """Bounded origin evidence attached to a message.

    Authenticated transport identity comes from the peer channel, not from the
    message text.  ``UNVERIFIED`` content is retained for review only.
    """

    origin_platform_id: str
    origin_core_id: UUID | None
    envelope_digest: str
    authenticity: ProvenanceAuthenticity
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.origin_platform_id, "origin_platform_id")
        if self.origin_core_id is not None:
            _uuid(self.origin_core_id, "origin_core_id")
        _digest(self.envelope_digest, "envelope_digest")
        if not isinstance(self.authenticity, ProvenanceAuthenticity):
            raise TypeError("authenticity must be ProvenanceAuthenticity")
        if self.received_at is not None:
            object.__setattr__(self, "received_at", _utc(self.received_at, "received_at"))

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": PROVENANCE_SCHEMA,
            "origin_platform_id": self.origin_platform_id,
            "origin_core_id": None if self.origin_core_id is None else str(self.origin_core_id),
            "envelope_digest": self.envelope_digest,
            "authenticity": self.authenticity.value,
            "received_at": None if self.received_at is None else self.received_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, document: object) -> "Provenance":
        payload = _exact(
            document,
            frozenset({
                "schema", "origin_platform_id", "origin_core_id",
                "envelope_digest", "authenticity", "received_at",
            }),
            PROVENANCE_SCHEMA,
        )
        if payload["schema"] != PROVENANCE_SCHEMA:
            raise ValueError("unsupported provenance schema")
        received = payload["received_at"]
        if received is not None:
            received = _timestamp(received, "received_at")
        origin_core = payload["origin_core_id"]
        return cls(
            origin_platform_id=payload["origin_platform_id"],
            origin_core_id=None if origin_core is None else _uuid_text(origin_core, "origin_core_id"),
            envelope_digest=payload["envelope_digest"],
            authenticity=ProvenanceAuthenticity(payload["authenticity"]),
            received_at=received,
        )


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """An immutable social message.

    ``body`` is untrusted text even when the transport authenticated the sender.
    This contract deliberately has no authority, capability, role or command
    field.  A peer can therefore never acquire authority by sending data.
    """

    message_id: UUID
    room_id: RoomId
    sender_core_id: UUID
    audience: Audience
    body: str
    created_at: datetime
    reply_to: UUID | None
    origin: MessageOrigin
    sequence: int
    provenance: Provenance

    def __post_init__(self) -> None:
        _uuid(self.message_id, "message_id")
        if not isinstance(self.room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        _uuid(self.sender_core_id, "sender_core_id")
        if not isinstance(self.audience, Audience):
            raise TypeError("audience must be Audience")
        if self.audience.room_id != self.room_id:
            raise ValueError("audience room must match the message room")
        if not isinstance(self.body, str):
            raise ValueError("body must be text")
        encoded = self.body.encode("utf-8")
        if not encoded or len(encoded) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("body must be non-empty and within the message size bound")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.reply_to is not None:
            _uuid(self.reply_to, "reply_to")
            if self.reply_to == self.message_id:
                raise ValueError("a message cannot reply to itself")
        if not isinstance(self.origin, MessageOrigin):
            raise TypeError("origin must be MessageOrigin")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": CHAT_MESSAGE_SCHEMA,
            "message_id": str(self.message_id),
            "room_id": self.room_id.to_payload(),
            "sender_core_id": str(self.sender_core_id),
            "audience": self.audience.to_payload(),
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "reply_to": None if self.reply_to is None else str(self.reply_to),
            "origin": self.origin.value,
            "sequence": self.sequence,
            "provenance": self.provenance.to_payload(),
        }

    @classmethod
    def from_payload(cls, document: object) -> "ChatMessage":
        payload = _exact(
            document,
            frozenset({
                "schema", "message_id", "room_id", "sender_core_id", "audience",
                "body", "created_at", "reply_to", "origin", "sequence", "provenance",
            }),
            CHAT_MESSAGE_SCHEMA,
        )
        if payload["schema"] != CHAT_MESSAGE_SCHEMA:
            raise ValueError("unsupported chat message schema")
        reply_to = payload["reply_to"]
        return cls(
            message_id=_uuid_text(payload["message_id"], "message_id"),
            room_id=RoomId.from_payload(payload["room_id"]),
            sender_core_id=_uuid_text(payload["sender_core_id"], "sender_core_id"),
            audience=Audience.from_payload(payload["audience"]),
            body=payload["body"],
            created_at=_timestamp(payload["created_at"], "created_at"),
            reply_to=None if reply_to is None else _uuid_text(reply_to, "reply_to"),
            origin=MessageOrigin(payload["origin"]),
            sequence=payload["sequence"],
            provenance=Provenance.from_payload(payload["provenance"]),
        )


def message_digest(message: ChatMessage) -> str:
    """Return the canonical digest of a message payload.

    The provenance ``envelope_digest`` field is excluded from the hashed
    projection so a message can reference its own canonical digest without a
    circular dependency.  The field is still validated and compared at the
    receiving boundary.
    """
    if not isinstance(message, ChatMessage):
        raise TypeError("message must be ChatMessage")
    payload = message.to_payload()
    provenance = dict(payload["provenance"])
    provenance["envelope_digest"] = ""
    payload["provenance"] = provenance
    return payload_digest(payload)


@dataclass(frozen=True, slots=True)
class RoomMembership:
    """Versioned local authorization for one Core in one room.

    ``epoch`` fences revisions.  ``history_from_sequence`` bounds which older
    room sequence numbers this member may project; a newly joined member does
    not automatically receive earlier history.
    """

    room_id: RoomId
    core_id: UUID
    epoch: int
    status: MembershipStatus
    joined_at: datetime
    history_from_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        _uuid(self.core_id, "core_id")
        if type(self.epoch) is not int or self.epoch < 1:
            raise ValueError("epoch must be a positive integer")
        if not isinstance(self.status, MembershipStatus):
            raise TypeError("status must be MembershipStatus")
        object.__setattr__(self, "joined_at", _utc(self.joined_at, "joined_at"))
        if type(self.history_from_sequence) is not int or self.history_from_sequence < 0:
            raise ValueError("history_from_sequence must be a nonnegative integer")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": ROOM_MEMBERSHIP_SCHEMA,
            "room_id": self.room_id.to_payload(),
            "core_id": str(self.core_id),
            "epoch": self.epoch,
            "status": self.status.value,
            "joined_at": self.joined_at.isoformat(),
            "history_from_sequence": self.history_from_sequence,
        }

    @classmethod
    def from_payload(cls, document: object) -> "RoomMembership":
        payload = _exact(
            document,
            frozenset({
                "schema", "room_id", "core_id", "epoch", "status",
                "joined_at", "history_from_sequence",
            }),
            ROOM_MEMBERSHIP_SCHEMA,
        )
        if payload["schema"] != ROOM_MEMBERSHIP_SCHEMA:
            raise ValueError("unsupported room membership schema")
        return cls(
            room_id=RoomId.from_payload(payload["room_id"]),
            core_id=_uuid_text(payload["core_id"], "core_id"),
            epoch=payload["epoch"],
            status=MembershipStatus(payload["status"]),
            joined_at=_timestamp(payload["joined_at"], "joined_at"),
            history_from_sequence=payload["history_from_sequence"],
        )


@dataclass(frozen=True, slots=True)
class ResourceReservationRef:
    """Opaque reference to an existing resource reservation.

    The reference is evidence and a correlation key only; it never reserves,
    leases or authorizes compute by itself.
    """

    reservation_id: str
    node_id: str
    workload_id: UUID
    expires_at: datetime

    def __post_init__(self) -> None:
        _bounded_identifier(self.reservation_id, "reservation_id")
        _bounded_identifier(self.node_id, "node_id")
        _uuid(self.workload_id, "workload_id")
        object.__setattr__(self, "expires_at", _utc(self.expires_at, "expires_at"))

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_RESERVATION_SCHEMA,
            "reservation_id": self.reservation_id,
            "node_id": self.node_id,
            "workload_id": str(self.workload_id),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, document: object) -> "ResourceReservationRef":
        payload = _exact(
            document,
            frozenset({"schema", "reservation_id", "node_id", "workload_id", "expires_at"}),
            RESOURCE_RESERVATION_SCHEMA,
        )
        if payload["schema"] != RESOURCE_RESERVATION_SCHEMA:
            raise ValueError("unsupported resource reservation schema")
        return cls(
            reservation_id=payload["reservation_id"],
            node_id=payload["node_id"],
            workload_id=_uuid_text(payload["workload_id"], "workload_id"),
            expires_at=_timestamp(payload["expires_at"], "expires_at"),
        )


@dataclass(frozen=True, slots=True)
class InferenceWorkload:
    """Immutable inference request identity and its bound resource reference."""

    workload_id: UUID
    model_id: str
    model_digest: str
    input_digest: str
    requester_core_id: UUID
    purpose: str
    max_output_tokens: int
    created_at: datetime
    resource_reservation: ResourceReservationRef | None = None

    def __post_init__(self) -> None:
        _uuid(self.workload_id, "workload_id")
        _bounded_identifier(self.model_id, "model_id")
        _digest(self.model_digest, "model_digest")
        _digest(self.input_digest, "input_digest")
        _uuid(self.requester_core_id, "requester_core_id")
        if not isinstance(self.purpose, str) or not 1 <= len(self.purpose.strip()) <= 512:
            raise ValueError("purpose must be 1..512 characters")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 1_000_000:
            raise ValueError("max_output_tokens must be in 1..1000000")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        if self.resource_reservation is not None:
            if not isinstance(self.resource_reservation, ResourceReservationRef):
                raise TypeError("resource_reservation must be ResourceReservationRef")
            if self.resource_reservation.workload_id != self.workload_id:
                raise ValueError("resource reservation belongs to another workload")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": INFERENCE_WORKLOAD_SCHEMA,
            "workload_id": str(self.workload_id),
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "input_digest": self.input_digest,
            "requester_core_id": str(self.requester_core_id),
            "purpose": self.purpose,
            "max_output_tokens": self.max_output_tokens,
            "created_at": self.created_at.isoformat(),
            "resource_reservation": (
                None if self.resource_reservation is None
                else self.resource_reservation.to_payload()
            ),
        }

    @classmethod
    def from_payload(cls, document: object) -> "InferenceWorkload":
        payload = _exact(
            document,
            frozenset({
                "schema", "workload_id", "model_id", "model_digest", "input_digest",
                "requester_core_id", "purpose", "max_output_tokens", "created_at",
                "resource_reservation",
            }),
            INFERENCE_WORKLOAD_SCHEMA,
        )
        if payload["schema"] != INFERENCE_WORKLOAD_SCHEMA:
            raise ValueError("unsupported inference workload schema")
        reservation = payload["resource_reservation"]
        return cls(
            workload_id=_uuid_text(payload["workload_id"], "workload_id"),
            model_id=payload["model_id"],
            model_digest=payload["model_digest"],
            input_digest=payload["input_digest"],
            requester_core_id=_uuid_text(payload["requester_core_id"], "requester_core_id"),
            purpose=payload["purpose"],
            max_output_tokens=payload["max_output_tokens"],
            created_at=_timestamp(payload["created_at"], "created_at"),
            resource_reservation=(
                None if reservation is None else ResourceReservationRef.from_payload(reservation)
            ),
        )


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """Idempotent inference request identity; never a scheduling authority."""

    request_id: UUID
    workload: InferenceWorkload
    idempotency_key: str
    expires_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.request_id, "request_id")
        if not isinstance(self.workload, InferenceWorkload):
            raise TypeError("workload must be InferenceWorkload")
        _bounded_identifier(self.idempotency_key, "idempotency_key")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= self.workload.created_at:
            raise ValueError("expires_at must follow workload creation")
        object.__setattr__(self, "expires_at", expires)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": INFERENCE_REQUEST_SCHEMA,
            "request_id": str(self.request_id),
            "workload": self.workload.to_payload(),
            "idempotency_key": self.idempotency_key,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, document: object) -> "InferenceRequest":
        payload = _exact(
            document,
            frozenset({"schema", "request_id", "workload", "idempotency_key", "expires_at"}),
            INFERENCE_REQUEST_SCHEMA,
        )
        if payload["schema"] != INFERENCE_REQUEST_SCHEMA:
            raise ValueError("unsupported inference request schema")
        return cls(
            request_id=_uuid_text(payload["request_id"], "request_id"),
            workload=InferenceWorkload.from_payload(payload["workload"]),
            idempotency_key=payload["idempotency_key"],
            expires_at=_timestamp(payload["expires_at"], "expires_at"),
        )


__all__ = [
    "SOCIAL_CONTRACT_VERSION",
    "CORE_IDENTITY_SCHEMA",
    "ROOM_ID_SCHEMA",
    "AUDIENCE_SCHEMA",
    "PROVENANCE_SCHEMA",
    "CHAT_MESSAGE_SCHEMA",
    "ROOM_MEMBERSHIP_SCHEMA",
    "INFERENCE_WORKLOAD_SCHEMA",
    "INFERENCE_REQUEST_SCHEMA",
    "RESOURCE_RESERVATION_SCHEMA",
    "MAX_MESSAGE_BODY_BYTES",
    "MAX_DISPLAY_NAME_CHARS",
    "RoomKind",
    "AudienceKind",
    "MembershipStatus",
    "MessageOrigin",
    "ProvenanceAuthenticity",
    "CoreIdentity",
    "RoomId",
    "Audience",
    "Provenance",
    "ChatMessage",
    "RoomMembership",
    "ResourceReservationRef",
    "InferenceWorkload",
    "InferenceRequest",
    "canonical_json",
    "payload_digest",
    "message_digest",
]
