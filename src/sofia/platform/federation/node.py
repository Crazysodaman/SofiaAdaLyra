"""Authenticated Core-to-Core federation node.

A node owns exactly one local Core identity and one active writer generation.
It enrolls peers explicitly, stores durable outbox/inbox records, authorizes
recipient-scoped room delivery and exposes peer content only as untrusted data.
It is not a second Core, a cloned persona, a shared writer or an autonomous
social agent.  Messages never carry or acquire authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping
from uuid import UUID, uuid4

from sofia.platform.federation.envelope import PeerEnvelope
from sofia.platform.federation.errors import (
    FederationConflict,
    FederationDenied,
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
from sofia.platform.federation.store import FederationState
from sofia.platform.social.contracts import (
    SOCIAL_CONTRACT_VERSION,
    MAX_MESSAGE_BODY_BYTES,
    Audience,
    AudienceKind,
    ChatMessage,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
    Provenance,
    ProvenanceAuthenticity,
    RoomId,
    RoomKind,
    RoomMembership,
    message_digest,
)
from sofia.sdk.contracts import ProtocolVersion, ProtocolVersionRange


DEFAULT_ENROLLMENT_TTL = timedelta(days=30)
DEFAULT_MESSAGE_TTL = timedelta(days=1)
_MAX_FANOUT = 256


def _bounded_uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _require_authority(authority: Callable[[], bool] | None, operation: str) -> None:
    if not callable(authority):
        raise FederationDenied(f"{operation} requires a local authority callback")
    try:
        permitted = authority()
    except Exception as exc:
        raise FederationDenied(f"{operation} authority check failed") from exc
    if permitted is not True:
        raise FederationDenied(f"{operation} was not authorized by the local authority")


@dataclass(frozen=True, slots=True)
class SendResult:
    outbox: OutboxRecord
    envelope: PeerEnvelope
    duplicate: bool = False

    @property
    def status(self) -> DeliveryStatus:
        return self.outbox.status


class FederationNode:
    def __init__(
        self,
        state_path: Path | str,
        *,
        transport=None,
        clock: Callable[[], datetime] | None = None,
        supported_contracts: Iterable[str] | None = None,
        protocol_range: ProtocolVersionRange | None = None,
        max_clock_skew: timedelta = timedelta(minutes=5),
    ) -> None:
        self.state = FederationState(state_path)
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._contracts = frozenset(
            supported_contracts if supported_contracts is not None
            else (SOCIAL_CONTRACT_VERSION,)
        )
        if not self._contracts or any(not isinstance(item, str) for item in self._contracts):
            raise ValueError("supported contracts must be a nonempty set of schema names")
        self._protocol_range = protocol_range or ProtocolVersionRange(
            ProtocolVersion(1, 0), ProtocolVersion(1, 0)
        )
        if not isinstance(self._protocol_range, ProtocolVersionRange):
            raise TypeError("protocol_range must be ProtocolVersionRange")
        if not isinstance(max_clock_skew, timedelta) or max_clock_skew < timedelta(0):
            raise ValueError("max_clock_skew must be a nonnegative duration")
        self._max_clock_skew = max_clock_skew

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        self.state.close()

    def __enter__(self) -> "FederationNode":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise FederationIdentityError("federation clock must return an aware datetime")
        return value.astimezone(timezone.utc)

    def activate(self, identity: CoreIdentity, *, trust_anchor: str) -> CoreIdentity:
        if not isinstance(identity, CoreIdentity):
            raise TypeError("identity must be CoreIdentity")
        self.state.set_local_identity(identity, trust_anchor=trust_anchor)
        return self.identity

    @property
    def identity(self) -> CoreIdentity:
        return self.state.local_identity()[0]

    @property
    def platform_id(self) -> str:
        return self.identity.platform_id

    @property
    def core_id(self) -> UUID:
        return self.identity.core_id

    @property
    def generation(self) -> int:
        return self.identity.generation

    @property
    def trust_anchor(self) -> str:
        return self.state.local_identity()[1]

    @property
    def stopped(self) -> bool:
        return self.state.is_stopped()

    def advance_generation(
        self, generation: int, *, authority: Callable[[], bool],
    ) -> CoreIdentity:
        _require_authority(authority, "advancing the writer generation")
        return self.state.advance_local_generation(generation)

    def engage_stop(self) -> None:
        self.state.engage_stop(now=self._now())

    def clear_stop(self, *, authority: Callable[[], bool]) -> None:
        _require_authority(authority, "clearing the federation STOP")
        self.state.clear_stop(now=self._now())

    def _require_running(self) -> None:
        if self.stopped:
            raise FederationStopped("local STOP suspends all federation traffic")

    # ------------------------------------------------------------------
    # Contact requests and enrollment
    # ------------------------------------------------------------------
    def request_contact(
        self,
        remote: CoreIdentity,
        *,
        trust_anchor: str,
        ttl: timedelta = DEFAULT_ENROLLMENT_TTL,
    ) -> PeerRecord:
        now = self._now()
        self._require_running()
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise ValueError("enrollment ttl must be positive")
        return self.state.request_peer(
            remote, trust_anchor=trust_anchor, direction=ContactDirection.OUTBOUND,
            expires_at=now + ttl, now=now,
        )

    def receive_contact_request(
        self,
        remote: CoreIdentity,
        *,
        trust_anchor: str,
        ttl: timedelta = DEFAULT_ENROLLMENT_TTL,
    ) -> PeerRecord:
        now = self._now()
        self._require_running()
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise ValueError("enrollment ttl must be positive")
        return self.state.request_peer(
            remote, trust_anchor=trust_anchor, direction=ContactDirection.INBOUND,
            expires_at=now + ttl, now=now,
        )

    def accept_contact(
        self, peer_id: UUID, *, outbound: bool = True, inbound: bool = True,
    ) -> PeerRecord:
        _bounded_uuid(peer_id, "peer_id")
        return self.state.accept_peer(
            peer_id, outbound=outbound, inbound=inbound, now=self._now(),
        )

    def deny_contact(self, peer_id: UUID) -> PeerRecord:
        return self.state.deny_peer(peer_id, now=self._now())

    def block_peer(self, peer_id: UUID) -> PeerRecord:
        return self.state.block_peer(peer_id, now=self._now())

    def revoke_peer(self, peer_id: UUID) -> PeerRecord:
        return self.state.revoke_peer(peer_id, now=self._now())

    def rotate_peer_generation(
        self, peer_id: UUID, generation: int, *, authority: Callable[[], bool],
    ) -> PeerRecord:
        _require_authority(authority, "rotating a peer writer generation")
        return self.state.update_peer_generation(
            peer_id, generation=generation, now=self._now(),
        )

    def peers(self) -> tuple[PeerRecord, ...]:
        return self.state.list_peers()

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def create_room(self, room_id: RoomId, kind: RoomKind) -> None:
        self.state.create_room(room_id, kind=kind, now=self._now())

    def join_room(
        self,
        room_id: RoomId,
        core_id: UUID,
        *,
        history_from_sequence: int = 0,
        authority: Callable[[], bool] | None = None,
    ) -> RoomMembership:
        _bounded_uuid(core_id, "core_id")
        existing = self.state.membership(room_id, core_id)
        if existing is not None and existing.status in {
            MembershipStatus.REVOKED, MembershipStatus.BLOCKED,
        }:
            _require_authority(authority, "rejoining a revoked or blocked room membership")
        return self.state.set_membership(
            room_id, core_id, status=MembershipStatus.ACTIVE,
            history_from_sequence=history_from_sequence, now=self._now(),
        )

    def revoke_membership(self, room_id: RoomId, core_id: UUID) -> RoomMembership:
        existing = self.state.membership(room_id, core_id)
        if existing is None:
            raise FederationRoomError("Core is not a member of this room")
        return self.state.set_membership(
            room_id, core_id, status=MembershipStatus.REVOKED,
            history_from_sequence=existing.history_from_sequence, now=self._now(),
        )

    def membership(self, room_id: RoomId, core_id: UUID) -> RoomMembership | None:
        return self.state.membership(room_id, core_id)

    def ensure_direct_room(self, room_id: RoomId, peer_id: UUID) -> RoomMembership:
        if not isinstance(room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        peer = self.state.peer_by_id(_bounded_uuid(peer_id, "peer_id"))
        if peer is None:
            raise FederationPeerError("peer is not enrolled")
        local = self.identity
        self.state.create_room(room_id, kind=RoomKind.DIRECT, now=self._now())
        self._ensure_active_membership(room_id, local.core_id)
        self._ensure_active_membership(room_id, peer.remote_core_id)
        return self.state.require_active_member(room_id, local.core_id)

    def ensure_group_room(
        self, room_id: RoomId, peer_ids: Iterable[UUID],
    ) -> tuple[RoomMembership, ...]:
        peers = []
        for peer_id in peer_ids:
            peer = self.state.peer_by_id(_bounded_uuid(peer_id, "peer_id"))
            if peer is None:
                raise FederationPeerError("peer is not enrolled")
            peers.append(peer)
        if not peers or len(peers) > _MAX_FANOUT:
            raise FederationRoomError("group room requires 1..256 enrolled peers")
        self.state.create_room(room_id, kind=RoomKind.PRIVATE_GROUP, now=self._now())
        local = self.identity
        memberships = [self._ensure_active_membership(room_id, local.core_id)]
        for peer in peers:
            memberships.append(self._ensure_active_membership(room_id, peer.remote_core_id))
        return tuple(memberships)

    def _ensure_active_membership(self, room_id: RoomId, core_id: UUID) -> RoomMembership:
        existing = self.state.membership(room_id, core_id)
        if existing is None:
            return self.state.set_membership(
                room_id, core_id, status=MembershipStatus.ACTIVE,
                history_from_sequence=0, now=self._now(),
            )
        if existing.status is not MembershipStatus.ACTIVE:
            raise FederationRoomError(
                "existing membership is not active; explicit reauthorization is required"
            )
        return existing

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _validate_audience(
        self, audience: Audience, room_id: RoomId, room_kind: RoomKind,
        remote_core_id: UUID,
    ) -> None:
        if not isinstance(audience, Audience):
            raise TypeError("audience must be Audience")
        if audience.room_id != room_id:
            raise FederationRoomError("audience room does not match the sending room")
        if audience.kind.value != room_kind.value:
            raise FederationRoomError("audience kind does not match the room kind")
        if room_kind is RoomKind.DIRECT:
            if audience.direct_recipient() != remote_core_id:
                raise FederationRoomError(
                    "direct audience must name exactly the addressed peer Core"
                )
        elif audience.recipient_core_ids:
            raise FederationRoomError("group audiences cannot embed a recipient list")

    def _derive_audience(
        self, room_id: RoomId, room_kind: RoomKind, remote_core_id: UUID,
        audience_id: str | None,
    ) -> Audience:
        identifier = audience_id or f"audience:{room_id.value}"
        kind = AudienceKind(room_kind.value)
        recipients = (remote_core_id,) if room_kind is RoomKind.DIRECT else ()
        return Audience(
            audience_id=identifier, kind=kind, room_id=room_id,
            recipient_core_ids=recipients,
        )

    def send_message(
        self,
        peer_id: UUID,
        room_id: RoomId,
        body: str,
        *,
        audience: Audience | None = None,
        message_id: UUID | None = None,
        sequence: int | None = None,
        created_at: datetime | None = None,
        reply_to: UUID | None = None,
        idempotency_key: str | None = None,
        expires_at: datetime | None = None,
        ttl: timedelta = DEFAULT_MESSAGE_TTL,
    ) -> SendResult:
        now = self._now()
        self._require_running()
        if not isinstance(room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        if not isinstance(body, str):
            raise ValueError("body must be text")
        encoded = body.encode("utf-8")
        if not encoded or len(encoded) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("body must be non-empty and within the message size bound")
        if message_id is not None:
            _bounded_uuid(message_id, "message_id")
        if reply_to is not None:
            _bounded_uuid(reply_to, "reply_to")
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise ValueError("message ttl must be positive")

        identity = self.identity
        peer = self.state.peer_by_id(_bounded_uuid(peer_id, "peer_id"))
        if peer is None:
            raise FederationPeerError("peer is not enrolled")
        self.state.assert_peer_authorized(
            peer.peer_id, direction=ContactDirection.OUTBOUND, now=now,
        )
        if peer.state is not PeerState.ACTIVE:
            raise FederationPeerError("peer is not active")
        room_kind = self.state.room_kind(room_id)
        self.state.require_active_member(room_id, identity.core_id)
        self.state.require_active_member(room_id, peer.remote_core_id)
        selected_audience = self._derive_audience(
            room_id, room_kind, peer.remote_core_id,
            None if audience is None else audience.audience_id,
        ) if audience is None else audience
        self._validate_audience(selected_audience, room_id, room_kind, peer.remote_core_id)

        message_identifier = message_id or uuid4()
        key = idempotency_key or f"message:{message_identifier}"
        existing = self.state.outbox_by_idempotency(peer.remote_platform_id, key)
        if existing is not None:
            existing_envelope = PeerEnvelope.from_payload(json.loads(existing.envelope_json))
            if (
                existing_envelope.message.room_id != room_id
                or existing_envelope.message.body != body
                or existing_envelope.message.audience.kind is not selected_audience.kind
                or existing_envelope.message.audience.audience_id != selected_audience.audience_id
                or existing_envelope.message.audience.direct_recipient()
                != selected_audience.direct_recipient()
            ):
                raise FederationConflict(
                    "idempotency key was reused with different message content"
                )
            if message_id is not None and existing.message_id != message_id:
                raise FederationConflict("idempotency key belongs to another message id")
            return SendResult(existing, existing_envelope, duplicate=True)

        allocated_sequence = sequence
        if allocated_sequence is None:
            allocated_sequence = self.state.allocate_outgoing_sequence(room_id, identity.core_id)
        elif type(allocated_sequence) is not int or allocated_sequence < 1:
            raise ValueError("sequence must be a positive integer")
        moment = created_at.astimezone(timezone.utc) if created_at is not None else now
        if created_at is not None and (
            created_at.tzinfo is None or created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")
        expiry = expires_at.astimezone(timezone.utc) if expires_at is not None else moment + ttl
        if expires_at is not None and (
            expires_at.tzinfo is None or expires_at.utcoffset() is None
        ):
            raise ValueError("expires_at must be timezone-aware")

        draft_provenance = Provenance(
            origin_platform_id=identity.platform_id,
            origin_core_id=identity.core_id,
            envelope_digest="0" * 64,
            authenticity=ProvenanceAuthenticity.AUTHENTICATED,
        )
        draft = ChatMessage(
            message_id=message_identifier,
            room_id=room_id,
            sender_core_id=identity.core_id,
            audience=selected_audience,
            body=body,
            created_at=moment,
            reply_to=reply_to,
            origin=MessageOrigin.LOCAL,
            sequence=allocated_sequence,
            provenance=draft_provenance,
        )
        digest = message_digest(draft)
        message = ChatMessage(
            message_id=draft.message_id,
            room_id=draft.room_id,
            sender_core_id=draft.sender_core_id,
            audience=draft.audience,
            body=draft.body,
            created_at=draft.created_at,
            reply_to=draft.reply_to,
            origin=draft.origin,
            sequence=draft.sequence,
            provenance=Provenance(
                origin_platform_id=identity.platform_id,
                origin_core_id=identity.core_id,
                envelope_digest=digest,
                authenticity=ProvenanceAuthenticity.AUTHENTICATED,
            ),
        )
        envelope = PeerEnvelope(
            message=message,
            source_platform_id=identity.platform_id,
            source_core_id=identity.core_id,
            source_generation=identity.generation,
            destination_platform_id=peer.remote_platform_id,
            destination_core_id=peer.remote_core_id,
            destination_generation=peer.remote_generation,
            idempotency_key=key,
            sent_at=now,
            expires_at=expiry,
            payload_digest=digest,
            protocol_version=str(self._protocol_range.maximum),
            content_type=SOCIAL_CONTRACT_VERSION,
        )
        record, duplicate = self.state.enqueue_outbox(envelope, now=now)
        if duplicate:
            return SendResult(record, envelope, duplicate=True)
        if self._transport is not None:
            authenticated = AuthenticatedPeer(
                platform_id=identity.platform_id,
                core_id=identity.core_id,
                generation=identity.generation,
                trust_anchor=self.trust_anchor,
                protocol_version=ProtocolVersion.parse(envelope.protocol_version),
            )
            try:
                receipt = self._transport.deliver(envelope, authenticated)
                if not isinstance(receipt, TransportReceipt):
                    receipt = TransportReceipt(
                        TransportOutcome.UNCERTAIN, "transport returned an invalid receipt",
                    )
            except Exception as exc:  # transport failure is uncertain, never success
                receipt = TransportReceipt(
                    TransportOutcome.UNCERTAIN, f"transport failure: {type(exc).__name__}",
                )
            record = self.state.record_send_attempt(
                envelope.message_id, outcome=receipt.outcome.value,
                detail=receipt.detail, now=self._now(),
            )
        return SendResult(record, envelope, duplicate=False)

    def send_to_room(
        self, room_id: RoomId, body: str, *, topic_idempotency: str | None = None, **kwargs,
    ) -> tuple[SendResult, ...]:
        """Send one recipient-specific envelope per active remote room member."""
        self._require_running()
        local = self.identity
        members = self.state.active_members(room_id)
        if not members:
            raise FederationRoomError("room has no active members")
        member_ids = {member.core_id for member in members}
        if local.core_id not in member_ids:
            raise FederationRoomError("local Core is not an active room member")
        results = []
        for peer in self.state.list_peers():
            if peer.remote_core_id not in member_ids or peer.state is not PeerState.ACTIVE:
                continue
            key = kwargs.get("idempotency_key")
            if topic_idempotency:
                key = f"{topic_idempotency}:{peer.remote_core_id}"
            results.append(self.send_message(peer.peer_id, room_id, body, idempotency_key=key, **{
                name: value for name, value in kwargs.items() if name != "idempotency_key"
            }))
        if not results:
            raise FederationPeerError("no active enrolled peer is a member of this room")
        return tuple(results)

    # ------------------------------------------------------------------
    # Receiving and negotiation
    # ------------------------------------------------------------------
    def _negotiate(self, envelope: PeerEnvelope) -> None:
        if envelope.content_type not in self._contracts:
            raise FederationSchemaMismatch("unsupported social contract schema")
        offered = ProtocolVersion.parse(envelope.protocol_version)
        if not self._protocol_range.contains(offered):
            raise FederationSchemaMismatch("unsupported federation protocol version")

    def _receive(self, envelope: PeerEnvelope, authenticated: AuthenticatedPeer) -> str:
        now = self._now()
        self._require_running()
        identity, _anchor = self.state.local_identity()
        if envelope.destination_platform_id != identity.platform_id:
            raise FederationIdentityError("envelope is addressed to another Platform")
        if envelope.destination_core_id != identity.core_id:
            raise FederationIdentityError("envelope is addressed to another Core identity")
        if envelope.destination_generation != identity.generation:
            raise FederationIdentityError(
                "envelope targets a stale or unknown destination writer generation"
            )
        self._negotiate(envelope)
        if authenticated.platform_id != envelope.source_platform_id:
            raise FederationIdentityError("authenticated Platform does not match envelope source")
        if authenticated.core_id != envelope.source_core_id:
            raise FederationIdentityError("authenticated Core does not match envelope sender")
        if authenticated.generation != envelope.source_generation:
            raise FederationIdentityError("authenticated writer generation does not match the sender")
        peer = self.state.peer_by_identity(
            envelope.source_platform_id, envelope.source_core_id,
        )
        if peer is None:
            raise FederationPeerError("sender Core is not an enrolled peer on this Platform")
        self.state.assert_peer_authorized(
            peer.peer_id, direction=ContactDirection.INBOUND, now=now,
            authenticated_platform_id=authenticated.platform_id,
            authenticated_core_id=authenticated.core_id,
            authenticated_generation=authenticated.generation,
            authenticated_trust_anchor=authenticated.trust_anchor,
        )
        if envelope.expires_at <= now:
            raise FederationPeerError("inbound envelope has expired")
        if envelope.sent_at > now + self._max_clock_skew:
            raise FederationIdentityError("sender clock is too far in the future")
        if envelope.message.provenance.envelope_digest != envelope.payload_digest:
            raise FederationIdentityError("message provenance digest does not match the envelope")
        room_kind = self.state.room_kind(envelope.message.room_id)
        sender_membership = self.state.require_active_member(
            envelope.message.room_id, envelope.source_core_id,
        )
        recipient_membership = self.state.require_active_member(
            envelope.message.room_id, identity.core_id,
        )
        if recipient_membership.history_from_sequence > envelope.message.sequence:
            raise FederationRoomError(
                "recipient membership history boundary excludes this message"
            )
        if sender_membership.epoch < 1:
            raise FederationRoomError("sender membership epoch is invalid")
        audience = envelope.message.audience
        if audience.room_id != envelope.message.room_id:
            raise FederationRoomError("audience room does not match the message room")
        if room_kind is RoomKind.DIRECT:
            if audience.kind is not AudienceKind.DIRECT:
                raise FederationRoomError("direct room requires a direct audience")
            if audience.direct_recipient() != identity.core_id:
                raise FederationRoomError("direct audience does not name this recipient Core")
        else:
            if audience.kind.value != room_kind.value:
                raise FederationRoomError("group audience kind does not match the room")
            if audience.recipient_core_ids:
                raise FederationRoomError("group audience cannot embed a recipient list")
        record, duplicate = self.state.record_inbound(envelope, now=now)
        if duplicate:
            return f"duplicate:{record.status.value}"
        return "RECEIVED"

    def receive(
        self, envelope: PeerEnvelope, authenticated: AuthenticatedPeer,
    ) -> TransportReceipt:
        if not isinstance(envelope, PeerEnvelope):
            raise TypeError("envelope must be PeerEnvelope")
        if not isinstance(authenticated, AuthenticatedPeer):
            raise TypeError("authenticated peer identity is required")
        try:
            detail = self._receive(envelope, authenticated)
        except (FederationConflict, FederationDenied, FederationReplay, FederationSchemaMismatch) as exc:
            return TransportReceipt(
                TransportOutcome.REJECTED, f"{type(exc).__name__}: {exc}",
            )
        return TransportReceipt(TransportOutcome.DELIVERED, detail)

    # ------------------------------------------------------------------
    # Inbox projections and decisions
    # ------------------------------------------------------------------
    def inbox_records(self) -> tuple[InboxRecord, ...]:
        return self.state.list_inbox()

    def outbox_records(self) -> tuple[OutboxRecord, ...]:
        return self.state.list_outbox()

    def _envelope_for_record(self, record: InboxRecord | OutboxRecord) -> PeerEnvelope:
        return PeerEnvelope.from_payload(json.loads(record.envelope_json))

    def inbound_message(self, message_id: UUID) -> InboundMessage:
        record = self.state.inbox_record(_bounded_uuid(message_id, "message_id"))
        if record is None:
            raise FederationPeerError("inbound message is unknown")
        envelope = self._envelope_for_record(record)
        return InboundMessage(
            message=envelope.message,
            source_platform_id=envelope.source_platform_id,
            untrusted=True,
        )

    def project(
        self, message_id: UUID, *, recipient_core_id: UUID | None = None,
    ) -> AudienceProjection:
        """Project one stored inbound message for the local authorized Core.

        The projection is recipient-specific: room membership and the
        ``history_from_sequence`` boundary are re-checked on every call.
        """
        identity = self.identity
        recipient = identity.core_id if recipient_core_id is None else _bounded_uuid(
            recipient_core_id, "recipient_core_id",
        )
        if recipient != identity.core_id:
            raise FederationRoomError("only the addressed local Core may project this message")
        record = self.state.inbox_record(_bounded_uuid(message_id, "message_id"))
        if record is None:
            raise FederationPeerError("inbound message is unknown")
        if record.status not in {
            DeliveryStatus.RECEIVED, DeliveryStatus.ACCEPTED, DeliveryStatus.HANDLED,
        }:
            raise FederationRoomError("message was not accepted for projection")
        envelope = self._envelope_for_record(record)
        membership = self.state.require_active_member(envelope.message.room_id, recipient)
        if membership.history_from_sequence > envelope.message.sequence:
            raise FederationRoomError("membership history boundary excludes this message")
        room_kind = self.state.room_kind(envelope.message.room_id)
        audience = envelope.message.audience
        if room_kind is RoomKind.DIRECT:
            if audience.direct_recipient() != recipient:
                raise FederationRoomError("direct audience does not name this recipient")
        elif audience.kind.value != room_kind.value:
            raise FederationRoomError("group audience kind does not match the room")
        return AudienceProjection(
            message_id=envelope.message.message_id,
            room_id=envelope.message.room_id,
            sender_core_id=envelope.message.sender_core_id,
            recipient_core_id=recipient,
            audience=audience,
            body=envelope.message.body,
            created_at=envelope.message.created_at,
            sequence=envelope.message.sequence,
            untrusted=True,
        )

    def decide_inbound(
        self, message_id: UUID, status: DeliveryStatus, *, detail: str | None = None,
    ) -> PeerAcknowledgment:
        """Record an independent local Core decision; returns an authenticated ack."""
        moment = self._now()
        identity = self.identity
        record = self.state.inbox_record(_bounded_uuid(message_id, "message_id"))
        if record is None:
            raise FederationPeerError("inbound message is unknown")
        if record.source_platform_id == identity.platform_id:
            raise FederationIdentityError("cannot decide a message from the local Platform")
        decided = self.state.decide_inbound(message_id, status, detail=detail, now=moment)
        return PeerAcknowledgment(
            message_id=decided.message_id,
            status=decided.status,
            acknowledging_platform_id=identity.platform_id,
            acknowledging_core_id=identity.core_id,
            acknowledged_at=moment,
        )

    def apply_ack(self, acknowledgment: PeerAcknowledgment) -> OutboxRecord:
        """Apply a terminal acknowledgment received over an authenticated channel."""
        if not isinstance(acknowledgment, PeerAcknowledgment):
            raise TypeError("acknowledgment must be PeerAcknowledgment")
        identity = self.identity
        record = self.state.outbox_record(acknowledgment.message_id)
        if record is None:
            raise FederationPeerError("acknowledged message is not in the local outbox")
        if (
            record.destination_platform_id != acknowledgment.acknowledging_platform_id
            or record.destination_core_id != acknowledgment.acknowledging_core_id
        ):
            raise FederationIdentityError(
                "acknowledging identity does not match the addressed outbox recipient"
            )
        if identity.platform_id == acknowledgment.acknowledging_platform_id:
            raise FederationIdentityError("a local Platform cannot acknowledge its own outbox")
        return self.state.record_recipient_ack(
            acknowledgment.message_id, acknowledgment.status,
            detail="recipient decision", now=self._now(),
        )

    # ------------------------------------------------------------------
    # Reconnect, retry and reconciliation
    # ------------------------------------------------------------------
    def resend_pending(self) -> tuple[OutboxRecord, ...]:
        """Retry queued/unconfirmed envelopes; receiver deduplicates by message id."""
        self._require_running()
        now = self._now()
        self.state.mark_outbox_expired(now)
        identity = self.identity
        results = []
        for record in self.state.pending_outbox(now=now):
            peer = self.state.peer_by_identity(
                record.destination_platform_id, record.destination_core_id,
            )
            if peer is None:
                results.append(record)
                continue
            try:
                self.state.assert_peer_authorized(
                    peer.peer_id, direction=ContactDirection.OUTBOUND, now=now,
                )
            except FederationDenied:
                results.append(self.state.record_recipient_ack(
                    record.message_id, DeliveryStatus.DENIED,
                    detail="peer is no longer authorized for outbound contact",
                    now=now,
                ))
                continue
            if self._transport is None:
                results.append(record)
                continue
            envelope = self._envelope_for_record(record)
            authenticated = AuthenticatedPeer(
                platform_id=identity.platform_id,
                core_id=identity.core_id,
                generation=identity.generation,
                trust_anchor=self.trust_anchor,
                protocol_version=ProtocolVersion.parse(envelope.protocol_version),
            )
            try:
                receipt = self._transport.deliver(envelope, authenticated)
                if not isinstance(receipt, TransportReceipt):
                    receipt = TransportReceipt(
                        TransportOutcome.UNCERTAIN, "transport returned an invalid receipt",
                    )
            except Exception as exc:
                receipt = TransportReceipt(
                    TransportOutcome.UNCERTAIN, f"transport failure: {type(exc).__name__}",
                )
            results.append(self.state.record_send_attempt(
                record.message_id, outcome=receipt.outcome.value,
                detail=receipt.detail, now=self._now(),
            ))
        return tuple(results)

    def reconcile(self, confirmed: Mapping[UUID, DeliveryStatus]) -> tuple[OutboxRecord, ...]:
        """Truthfully reconcile uncertain outcomes against durable evidence.

        A transport acknowledgement can establish ``RECEIVED`` only.  Terminal
        social decisions must arrive as an independent recipient
        acknowledgment; they are never inferred from delivery.
        """
        moment = self._now()
        results = []
        for message_id, status in confirmed.items():
            _bounded_uuid(message_id, "message_id")
            if not isinstance(status, DeliveryStatus):
                raise TypeError("reconciliation status must be DeliveryStatus")
            if status is DeliveryStatus.RECEIVED:
                results.append(self.state.reconcile_outbox_received(message_id, now=moment))
            elif status in {
                DeliveryStatus.ACCEPTED, DeliveryStatus.DECLINED, DeliveryStatus.DENIED,
                DeliveryStatus.EXPIRED, DeliveryStatus.HANDLED,
            }:
                results.append(self.state.record_recipient_ack(
                    message_id, status, detail="reconciled recipient decision", now=moment,
                ))
            else:
                raise ValueError("reconciliation requires RECEIVED or a terminal decision")
        return tuple(results)


__all__ = ["FederationNode", "SendResult", "DEFAULT_ENROLLMENT_TTL", "DEFAULT_MESSAGE_TTL"]
