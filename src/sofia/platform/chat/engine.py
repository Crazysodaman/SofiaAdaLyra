"""Durable, access-controlled multi-Core chat and channel engine.

Design boundaries:

* One canonical Platform state and one short SQLite write path. No second
  database, no shadow Core memory and no concurrent writer fan-out.
* Every read and every delivery is checked against the acting member's current
  membership epoch and history floor. A late join cannot read pre-join text
  unless the room explicitly granted a bounded history epoch.
* Core identity comes from the authenticated caller or verified peer envelope,
  never from message text. Peer text is stored as untrusted data.
* Chat messages grant no execution authority. ``stop_provider`` may suspend
  Core-originated outreach on operator STOP; owner local conversation remains.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Mapping
from uuid import UUID, uuid4

from sofia.platform.chat.contracts import (
    ActorKind,
    ChatActor,
    ChatAudience,
    ChatAuditEvent,
    ChatMessage,
    CoreIdentity,
    Draft,
    GENERAL_ROOM_ID,
    InvitationStatus,
    MAX_CORE_IDENTITIES,
    MAX_MESSAGE_BODY_BYTES,
    MembershipStatus,
    MessageOrigin,
    MessagePage,
    MessageProvenance,
    OutboxEntry,
    PeerEnvelope,
    RetentionResult,
    Room,
    RoomHistoryPolicy,
    RoomInvitation,
    RoomKind,
    RoomMembership,
    RoomSync,
    SyncResult,
)
from sofia.platform.chat.store import ChatStore


_ID_MAX = 160


def _text_id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _ID_MAX
        or not value[0].isalnum()
        or any(
            not (character.isalnum() or character in "_.:@/-")
            for character in value
        )
    ):
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _positive_int(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _audience_payload(audience: ChatAudience) -> str:
    return json.dumps(
        {
            "room_id": audience.room_id,
            "kind": audience.kind.value,
            "membership_epoch": audience.membership_epoch,
            "member_ids": list(audience.member_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _audience_from_payload(value: str) -> ChatAudience:
    data = json.loads(value)
    return ChatAudience(
        room_id=data["room_id"],
        kind=RoomKind(data["kind"]),
        membership_epoch=data["membership_epoch"],
        member_ids=tuple(data["member_ids"]),
    )


def _provenance_payload(provenance: MessageProvenance) -> str:
    return json.dumps(
        {
            "source_platform_id": provenance.source_platform_id,
            "source_generation": provenance.source_generation,
            "transport_verified": provenance.transport_verified,
            "untrusted_content": provenance.untrusted_content,
            "received_at": _iso(provenance.received_at),
            "idempotency_key": provenance.idempotency_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _provenance_from_payload(value: str) -> MessageProvenance:
    data = json.loads(value)
    return MessageProvenance(
        source_platform_id=data["source_platform_id"],
        source_generation=data["source_generation"],
        transport_verified=data["transport_verified"],
        untrusted_content=data["untrusted_content"],
        received_at=datetime.fromisoformat(data["received_at"]),
        idempotency_key=data.get("idempotency_key"),
    )


def _room_from_row(row: sqlite3.Row) -> Room:
    return Room(
        room_id=row["room_id"],
        kind=RoomKind(row["kind"]),
        name=row["name"],
        topic=row["topic"],
        created_at=datetime.fromisoformat(row["created_at"]),
        created_by=row["created_by"],
        owner_core_id=row["owner_core_id"],
        membership_epoch=row["membership_epoch"],
        history_policy=RoomHistoryPolicy(row["history_policy"]),
        retention_seconds=row["retention_seconds"],
        sequence=row["sequence"],
    )


def _membership_from_row(row: sqlite3.Row) -> RoomMembership:
    return RoomMembership(
        room_id=row["room_id"],
        core_id=row["core_id"],
        epoch=row["epoch"],
        status=MembershipStatus(row["status"]),
        joined_at=_dt(row["joined_at"]),
        history_from_sequence=row["history_from_sequence"],
        member_kind=ActorKind(row["member_kind"]),
        invited_by=row["invited_by"],
        removed_by=row["removed_by"],
        left_at=_dt(row["left_at"]),
    )


def _invitation_from_row(row: sqlite3.Row) -> RoomInvitation:
    return RoomInvitation(
        invite_id=row["invite_id"],
        room_id=row["room_id"],
        invitee_id=row["invitee_id"],
        invited_by=row["invited_by"],
        status=InvitationStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=_dt(row["expires_at"]),
        history_from_sequence=row["history_from_sequence"],
        epoch=row["epoch"],
    )


def _message_from_row(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        message_id=row["message_id"],
        room_id=row["room_id"],
        sender_core_id=row["sender_id"],
        audience=_audience_from_payload(row["audience_json"]),
        body=row["body"],
        created_at=datetime.fromisoformat(row["created_at"]),
        reply_to=row["reply_to"],
        origin=MessageOrigin(row["origin"]),
        sequence=row["sequence"],
        provenance=_provenance_from_payload(row["provenance_json"]),
        edited_at=_dt(row["edited_at"]),
        revision=row["revision"],
        deleted_at=_dt(row["deleted_at"]),
        deleted_by=row["deleted_by"],
    )


class ChatEngine:
    """Platform-owned multi-Core chat, channel, inbox and history service."""

    def __init__(
        self,
        state_path: Path | str,
        *,
        owner_id: str = "platform:owner",
        platform_id: str = "platform:local",
        clock: Callable[[], datetime] | None = None,
        stop_provider: Callable[[], bool] | None = None,
        max_cores: int | None = MAX_CORE_IDENTITIES,
    ) -> None:
        self._owner_id = _text_id(owner_id, "owner_id")
        self._platform_id = _text_id(platform_id, "platform_id")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if stop_provider is not None and not callable(stop_provider):
            raise TypeError("stop_provider must be callable")
        if max_cores is not None:
            _positive_int(max_cores, "max_cores")
        self._clock = clock
        self._stop_provider = stop_provider
        self._max_cores = max_cores
        self._store = ChatStore(state_path)
        self._ensure_general(self._now())

    # ------------------------------------------------------------------
    # Identity and authenticated actor projection
    # ------------------------------------------------------------------
    @property
    def owner_id(self) -> str:
        return self._owner_id

    @property
    def platform_id(self) -> str:
        return self._platform_id

    @property
    def state_path(self) -> Path:
        return self._store.path

    def owner_actor(self) -> ChatActor:
        return ChatActor.owner(self._owner_id)

    def _now(self) -> datetime:
        value = self._clock() if self._clock is not None else datetime.now(timezone.utc)
        return _aware(value, "clock result")

    def _is_stopped(self) -> bool:
        if self._stop_provider is None:
            return False
        return bool(self._stop_provider())

    def _authorize_actor(self, db: sqlite3.Connection, actor: ChatActor) -> None:
        if not isinstance(actor, ChatActor):
            raise TypeError("actor must be a ChatActor")
        if actor.kind is ActorKind.OWNER:
            if actor.actor_id != self._owner_id:
                raise PermissionError("owner actor is not the configured Platform owner")
            return
        identity = actor.identity
        assert identity is not None
        row = db.execute(
            "SELECT platform_id, generation, authorized FROM chat_core WHERE core_id=?",
            (identity.core_id_text,),
        ).fetchone()
        if row is None:
            raise PermissionError("Core is not enrolled on this Platform")
        if row["authorized"] != 1:
            raise PermissionError("Core authorization has been revoked")
        if row["platform_id"] != identity.platform_id:
            raise PermissionError("Core platform binding does not match enrollment")
        if row["generation"] != identity.generation:
            raise PermissionError("stale or fenced Core generation")

    def _authorize_peer(
        self, db: sqlite3.Connection, peer: CoreIdentity
    ) -> sqlite3.Row:
        if not isinstance(peer, CoreIdentity):
            raise TypeError("peer must be a CoreIdentity")
        row = db.execute(
            "SELECT * FROM chat_core WHERE core_id=?",
            (peer.core_id_text,),
        ).fetchone()
        if row is None:
            raise PermissionError("peer Core is not enrolled on this Platform")
        if row["authorized"] != 1:
            raise PermissionError("peer Core authorization has been revoked")
        if row["platform_id"] != peer.platform_id:
            raise PermissionError("peer platform binding does not match enrollment")
        if row["generation"] != peer.generation:
            raise PermissionError("peer Core generation is stale or fenced")
        return row

    def register_core(
        self,
        identity: CoreIdentity,
        *,
        authorize: bool = True,
    ) -> CoreIdentity:
        """Register an independently issued Core identity and join #general."""
        if not isinstance(identity, CoreIdentity):
            raise TypeError("identity must be a CoreIdentity")
        if type(authorize) is not bool:
            raise TypeError("authorize must be bool")
        at = self._now()
        with self._store.transaction() as db:
            existing = db.execute(
                "SELECT * FROM chat_core WHERE core_id=?",
                (identity.core_id_text,),
            ).fetchone()
            if existing is None:
                if self._max_cores is not None:
                    count = db.execute(
                        "SELECT COUNT(*) FROM chat_core WHERE authorized=1"
                    ).fetchone()[0]
                    if authorize and count >= self._max_cores:
                        raise ValueError(
                            "configured Core identity limit reached; "
                            "independent Cores must use separate enrolled identities"
                        )
                db.execute(
                    """
                    INSERT INTO chat_core(
                        core_id, platform_id, generation, display_name,
                        authorized, registered_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        identity.core_id_text,
                        identity.platform_id,
                        identity.generation,
                        identity.display_name,
                        1 if authorize else 0,
                        _iso(at),
                        _iso(at),
                    ),
                )
                event = "core.registered"
            else:
                if existing["platform_id"] != identity.platform_id:
                    raise PermissionError(
                        "Core identity is already bound to another Platform lineage"
                    )
                if identity.generation < existing["generation"]:
                    raise PermissionError("stale Core generation cannot be registered")
                db.execute(
                    """
                    UPDATE chat_core
                    SET generation=?, display_name=?, authorized=?, updated_at=?
                    WHERE core_id=?
                    """,
                    (
                        identity.generation,
                        identity.display_name,
                        1 if authorize else 0,
                        _iso(at),
                        identity.core_id_text,
                    ),
                )
                event = "core.reauthorized"
            room = self._room(db, GENERAL_ROOM_ID)
            self._activate_general_member(db, identity.core_id_text, at)
            self._audit(
                db,
                actor_id=identity.core_id_text,
                event_type=event,
                room_id=room.room_id,
                at=at,
                platform_id=identity.platform_id,
                generation=identity.generation,
                display_name=identity.display_name,
                authorized=authorize,
            )
        return identity

    def revoke_core(
        self,
        actor: ChatActor,
        core_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        _text_id(core_id, "core_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if actor.kind is not ActorKind.OWNER:
                raise PermissionError("only the Platform owner may revoke a Core")
            row = db.execute(
                "SELECT * FROM chat_core WHERE core_id=?", (core_id,)
            ).fetchone()
            if row is None:
                raise LookupError("Core is not enrolled")
            if row["authorized"] == 0:
                return
            db.execute(
                "UPDATE chat_core SET authorized=0, updated_at=? WHERE core_id=?",
                (_iso(at), core_id),
            )
            rooms = db.execute(
                "SELECT room_id FROM chat_membership WHERE core_id=? AND status=?",
                (core_id, MembershipStatus.ACTIVE.value),
            ).fetchall()
            for room_row in rooms:
                room_id = room_row["room_id"]
                epoch = self._bump_epoch(db, room_id)
                db.execute(
                    """
                    UPDATE chat_membership
                    SET status=?, epoch=?, removed_by=?, left_at=?, updated_at=?
                    WHERE room_id=? AND core_id=?
                    """,
                    (
                        MembershipStatus.REVOKED.value,
                        epoch,
                        actor.actor_id,
                        _iso(at),
                        _iso(at),
                        room_id,
                        core_id,
                    ),
                )
                self._audit(
                    db,
                    actor_id=actor.actor_id,
                    event_type="membership.revoked",
                    room_id=room_id,
                    at=at,
                    target_id=core_id,
                    reason=reason,
                    epoch=epoch,
                )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="core.revoked",
                room_id=GENERAL_ROOM_ID,
                at=at,
                target_id=core_id,
                reason=reason,
            )

    def core_identity(self, core_id: str) -> CoreIdentity | None:
        _text_id(core_id, "core_id")
        with self._store.reader() as db:
            row = db.execute(
                "SELECT * FROM chat_core WHERE core_id=?", (core_id,)
            ).fetchone()
        if row is None:
            return None
        return CoreIdentity(
            core_id=UUID(row["core_id"]),
            platform_id=row["platform_id"],
            generation=row["generation"],
            display_name=row["display_name"],
        )

    def core_identities(self) -> tuple[CoreIdentity, ...]:
        with self._store.reader() as db:
            rows = db.execute(
                "SELECT * FROM chat_core WHERE authorized=1 ORDER BY core_id"
            ).fetchall()
        return tuple(
            CoreIdentity(
                core_id=UUID(row["core_id"]),
                platform_id=row["platform_id"],
                generation=row["generation"],
                display_name=row["display_name"],
            )
            for row in rows
        )

    # ------------------------------------------------------------------
    # Rooms, invitations and membership lifecycle
    # ------------------------------------------------------------------
    def _ensure_general(self, at: datetime) -> None:
        with self._store.transaction() as db:
            self._ensure_general_in_transaction(db, at)

    def _ensure_general_in_transaction(
        self, db: sqlite3.Connection, at: datetime
    ) -> None:
        row = db.execute(
            "SELECT * FROM chat_room WHERE room_id=?", (GENERAL_ROOM_ID,)
        ).fetchone()
        if row is None:
            db.execute(
                """
                INSERT INTO chat_room(
                    room_id, kind, name, topic, created_at, created_by,
                    owner_core_id, membership_epoch, history_policy,
                    retention_seconds, sequence
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    GENERAL_ROOM_ID,
                    RoomKind.GENERAL.value,
                    "#general",
                    "Shared Platform room for the owner and authorized Cores.",
                    _iso(at),
                    self._owner_id,
                    None,
                    1,
                    RoomHistoryPolicy.FULL_HISTORY.value,
                    None,
                    0,
                ),
            )
            self._audit(
                db,
                actor_id=self._owner_id,
                event_type="room.created",
                room_id=GENERAL_ROOM_ID,
                at=at,
                kind=RoomKind.GENERAL.value,
            )
        membership = db.execute(
            "SELECT * FROM chat_membership WHERE room_id=? AND core_id=?",
            (GENERAL_ROOM_ID, self._owner_id),
        ).fetchone()
        if membership is None:
            db.execute(
                """
                INSERT INTO chat_membership(
                    room_id, core_id, member_kind, epoch, status, joined_at,
                    history_from_sequence, invited_by, invite_expires_at,
                    removed_by, left_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    GENERAL_ROOM_ID,
                    self._owner_id,
                    ActorKind.OWNER.value,
                    db.execute(
                        "SELECT membership_epoch FROM chat_room WHERE room_id=?",
                        (GENERAL_ROOM_ID,),
                    ).fetchone()[0],
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    None,
                    None,
                    None,
                    None,
                    _iso(at),
                ),
            )
            self._audit(
                db,
                actor_id=self._owner_id,
                event_type="membership.joined",
                room_id=GENERAL_ROOM_ID,
                at=at,
                target_id=self._owner_id,
                history_from_sequence=1,
            )
        elif membership["status"] != MembershipStatus.ACTIVE.value:
            epoch = self._bump_epoch(db, GENERAL_ROOM_ID)
            db.execute(
                """
                UPDATE chat_membership
                SET epoch=?, status=?, joined_at=?, history_from_sequence=?,
                    removed_by=NULL, left_at=NULL, updated_at=?
                WHERE room_id=? AND core_id=?
                """,
                (
                    epoch,
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    _iso(at),
                    GENERAL_ROOM_ID,
                    self._owner_id,
                ),
            )
            self._audit(
                db,
                actor_id=self._owner_id,
                event_type="membership.joined",
                room_id=GENERAL_ROOM_ID,
                at=at,
                target_id=self._owner_id,
                history_from_sequence=1,
                epoch=epoch,
            )

    def _activate_general_member(
        self, db: sqlite3.Connection, member_id: str, at: datetime
    ) -> RoomMembership:
        row = db.execute(
            "SELECT * FROM chat_membership WHERE room_id=? AND core_id=?",
            (GENERAL_ROOM_ID, member_id),
        ).fetchone()
        if row is not None and row["status"] == MembershipStatus.ACTIVE.value:
            return _membership_from_row(row)
        epoch = self._bump_epoch(db, GENERAL_ROOM_ID)
        if row is None:
            db.execute(
                """
                INSERT INTO chat_membership(
                    room_id, core_id, member_kind, epoch, status, joined_at,
                    history_from_sequence, invited_by, invite_expires_at,
                    removed_by, left_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    GENERAL_ROOM_ID,
                    member_id,
                    ActorKind.CORE.value,
                    epoch,
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    None,
                    None,
                    None,
                    None,
                    _iso(at),
                ),
            )
        else:
            db.execute(
                """
                UPDATE chat_membership
                SET epoch=?, status=?, joined_at=?, history_from_sequence=?,
                    removed_by=NULL, left_at=NULL, updated_at=?
                WHERE room_id=? AND core_id=?
                """,
                (
                    epoch,
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    _iso(at),
                    GENERAL_ROOM_ID,
                    member_id,
                ),
            )
        self._audit(
            db,
            actor_id=member_id,
            event_type="membership.joined",
            room_id=GENERAL_ROOM_ID,
            at=at,
            target_id=member_id,
            history_from_sequence=1,
            epoch=epoch,
        )
        return _membership_from_row(
            db.execute(
                "SELECT * FROM chat_membership WHERE room_id=? AND core_id=?",
                (GENERAL_ROOM_ID, member_id),
            ).fetchone()
        )

    def _room(self, db: sqlite3.Connection, room_id: str) -> Room:
        row = db.execute(
            "SELECT * FROM chat_room WHERE room_id=?", (room_id,)
        ).fetchone()
        if row is None:
            raise LookupError("room does not exist")
        return _room_from_row(row)

    def _membership(
        self, db: sqlite3.Connection, room_id: str, core_id: str
    ) -> RoomMembership | None:
        row = db.execute(
            "SELECT * FROM chat_membership WHERE room_id=? AND core_id=?",
            (room_id, core_id),
        ).fetchone()
        return None if row is None else _membership_from_row(row)

    def _require_active(
        self, db: sqlite3.Connection, room_id: str, actor: ChatActor
    ) -> RoomMembership:
        membership = self._membership(db, room_id, actor.actor_id)
        if membership is None or membership.status is not MembershipStatus.ACTIVE:
            raise PermissionError("actor is not an active member of this room")
        return membership

    def _require_room_admin(
        self,
        db: sqlite3.Connection,
        room: Room,
        actor: ChatActor,
        *,
        allow_platform_owner: bool = True,
    ) -> None:
        if allow_platform_owner and actor.kind is ActorKind.OWNER:
            if actor.actor_id == self._owner_id:
                return
        self._require_active(db, room.room_id, actor)
        if room.owner_core_id != actor.actor_id:
            raise PermissionError("actor is not the owner Core of this room")

    def _bump_epoch(self, db: sqlite3.Connection, room_id: str) -> int:
        db.execute(
            "UPDATE chat_room SET membership_epoch=membership_epoch+1 WHERE room_id=?",
            (room_id,),
        )
        row = db.execute(
            "SELECT membership_epoch FROM chat_room WHERE room_id=?", (room_id,)
        ).fetchone()
        if row is None:
            raise LookupError("room does not exist")
        return row[0]

    def _active_members(
        self, db: sqlite3.Connection, room_id: str
    ) -> tuple[RoomMembership, ...]:
        rows = db.execute(
            "SELECT * FROM chat_membership WHERE room_id=? AND status=? "
            "ORDER BY core_id",
            (room_id, MembershipStatus.ACTIVE.value),
        ).fetchall()
        return tuple(_membership_from_row(row) for row in rows)

    def _audience(self, db: sqlite3.Connection, room: Room) -> ChatAudience:
        members = self._active_members(db, room.room_id)
        if not members:
            raise PermissionError("room has no active members")
        return ChatAudience(
            room_id=room.room_id,
            kind=room.kind,
            membership_epoch=room.membership_epoch,
            member_ids=tuple(member.core_id for member in members),
        )

    def _audit(
        self,
        db: sqlite3.Connection,
        *,
        actor_id: str,
        event_type: str,
        room_id: str,
        at: datetime,
        **payload: object,
    ) -> None:
        document = {"room_id": room_id}
        for key, value in payload.items():
            if isinstance(value, datetime):
                document[key] = _iso(value)
            else:
                document[key] = value
        self._store.audit.append_in_transaction(
            db,
            actor_id=actor_id,
            event_type=f"chat.{event_type}",
            payload=document,
            occurred_at=at,
        )

    def _blocked_pair(
        self, db: sqlite3.Connection, left: str, right: str
    ) -> bool:
        row = db.execute(
            """
            SELECT 1 FROM chat_block
            WHERE (blocker_id=? AND blocked_id=?)
               OR (blocker_id=? AND blocked_id=?)
            LIMIT 1
            """,
            (left, right, right, left),
        ).fetchone()
        return row is not None

    def room(self, actor: ChatActor, room_id: str) -> Room:
        _text_id(room_id, "room_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            self._require_active(db, room_id, actor)
            return room

    def rooms(self, actor: ChatActor) -> tuple[Room, ...]:
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            rows = db.execute(
                """
                SELECT r.* FROM chat_room AS r
                JOIN chat_membership AS m ON m.room_id=r.room_id
                WHERE m.core_id=? AND m.status=?
                ORDER BY r.created_at, r.room_id
                """,
                (actor.actor_id, MembershipStatus.ACTIVE.value),
            ).fetchall()
            return tuple(_room_from_row(row) for row in rows)

    def create_group(
        self,
        actor: ChatActor,
        name: str,
        *,
        topic: str = "",
        member_ids: Iterable[str] = (),
        history_policy: RoomHistoryPolicy = RoomHistoryPolicy.NO_PRE_JOIN,
        retention_seconds: int | None = None,
    ) -> Room:
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("name must be nonempty and bounded")
        if not isinstance(topic, str) or len(topic) > 2000:
            raise ValueError("topic must be bounded text")
        if not isinstance(history_policy, RoomHistoryPolicy):
            raise TypeError("history_policy must be a RoomHistoryPolicy")
        if retention_seconds is not None:
            _positive_int(retention_seconds, "retention_seconds")
        if isinstance(member_ids, (str, bytes)):
            raise TypeError("member_ids must be an iterable of identifiers")
        targets = tuple(dict.fromkeys(member_ids))
        for target in targets:
            _text_id(target, "member_id")
            if target in (actor.actor_id, self._owner_id):
                continue
            if self.core_identity(target) is None:
                raise PermissionError("invited Core is not enrolled")
        at = self._now()
        room_id = f"group:{uuid4()}"
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            db.execute(
                """
                INSERT INTO chat_room(
                    room_id, kind, name, topic, created_at, created_by,
                    owner_core_id, membership_epoch, history_policy,
                    retention_seconds, sequence
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    room_id,
                    RoomKind.PRIVATE_GROUP.value,
                    name.strip(),
                    topic,
                    _iso(at),
                    actor.actor_id,
                    actor.actor_id if actor.kind is ActorKind.CORE else None,
                    1,
                    history_policy.value,
                    retention_seconds,
                    0,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="room.created",
                room_id=room_id,
                at=at,
                kind=RoomKind.PRIVATE_GROUP.value,
                name=name.strip(),
            )
            db.execute(
                """
                INSERT INTO chat_membership(
                    room_id, core_id, member_kind, epoch, status, joined_at,
                    history_from_sequence, invited_by, invite_expires_at,
                    removed_by, left_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    room_id,
                    actor.actor_id,
                    actor.kind.value,
                    1,
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    actor.actor_id,
                    None,
                    None,
                    None,
                    _iso(at),
                ),
            )
            for target in targets:
                if target in (actor.actor_id, self._owner_id):
                    continue
                self._invite_in_transaction(
                    db,
                    actor=actor,
                    room=self._room(db, room_id),
                    invitee_id=target,
                    history_from_sequence=None,
                    expires_at=None,
                    at=at,
                )
            return self._room(db, room_id)

    def _direct_room_id(self, left: str, right: str) -> str:
        digest = sha256(
            "|".join(sorted((left, right))).encode("utf-8")
        ).hexdigest()
        return f"direct:{digest}"

    def open_direct(self, actor: ChatActor, other_id: str) -> Room:
        _text_id(other_id, "other_id")
        if other_id == actor.actor_id:
            raise ValueError("cannot open a direct room with self")
        other = self.core_identity(other_id)
        if other is None:
            raise PermissionError("direct recipient Core is not enrolled")
        if actor.kind is ActorKind.CORE and other_id == self._owner_id:
            raise PermissionError("the owner must initiate owner-to-Core conversation")
        at = self._now()
        room_id = self._direct_room_id(actor.actor_id, other_id)
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            existing = db.execute(
                "SELECT * FROM chat_room WHERE room_id=?", (room_id,)
            ).fetchone()
            if existing is not None:
                room = _room_from_row(existing)
                membership = self._membership(db, room_id, actor.actor_id)
                if membership is None or not membership.is_active:
                    raise PermissionError("actor is no longer a member of this direct room")
                return room
            if self._blocked_pair(db, actor.actor_id, other_id):
                raise PermissionError("direct conversation is blocked")
            name = f"Direct: {actor.actor_id} / {other_id}"
            db.execute(
                """
                INSERT INTO chat_room(
                    room_id, kind, name, topic, created_at, created_by,
                    owner_core_id, membership_epoch, history_policy,
                    retention_seconds, sequence
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    room_id,
                    RoomKind.DIRECT.value,
                    name[:200],
                    "",
                    _iso(at),
                    actor.actor_id,
                    actor.actor_id if actor.kind is ActorKind.CORE else None,
                    1,
                    RoomHistoryPolicy.NO_PRE_JOIN.value,
                    None,
                    0,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="room.created",
                room_id=room_id,
                at=at,
                kind=RoomKind.DIRECT.value,
            )
            db.execute(
                """
                INSERT INTO chat_membership(
                    room_id, core_id, member_kind, epoch, status, joined_at,
                    history_from_sequence, invited_by, invite_expires_at,
                    removed_by, left_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    room_id,
                    actor.actor_id,
                    actor.kind.value,
                    1,
                    MembershipStatus.ACTIVE.value,
                    _iso(at),
                    1,
                    actor.actor_id,
                    None,
                    None,
                    None,
                    _iso(at),
                ),
            )
            if actor.kind is ActorKind.OWNER:
                db.execute(
                    """
                    INSERT INTO chat_membership(
                        room_id, core_id, member_kind, epoch, status, joined_at,
                        history_from_sequence, invited_by, invite_expires_at,
                        removed_by, left_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        room_id,
                        other_id,
                        ActorKind.CORE.value,
                        1,
                        MembershipStatus.ACTIVE.value,
                        _iso(at),
                        1,
                        actor.actor_id,
                        None,
                        None,
                        None,
                        _iso(at),
                    ),
                )
                self._audit(
                    db,
                    actor_id=actor.actor_id,
                    event_type="membership.joined",
                    room_id=room_id,
                    at=at,
                    target_id=other_id,
                    history_from_sequence=1,
                )
            else:
                self._invite_in_transaction(
                    db,
                    actor=actor,
                    room=self._room(db, room_id),
                    invitee_id=other_id,
                    history_from_sequence=None,
                    expires_at=None,
                    at=at,
                )
            return self._room(db, room_id)

    def invite(
        self,
        actor: ChatActor,
        room_id: str,
        core_id: str,
        *,
        history_from_sequence: int | None = None,
        expires_at: datetime | None = None,
    ) -> RoomInvitation:
        _text_id(room_id, "room_id")
        _text_id(core_id, "core_id")
        if history_from_sequence is not None:
            _positive_int(history_from_sequence, "history_from_sequence")
        if expires_at is not None:
            expires_at = _aware(expires_at, "expires_at")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if room.kind is RoomKind.GENERAL:
                raise ValueError("general membership is automatic for authorized Cores")
            if room.kind is RoomKind.DIRECT:
                raise ValueError("direct rooms have fixed membership")
            self._require_room_admin(db, room, actor)
            if self.core_identity(core_id) is None:
                raise PermissionError("invited Core is not enrolled")
            if self._blocked_pair(db, actor.actor_id, core_id):
                raise PermissionError("invitation is blocked")
            return self._invite_in_transaction(
                db,
                actor=actor,
                room=room,
                invitee_id=core_id,
                history_from_sequence=history_from_sequence,
                expires_at=expires_at,
                at=at,
            )

    def _invite_in_transaction(
        self,
        db: sqlite3.Connection,
        *,
        actor: ChatActor,
        room: Room,
        invitee_id: str,
        history_from_sequence: int | None,
        expires_at: datetime | None,
        at: datetime,
    ) -> RoomInvitation:
        if room.history_policy is not RoomHistoryPolicy.EXPLICIT_GRANT:
            if history_from_sequence is not None:
                raise PermissionError(
                    "room history policy does not permit a pre-join history grant"
                )
        else:
            if history_from_sequence is not None:
                if history_from_sequence > room.sequence:
                    raise ValueError("history grant exceeds the current room sequence")
        current = self._membership(db, room.room_id, invitee_id)
        if current is not None and current.status is MembershipStatus.ACTIVE:
            raise ValueError("Core is already an active member")
        epoch = self._bump_epoch(db, room.room_id)
        invite_id = f"invite:{uuid4()}"
        db.execute(
            """
            INSERT INTO chat_invitation(
                invite_id, room_id, invitee_id, invited_by, status,
                created_at, expires_at, history_from_sequence, epoch, resolved_at
            ) VALUES (?,?,?,?,?,?,?,?,?,NULL)
            """,
            (
                invite_id,
                room.room_id,
                invitee_id,
                actor.actor_id,
                InvitationStatus.PENDING.value,
                _iso(at),
                None if expires_at is None else _iso(expires_at),
                history_from_sequence,
                epoch,
            ),
        )
        db.execute(
            """
            INSERT INTO chat_membership(
                room_id, core_id, member_kind, epoch, status, joined_at,
                history_from_sequence, invited_by, invite_expires_at,
                removed_by, left_at, updated_at
            ) VALUES (?,?,?,?,?,NULL,?,?,?,NULL,NULL,?)
            ON CONFLICT(room_id, core_id) DO UPDATE SET
                epoch=excluded.epoch,
                status=excluded.status,
                joined_at=NULL,
                history_from_sequence=excluded.history_from_sequence,
                invited_by=excluded.invited_by,
                invite_expires_at=excluded.invite_expires_at,
                removed_by=NULL,
                left_at=NULL,
                updated_at=excluded.updated_at
            """,
            (
                room.room_id,
                invitee_id,
                ActorKind.CORE.value,
                epoch,
                MembershipStatus.INVITED.value,
                history_from_sequence,
                actor.actor_id,
                None if expires_at is None else _iso(expires_at),
                _iso(at),
            ),
        )
        self._audit(
            db,
            actor_id=actor.actor_id,
            event_type="membership.invited",
            room_id=room.room_id,
            at=at,
            target_id=invitee_id,
            invite_id=invite_id,
            epoch=epoch,
            history_from_sequence=history_from_sequence,
            expires_at=None if expires_at is None else _iso(expires_at),
        )
        return _invitation_from_row(
            db.execute(
                "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
            ).fetchone()
        )

    def pending_invitations(
        self,
        actor: ChatActor,
        *,
        room_id: str | None = None,
    ) -> tuple[RoomInvitation, ...]:
        if room_id is not None:
            _text_id(room_id, "room_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            if actor.kind is ActorKind.OWNER:
                if room_id is None:
                    rows = db.execute(
                        "SELECT * FROM chat_invitation WHERE status=? ORDER BY created_at",
                        (InvitationStatus.PENDING.value,),
                    ).fetchall()
                else:
                    rows = db.execute(
                        "SELECT * FROM chat_invitation WHERE status=? AND room_id=? "
                        "ORDER BY created_at",
                        (InvitationStatus.PENDING.value, room_id),
                    ).fetchall()
            else:
                if room_id is None:
                    rows = db.execute(
                        "SELECT * FROM chat_invitation WHERE status=? AND "
                        "(invitee_id=? OR invited_by=?) ORDER BY created_at",
                        (InvitationStatus.PENDING.value, actor.actor_id, actor.actor_id),
                    ).fetchall()
                else:
                    rows = db.execute(
                        "SELECT * FROM chat_invitation WHERE status=? AND room_id=? AND "
                        "(invitee_id=? OR invited_by=?) ORDER BY created_at",
                        (
                            InvitationStatus.PENDING.value,
                            room_id,
                            actor.actor_id,
                            actor.actor_id,
                        ),
                    ).fetchall()
            return tuple(_invitation_from_row(row) for row in rows)

    def invitation(self, actor: ChatActor, invite_id: str) -> RoomInvitation:
        _text_id(invite_id, "invite_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            row = db.execute(
                "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
            ).fetchone()
            if row is None:
                raise LookupError("invitation does not exist")
            invitation = _invitation_from_row(row)
            if (
                actor.kind is not ActorKind.OWNER
                and actor.actor_id not in (invitation.invitee_id, invitation.invited_by)
            ):
                room = self._room(db, invitation.room_id)
                self._require_room_admin(db, room, actor)
            return invitation

    def _resolve_invitation(
        self,
        db: sqlite3.Connection,
        invitation: RoomInvitation,
        *,
        status: InvitationStatus,
        membership_status: MembershipStatus,
        actor_id: str,
        at: datetime,
        event: str,
        reason: str | None = None,
        joined: bool = False,
    ) -> None:
        room = self._room(db, invitation.room_id)
        epoch = self._bump_epoch(db, room.room_id)
        db.execute(
            """
            UPDATE chat_invitation
            SET status=?, resolved_at=?
            WHERE invite_id=? AND status=?
            """,
            (
                status.value,
                _iso(at),
                invitation.invite_id,
                InvitationStatus.PENDING.value,
            ),
        )
        history_floor = (
            invitation.history_from_sequence
            if invitation.history_from_sequence is not None
            else room.sequence + 1
        )
        db.execute(
            """
            UPDATE chat_membership
            SET epoch=?, status=?, joined_at=?, history_from_sequence=?,
                removed_by=?, left_at=?, updated_at=?
            WHERE room_id=? AND core_id=?
            """,
            (
                epoch,
                membership_status.value,
                _iso(at) if joined else None,
                history_floor if joined else None,
                None if joined else actor_id,
                None if joined else _iso(at),
                _iso(at),
                invitation.room_id,
                invitation.invitee_id,
            ),
        )
        self._audit(
            db,
            actor_id=actor_id,
            event_type=event,
            room_id=invitation.room_id,
            at=at,
            target_id=invitation.invitee_id,
            invite_id=invitation.invite_id,
            epoch=epoch,
            history_from_sequence=history_floor if joined else None,
            reason=reason,
        )

    def accept_invitation(
        self, actor: ChatActor, invite_id: str
    ) -> RoomMembership:
        _text_id(invite_id, "invite_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if actor.kind is not ActorKind.CORE:
                raise PermissionError("only the invited Core may accept")
            row = db.execute(
                "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
            ).fetchone()
            if row is None:
                raise LookupError("invitation does not exist")
            invitation = _invitation_from_row(row)
            if invitation.invitee_id != actor.actor_id:
                raise PermissionError("invitation belongs to another Core")
            if invitation.status is not InvitationStatus.PENDING:
                raise ValueError("invitation is no longer pending")
            room = self._room(db, invitation.room_id)
            if self._blocked_pair(db, actor.actor_id, invitation.invited_by):
                self._resolve_invitation(
                    db,
                    invitation,
                    status=InvitationStatus.REVOKED,
                    membership_status=MembershipStatus.BLOCKED,
                    actor_id=actor.actor_id,
                    at=at,
                    event="permission.invitation_blocked",
                    reason="blocked pair",
                )
                raise PermissionError("invitation is blocked")
            if invitation.expires_at is not None and at > invitation.expires_at:
                self._resolve_invitation(
                    db,
                    invitation,
                    status=InvitationStatus.EXPIRED,
                    membership_status=MembershipStatus.EXPIRED,
                    actor_id="system:expiry",
                    at=at,
                    event="membership.expired",
                    reason="invitation expired",
                )
                raise PermissionError("invitation has expired")
            self._resolve_invitation(
                db,
                invitation,
                status=InvitationStatus.ACCEPTED,
                membership_status=MembershipStatus.ACTIVE,
                actor_id=actor.actor_id,
                at=at,
                event="membership.accepted",
                joined=True,
            )
            return _membership_from_row(
                db.execute(
                    "SELECT * FROM chat_membership WHERE room_id=? AND core_id=?",
                    (room.room_id, actor.actor_id),
                ).fetchone()
            )

    def decline_invitation(
        self, actor: ChatActor, invite_id: str
    ) -> RoomInvitation:
        _text_id(invite_id, "invite_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if actor.kind is not ActorKind.CORE:
                raise PermissionError("only the invited Core may decline")
            row = db.execute(
                "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
            ).fetchone()
            if row is None:
                raise LookupError("invitation does not exist")
            invitation = _invitation_from_row(row)
            if invitation.invitee_id != actor.actor_id:
                raise PermissionError("invitation belongs to another Core")
            if invitation.status is not InvitationStatus.PENDING:
                raise ValueError("invitation is no longer pending")
            self._resolve_invitation(
                db,
                invitation,
                status=InvitationStatus.DECLINED,
                membership_status=MembershipStatus.DECLINED,
                actor_id=actor.actor_id,
                at=at,
                event="membership.declined",
            )
            return _invitation_from_row(
                db.execute(
                    "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
                ).fetchone()
            )

    def revoke_invitation(self, actor: ChatActor, invite_id: str) -> None:
        _text_id(invite_id, "invite_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            row = db.execute(
                "SELECT * FROM chat_invitation WHERE invite_id=?", (invite_id,)
            ).fetchone()
            if row is None:
                raise LookupError("invitation does not exist")
            invitation = _invitation_from_row(row)
            if invitation.status is not InvitationStatus.PENDING:
                raise ValueError("invitation is no longer pending")
            room = self._room(db, invitation.room_id)
            permitted = (
                actor.kind is ActorKind.OWNER
                or actor.actor_id in (invitation.invited_by, invitation.invitee_id)
            )
            if not permitted:
                self._require_room_admin(db, room, actor)
            self._resolve_invitation(
                db,
                invitation,
                status=InvitationStatus.REVOKED,
                membership_status=MembershipStatus.REVOKED,
                actor_id=actor.actor_id,
                at=at,
                event="permission.invitation_revoked",
            )

    def join_room(
        self,
        actor: ChatActor,
        room_id: str,
        *,
        invitation_id: str | None = None,
    ) -> RoomMembership:
        _text_id(room_id, "room_id")
        if invitation_id is not None:
            invitation = self.invitation(actor, invitation_id)
            if invitation.room_id != room_id:
                raise ValueError("invitation belongs to another room")
            return self.accept_invitation(actor, invitation_id)
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if room.kind is RoomKind.GENERAL:
                if actor.kind is not ActorKind.CORE:
                    self._require_active(db, room_id, actor)
                    membership = self._membership(db, room_id, actor.actor_id)
                    assert membership is not None
                    return membership
                return self._activate_general_member(db, actor.actor_id, at)
            row = db.execute(
                """
                SELECT invite_id FROM chat_invitation
                WHERE room_id=? AND invitee_id=? AND status=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (room_id, actor.actor_id, InvitationStatus.PENDING.value),
            ).fetchone()
            if row is None:
                raise PermissionError("no pending invitation for this room")
            pending_invite_id = row["invite_id"]
        return self.accept_invitation(actor, pending_invite_id)

    def leave_room(self, actor: ChatActor, room_id: str) -> None:
        _text_id(room_id, "room_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if room.kind is RoomKind.GENERAL and actor.kind is ActorKind.OWNER:
                raise PermissionError("the Platform owner cannot leave #general")
            self._require_active(db, room_id, actor)
            epoch = self._bump_epoch(db, room_id)
            db.execute(
                """
                UPDATE chat_membership
                SET status=?, epoch=?, joined_at=NULL,
                    history_from_sequence=NULL, left_at=?, updated_at=?
                WHERE room_id=? AND core_id=?
                """,
                (
                    MembershipStatus.LEFT.value,
                    epoch,
                    _iso(at),
                    _iso(at),
                    room_id,
                    actor.actor_id,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="membership.left",
                room_id=room_id,
                at=at,
                target_id=actor.actor_id,
                epoch=epoch,
            )

    def remove_member(
        self,
        actor: ChatActor,
        room_id: str,
        target_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        self._remove_or_revoke(
            actor,
            room_id,
            target_id,
            status=MembershipStatus.REMOVED,
            event="membership.removed",
            reason=reason,
        )

    def revoke_membership(
        self,
        actor: ChatActor,
        room_id: str,
        target_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        self._remove_or_revoke(
            actor,
            room_id,
            target_id,
            status=MembershipStatus.REVOKED,
            event="membership.revoked",
            reason=reason,
        )

    def _remove_or_revoke(
        self,
        actor: ChatActor,
        room_id: str,
        target_id: str,
        *,
        status: MembershipStatus,
        event: str,
        reason: str | None,
    ) -> None:
        _text_id(room_id, "room_id")
        _text_id(target_id, "target_id")
        if target_id == self._owner_id:
            raise PermissionError("the Platform owner cannot be removed from chat")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            self._require_room_admin(db, room, actor)
            membership = self._membership(db, room_id, target_id)
            if membership is None:
                raise LookupError("target is not a member of this room")
            if membership.status in (
                MembershipStatus.REMOVED,
                MembershipStatus.REVOKED,
            ):
                return
            epoch = self._bump_epoch(db, room_id)
            db.execute(
                """
                UPDATE chat_membership
                SET status=?, epoch=?, joined_at=NULL,
                    history_from_sequence=NULL, removed_by=?, left_at=?,
                    updated_at=?
                WHERE room_id=? AND core_id=?
                """,
                (
                    status.value,
                    epoch,
                    actor.actor_id,
                    _iso(at),
                    _iso(at),
                    room_id,
                    target_id,
                ),
            )
            db.execute(
                """
                UPDATE chat_invitation
                SET status=?, resolved_at=?
                WHERE room_id=? AND invitee_id=? AND status=?
                """,
                (
                    InvitationStatus.REVOKED.value,
                    _iso(at),
                    room_id,
                    target_id,
                    InvitationStatus.PENDING.value,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type=event,
                room_id=room_id,
                at=at,
                target_id=target_id,
                epoch=epoch,
                reason=reason,
            )

    def block(
        self,
        actor: ChatActor,
        target_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        _text_id(target_id, "target_id")
        if target_id == actor.actor_id:
            raise ValueError("cannot block self")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if target_id != self._owner_id and self.core_identity(target_id) is None:
                raise PermissionError("block target is not enrolled")
            db.execute(
                """
                INSERT INTO chat_block(blocker_id, blocked_id, reason, created_at)
                VALUES (?,?,?,?)
                ON CONFLICT(blocker_id, blocked_id) DO UPDATE SET
                    reason=excluded.reason,
                    created_at=excluded.created_at
                """,
                (actor.actor_id, target_id, reason, _iso(at)),
            )
            # A block always ends pair-private delivery. A room owner or the
            # Platform owner additionally removes the blocked member from rooms
            # they control. Other group memberships keep the member but message
            # delivery/history is hidden bidirectionally by the block filter.
            direct_id = self._direct_room_id(actor.actor_id, target_id)
            owner_scope = 1 if actor.kind is ActorKind.OWNER else 0
            rooms = db.execute(
                """
                SELECT r.room_id FROM chat_room AS r
                JOIN chat_membership AS m ON m.room_id=r.room_id
                WHERE m.core_id=? AND m.status=?
                  AND (
                      r.room_id=?
                      OR r.owner_core_id=?
                      OR ?
                  )
                ORDER BY r.room_id
                """,
                (
                    target_id,
                    MembershipStatus.ACTIVE.value,
                    direct_id,
                    actor.actor_id,
                    owner_scope,
                ),
            ).fetchall()
            for room_row in rooms:
                blocked_room_id = room_row["room_id"]
                epoch = self._bump_epoch(db, blocked_room_id)
                db.execute(
                    """
                    UPDATE chat_membership
                    SET status=?, epoch=?, joined_at=NULL,
                        history_from_sequence=NULL, removed_by=?, left_at=?,
                        updated_at=?
                    WHERE room_id=? AND core_id=?
                    """,
                    (
                        MembershipStatus.BLOCKED.value,
                        epoch,
                        actor.actor_id,
                        _iso(at),
                        _iso(at),
                        blocked_room_id,
                        target_id,
                    ),
                )
                self._audit(
                    db,
                    actor_id=actor.actor_id,
                    event_type="permission.blocked",
                    room_id=blocked_room_id,
                    at=at,
                    target_id=target_id,
                    epoch=epoch,
                    reason=reason,
                )
            db.execute(
                """
                UPDATE chat_invitation
                SET status=?, resolved_at=?
                WHERE status=? AND (
                    (invited_by=? AND invitee_id=?)
                    OR (invited_by=? AND invitee_id=?)
                )
                """,
                (
                    InvitationStatus.REVOKED.value,
                    _iso(at),
                    InvitationStatus.PENDING.value,
                    actor.actor_id,
                    target_id,
                    target_id,
                    actor.actor_id,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="permission.blocked",
                room_id="global",
                at=at,
                target_id=target_id,
                reason=reason,
            )

    def unblock(self, actor: ChatActor, target_id: str) -> None:
        _text_id(target_id, "target_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            db.execute(
                "DELETE FROM chat_block WHERE blocker_id=? AND blocked_id=?",
                (actor.actor_id, target_id),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="permission.unblocked",
                room_id="global",
                at=at,
                target_id=target_id,
            )

    def blocked(self, actor: ChatActor) -> tuple[str, ...]:
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            rows = db.execute(
                "SELECT blocked_id FROM chat_block WHERE blocker_id=? ORDER BY blocked_id",
                (actor.actor_id,),
            ).fetchall()
            return tuple(row[0] for row in rows)

    def membership(self, actor: ChatActor, room_id: str, core_id: str) -> RoomMembership | None:
        _text_id(room_id, "room_id")
        _text_id(core_id, "core_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if actor.kind is not ActorKind.OWNER:
                self._require_active(db, room.room_id, actor)
            elif self._membership(db, room.room_id, actor.actor_id) is None:
                raise PermissionError("owner is not a member of this room")
            return self._membership(db, room.room_id, core_id)

    def memberships(self, actor: ChatActor, room_id: str) -> tuple[RoomMembership, ...]:
        _text_id(room_id, "room_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            self._require_active(db, room_id, actor)
            rows = db.execute(
                "SELECT * FROM chat_membership WHERE room_id=? ORDER BY core_id",
                (room_id,),
            ).fetchall()
            return tuple(_membership_from_row(row) for row in rows)

    def update_room(
        self,
        actor: ChatActor,
        room_id: str,
        *,
        name: str | None = None,
        topic: str | None = None,
    ) -> Room:
        _text_id(room_id, "room_id")
        if name is not None and (not name.strip() or len(name) > 200):
            raise ValueError("name must be nonempty and bounded")
        if topic is not None and len(topic) > 2000:
            raise ValueError("topic must be bounded text")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if room.kind is RoomKind.GENERAL and actor.kind is not ActorKind.OWNER:
                raise PermissionError("only the Platform owner may rename #general")
            self._require_room_admin(db, room, actor)
            db.execute(
                "UPDATE chat_room SET name=?, topic=? WHERE room_id=?",
                (
                    room.name if name is None else name.strip(),
                    room.topic if topic is None else topic,
                    room_id,
                ),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="room.updated",
                room_id=room_id,
                at=at,
                name=None if name is None else name.strip(),
                topic=topic,
            )
            return self._room(db, room_id)

    def set_retention(
        self,
        actor: ChatActor,
        room_id: str,
        retention_seconds: int | None,
    ) -> Room:
        _text_id(room_id, "room_id")
        if retention_seconds is not None:
            _positive_int(retention_seconds, "retention_seconds")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            self._require_room_admin(db, room, actor)
            db.execute(
                "UPDATE chat_room SET retention_seconds=? WHERE room_id=?",
                (retention_seconds, room_id),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="room.retention_updated",
                room_id=room_id,
                at=at,
                retention_seconds=retention_seconds,
            )
            return self._room(db, room_id)

    def set_history_policy(
        self,
        actor: ChatActor,
        room_id: str,
        policy: RoomHistoryPolicy,
    ) -> Room:
        _text_id(room_id, "room_id")
        if not isinstance(policy, RoomHistoryPolicy):
            raise TypeError("policy must be a RoomHistoryPolicy")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            if room.kind is RoomKind.GENERAL:
                if policy is not RoomHistoryPolicy.FULL_HISTORY:
                    raise PermissionError("#general must keep full shared history")
            self._require_room_admin(db, room, actor)
            db.execute(
                "UPDATE chat_room SET history_policy=? WHERE room_id=?",
                (policy.value, room_id),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="room.history_policy_updated",
                room_id=room_id,
                at=at,
                history_policy=policy.value,
            )
            return self._room(db, room_id)

    # ------------------------------------------------------------------
    # Message ordering, delivery and history
    # ------------------------------------------------------------------
    def _require_sendable(
        self, db: sqlite3.Connection, room: Room, actor_id: str
    ) -> None:
        members = self._active_members(db, room.room_id)
        if not members:
            raise PermissionError("room has no active members")
        if room.kind is RoomKind.DIRECT and len(members) != 2:
            raise PermissionError(
                "direct room requires both authorized members to be active"
            )
        if actor_id not in {member.core_id for member in members}:
            raise PermissionError("sender is not an active member")

    def _visible_floor(
        self, room: Room, membership: RoomMembership
    ) -> int:
        if membership.history_from_sequence is not None:
            return membership.history_from_sequence
        return room.sequence + 1

    def _member_platform(self, db: sqlite3.Connection, member_id: str) -> str:
        if member_id == self._owner_id:
            return self._platform_id
        row = db.execute(
            "SELECT platform_id FROM chat_core WHERE core_id=?", (member_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("active member has no registered Core identity")
        return row["platform_id"]

    def _enqueue_deliveries(
        self,
        db: sqlite3.Connection,
        *,
        message: ChatMessage,
        sender_platform_id: str,
        at: datetime,
    ) -> None:
        for member_id in message.audience.member_ids:
            if member_id == message.sender_core_id:
                continue
            platform = self._member_platform(db, member_id)
            status = "PENDING" if platform == sender_platform_id else "QUEUED_REMOTE"
            db.execute(
                """
                INSERT INTO chat_delivery(
                    message_id, recipient_id, status, queued_at,
                    delivered_at, acked_at
                ) VALUES (?,?,?,?,NULL,NULL)
                ON CONFLICT(message_id, recipient_id) DO NOTHING
                """,
                (message.message_id, member_id, status, _iso(at)),
            )
            if platform != sender_platform_id:
                db.execute(
                    """
                    INSERT INTO chat_outbox(
                        outbox_id, message_id, room_id, destination_core_id,
                        destination_platform_id, status, created_at, sent_at
                    ) VALUES (?,?,?,?,?,?,?,NULL)
                    """,
                    (
                        f"outbox:{uuid4()}",
                        message.message_id,
                        message.room_id,
                        member_id,
                        platform,
                        "QUEUED",
                        _iso(at),
                    ),
                )

    def _existing_message(
        self,
        db: sqlite3.Connection,
        *,
        message_id: str,
    ) -> ChatMessage | None:
        row = db.execute(
            "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
        ).fetchone()
        return None if row is None else _message_from_row(row)

    def _validate_reply(
        self,
        db: sqlite3.Connection,
        *,
        room: Room,
        actor_id: str,
        membership: RoomMembership,
        reply_to: str | None,
    ) -> None:
        if reply_to is None:
            return
        row = db.execute(
            "SELECT * FROM chat_message WHERE message_id=?", (reply_to,)
        ).fetchone()
        if row is None:
            raise ValueError("reply target does not exist")
        if row["room_id"] != room.room_id:
            raise ValueError("reply target belongs to another room")
        if row["sequence"] < self._visible_floor(room, membership):
            raise PermissionError("reply target is outside this member's visible history")
        if self._blocked_pair(db, actor_id, row["sender_id"]):
            raise PermissionError("reply target is blocked")

    def _insert_message(
        self,
        db: sqlite3.Connection,
        *,
        room: Room,
        message_id: str,
        sender_id: str,
        sender_kind: ActorKind,
        body: str,
        created_at: datetime,
        stored_at: datetime,
        reply_to: str | None,
        origin: MessageOrigin,
        audience: ChatAudience,
        provenance: MessageProvenance,
        idempotency_key: str | None,
    ) -> ChatMessage:
        sequence = room.sequence + 1
        updated = db.execute(
            "UPDATE chat_room SET sequence=? WHERE room_id=? AND sequence=?",
            (sequence, room.room_id, room.sequence),
        )
        if updated.rowcount != 1:
            raise RuntimeError("room sequence changed during message write")
        db.execute(
            """
            INSERT INTO chat_message(
                message_id, room_id, sender_id, sender_kind, body,
                created_at, stored_at, reply_to, origin, sequence,
                audience_json, provenance_json, idempotency_key,
                origin_platform_id, source_generation, edited_at,
                deleted_at, deleted_by, revision
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,0)
            """,
            (
                message_id,
                room.room_id,
                sender_id,
                sender_kind.value,
                body,
                _iso(created_at),
                _iso(stored_at),
                reply_to,
                origin.value,
                sequence,
                _audience_payload(audience),
                _provenance_payload(provenance),
                idempotency_key,
                provenance.source_platform_id,
                provenance.source_generation,
            ),
        )
        row = db.execute(
            "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
        ).fetchone()
        message = _message_from_row(row)
        self._enqueue_deliveries(
            db,
            message=message,
            sender_platform_id=provenance.source_platform_id,
            at=stored_at,
        )
        return message

    def send(
        self,
        actor: ChatActor,
        room_id: str,
        body: str,
        *,
        reply_to: str | None = None,
        created_at: datetime | None = None,
        idempotency_key: str | None = None,
        message_id: str | None = None,
    ) -> ChatMessage:
        _text_id(room_id, "room_id")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("message body must be nonempty text")
        if len(body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("message body exceeds the bounded maximum")
        if reply_to is not None:
            _text_id(reply_to, "reply_to")
        if idempotency_key is not None:
            _text_id(idempotency_key, "idempotency_key")
        if message_id is not None:
            _text_id(message_id, "message_id")
        at = self._now()
        created = at if created_at is None else _aware(created_at, "created_at")
        effective_id = str(uuid4()) if message_id is None else message_id
        if actor.kind is ActorKind.CORE and self._is_stopped():
            raise PermissionError("operator STOP suspends Core chat outreach")
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            membership = self._require_active(db, room_id, actor)
            if idempotency_key is not None:
                row = db.execute(
                    """
                    SELECT * FROM chat_message
                    WHERE room_id=? AND sender_id=? AND idempotency_key=?
                    """,
                    (room_id, actor.actor_id, idempotency_key),
                ).fetchone()
                if row is not None:
                    existing = _message_from_row(row)
                    if existing.body != body:
                        raise ValueError(
                            "idempotency key reused with different message content"
                        )
                    return existing
            existing = self._existing_message(db, message_id=effective_id)
            if existing is not None:
                if (
                    existing.room_id != room_id
                    or existing.sender_core_id != actor.actor_id
                    or existing.body != body
                ):
                    raise ValueError("message ID already used for different content")
                return existing
            self._require_sendable(db, room, actor.actor_id)
            self._validate_reply(
                db,
                room=room,
                actor_id=actor.actor_id,
                membership=membership,
                reply_to=reply_to,
            )
            audience = self._audience(db, room)
            origin = (
                MessageOrigin.OWNER
                if actor.kind is ActorKind.OWNER
                else MessageOrigin.LOCAL_CORE
            )
            provenance = MessageProvenance(
                source_platform_id=(
                    self._platform_id
                    if actor.kind is ActorKind.OWNER
                    else actor.identity.platform_id
                ),
                source_generation=(
                    None
                    if actor.kind is ActorKind.OWNER
                    else actor.identity.generation
                ),
                transport_verified=True,
                untrusted_content=False,
                received_at=at,
                idempotency_key=idempotency_key,
            )
            return self._insert_message(
                db,
                room=room,
                message_id=effective_id,
                sender_id=actor.actor_id,
                sender_kind=actor.kind,
                body=body,
                created_at=created,
                stored_at=at,
                reply_to=reply_to,
                origin=origin,
                audience=audience,
                provenance=provenance,
                idempotency_key=idempotency_key,
            )

    def receive_peer_message(
        self,
        peer: CoreIdentity,
        envelope: PeerEnvelope,
        *,
        received_at: datetime | None = None,
    ) -> ChatMessage:
        if not isinstance(envelope, PeerEnvelope):
            raise TypeError("envelope must be a PeerEnvelope")
        if not isinstance(peer, CoreIdentity):
            raise TypeError("peer must be a CoreIdentity")
        if envelope.source_core_id != peer.core_id_text:
            raise PermissionError("peer envelope sender does not match authenticated peer")
        if envelope.source_platform_id != peer.platform_id:
            raise PermissionError("peer envelope platform does not match authenticated peer")
        if envelope.source_generation != peer.generation:
            raise PermissionError("peer envelope generation does not match authenticated peer")
        if self._is_stopped():
            raise PermissionError("operator STOP suspends peer chat delivery")
        at = self._now()
        received = at if received_at is None else _aware(received_at, "received_at")
        with self._store.transaction() as db:
            self._authorize_peer(db, peer)
            room = self._room(db, envelope.room_id)
            membership = self._require_active(db, room.room_id, ChatActor.core(peer))
            existing = self._existing_message(db, message_id=envelope.message_id)
            if existing is not None:
                if (
                    existing.room_id != envelope.room_id
                    or existing.sender_core_id != peer.core_id_text
                    or existing.body != envelope.body
                ):
                    raise ValueError("peer message ID already used for different content")
                return existing
            if envelope.idempotency_key is not None:
                row = db.execute(
                    """
                    SELECT * FROM chat_message
                    WHERE room_id=? AND sender_id=? AND idempotency_key=?
                    """,
                    (room.room_id, peer.core_id_text, envelope.idempotency_key),
                ).fetchone()
                if row is not None:
                    found = _message_from_row(row)
                    if found.body != envelope.body:
                        raise ValueError(
                            "peer idempotency key reused with different content"
                        )
                    return found
            self._require_sendable(db, room, peer.core_id_text)
            self._validate_reply(
                db,
                room=room,
                actor_id=peer.core_id_text,
                membership=membership,
                reply_to=envelope.reply_to,
            )
            audience = self._audience(db, room)
            provenance = MessageProvenance(
                source_platform_id=peer.platform_id,
                source_generation=peer.generation,
                transport_verified=True,
                untrusted_content=True,
                received_at=received,
                idempotency_key=envelope.idempotency_key,
            )
            return self._insert_message(
                db,
                room=room,
                message_id=envelope.message_id,
                sender_id=peer.core_id_text,
                sender_kind=ActorKind.CORE,
                body=envelope.body,
                created_at=envelope.created_at,
                stored_at=received,
                reply_to=envelope.reply_to,
                origin=MessageOrigin.PEER_CORE,
                audience=audience,
                provenance=provenance,
                idempotency_key=envelope.idempotency_key,
            )

    def receive_peer_payload(
        self,
        peer: CoreIdentity,
        payload: Mapping[str, object],
        *,
        received_at: datetime | None = None,
    ) -> ChatMessage:
        return self.receive_peer_message(
            peer,
            PeerEnvelope.from_payload(payload),
            received_at=received_at,
        )

    def _history_connection(
        self,
        db: sqlite3.Connection,
        actor: ChatActor,
        room_id: str,
        *,
        after_sequence: int | None,
        before_sequence: int | None,
        limit: int,
    ) -> MessagePage:
        self._authorize_actor(db, actor)
        room = self._room(db, room_id)
        membership = self._require_active(db, room_id, actor)
        floor = self._visible_floor(room, membership)
        if after_sequence is not None and type(after_sequence) is not int:
            raise TypeError("after_sequence must be an integer or None")
        if before_sequence is not None and type(before_sequence) is not int:
            raise TypeError("before_sequence must be an integer or None")
        _positive_int(limit, "limit")
        if limit > 200:
            raise ValueError("limit must be <= 200")
        after = max(after_sequence or 0, floor - 1)
        before = before_sequence
        if before is not None and before <= after:
            return MessagePage(
                room_id=room_id,
                messages=(),
                next_cursor=None,
                has_more=False,
                membership_epoch=room.membership_epoch,
                history_from_sequence=floor,
            )
        parameters: list[object] = [
            room_id,
            floor,
            after,
            actor.actor_id,
            actor.actor_id,
        ]
        sql = """
            SELECT m.* FROM chat_message AS m
            WHERE m.room_id=? AND m.sequence>=? AND m.sequence>?
              AND NOT EXISTS (
                  SELECT 1 FROM chat_block AS b
                  WHERE (b.blocker_id=? AND b.blocked_id=m.sender_id)
                     OR (b.blocker_id=m.sender_id AND b.blocked_id=?)
              )
        """
        if before is not None:
            sql += " AND m.sequence<?"
            parameters.append(before)
        sql += " ORDER BY m.sequence ASC LIMIT ?"
        parameters.append(limit + 1)
        rows = db.execute(sql, parameters).fetchall()
        has_more = len(rows) > limit
        kept = rows[:limit]
        messages = tuple(_message_from_row(row) for row in kept)
        next_cursor = messages[-1].sequence if has_more else None
        return MessagePage(
            room_id=room_id,
            messages=messages,
            next_cursor=next_cursor,
            has_more=has_more,
            membership_epoch=room.membership_epoch,
            history_from_sequence=floor,
        )

    def history(
        self,
        actor: ChatActor,
        room_id: str,
        *,
        after_sequence: int | None = None,
        before_sequence: int | None = None,
        limit: int = 50,
    ) -> MessagePage:
        _text_id(room_id, "room_id")
        with self._store.reader() as db:
            return self._history_connection(
                db,
                actor,
                room_id,
                after_sequence=after_sequence,
                before_sequence=before_sequence,
                limit=limit,
            )

    def message(self, actor: ChatActor, message_id: str) -> ChatMessage:
        _text_id(message_id, "message_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            row = db.execute(
                "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise LookupError("message does not exist")
            room = self._room(db, row["room_id"])
            membership = self._require_active(db, room.room_id, actor)
            if row["sequence"] < self._visible_floor(room, membership):
                raise PermissionError("message predates this member's history floor")
            if self._blocked_pair(db, actor.actor_id, row["sender_id"]):
                raise PermissionError("message sender is blocked")
            return _message_from_row(row)

    def sync(
        self,
        actor: ChatActor,
        *,
        limit: int = 100,
    ) -> SyncResult:
        _positive_int(limit, "limit")
        if limit > 500:
            raise ValueError("limit must be <= 500")
        at = self._now()
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            room_rows = db.execute(
                """
                SELECT room_id FROM chat_membership
                WHERE core_id=? AND status=?
                ORDER BY room_id
                """,
                (actor.actor_id, MembershipStatus.ACTIVE.value),
            ).fetchall()
            room_ids = [row["room_id"] for row in room_rows]
        pages: list[RoomSync] = []
        for room_id in room_ids:
            with self._store.transaction() as db:
                self._authorize_actor(db, actor)
                cursor_row = db.execute(
                    "SELECT last_read_sequence FROM chat_cursor WHERE actor_id=? AND room_id=?",
                    (actor.actor_id, room_id),
                ).fetchone()
                cursor = 0 if cursor_row is None else cursor_row[0]
                page = self._history_connection(
                    db,
                    actor,
                    room_id,
                    after_sequence=cursor,
                    before_sequence=None,
                    limit=limit,
                )
                if page.messages:
                    message_ids = [message.message_id for message in page.messages]
                    placeholders = ",".join("?" for _ in message_ids)
                    db.execute(
                        f"""
                        UPDATE chat_delivery
                        SET status='ACKED', delivered_at=COALESCE(delivered_at, ?),
                            acked_at=?
                        WHERE recipient_id=? AND message_id IN ({placeholders})
                        """,
                        (
                            _iso(at),
                            _iso(at),
                            actor.actor_id,
                            *message_ids,
                        ),
                    )
                    db.execute(
                        f"""
                        UPDATE chat_outbox
                        SET status='DELIVERED', sent_at=?
                        WHERE destination_core_id=? AND status='QUEUED'
                          AND message_id IN ({placeholders})
                        """,
                        (_iso(at), actor.actor_id, *message_ids),
                    )
                    cursor = page.messages[-1].sequence
                    db.execute(
                        """
                        INSERT INTO chat_cursor(actor_id, room_id, last_read_sequence, updated_at)
                        VALUES (?,?,?,?)
                        ON CONFLICT(actor_id, room_id) DO UPDATE SET
                            last_read_sequence=excluded.last_read_sequence,
                            updated_at=excluded.updated_at
                        """,
                        (actor.actor_id, room_id, cursor, _iso(at)),
                    )
                pages.append(
                    RoomSync(
                        room_id=room_id,
                        messages=page.messages,
                        next_cursor=cursor,
                        has_more=page.has_more,
                    )
                )
        return SyncResult(actor_id=actor.actor_id, rooms=tuple(pages))

    def inbox(
        self,
        actor: ChatActor,
        *,
        room_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ChatMessage, ...]:
        if room_id is not None:
            _text_id(room_id, "room_id")
        _positive_int(limit, "limit")
        if limit > 500:
            raise ValueError("limit must be <= 500")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            parameters: list[object] = [actor.actor_id, actor.actor_id]
            sql = """
                SELECT m.* FROM chat_delivery AS d
                JOIN chat_message AS m ON m.message_id=d.message_id
                JOIN chat_membership AS mem
                  ON mem.room_id=m.room_id AND mem.core_id=d.recipient_id
                WHERE d.recipient_id=?
                  AND d.status IN ('PENDING','QUEUED_REMOTE')
                  AND mem.status='active'
                  AND m.sequence>=mem.history_from_sequence
                  AND NOT EXISTS (
                      SELECT 1 FROM chat_block AS b
                      WHERE (b.blocker_id=? AND b.blocked_id=m.sender_id)
                         OR (b.blocker_id=m.sender_id AND b.blocked_id=?)
                  )
            """
            parameters.append(actor.actor_id)
            if room_id is not None:
                sql += " AND m.room_id=?"
                parameters.append(room_id)
            sql += " ORDER BY m.room_id, m.sequence LIMIT ?"
            parameters.append(limit)
            rows = db.execute(sql, parameters).fetchall()
            return tuple(_message_from_row(row) for row in rows)

    def edit_message(
        self,
        actor: ChatActor,
        message_id: str,
        body: str,
    ) -> ChatMessage:
        _text_id(message_id, "message_id")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("message body must be nonempty text")
        if len(body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("message body exceeds the bounded maximum")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            row = db.execute(
                "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise LookupError("message does not exist")
            room = self._room(db, row["room_id"])
            self._require_active(db, room.room_id, actor)
            if row["sender_id"] != actor.actor_id:
                raise PermissionError("only the sender may edit a message")
            if row["deleted_at"] is not None:
                raise PermissionError("a tombstoned message cannot be edited")
            db.execute(
                """
                UPDATE chat_message
                SET body=?, edited_at=?, revision=revision+1
                WHERE message_id=?
                """,
                (body, _iso(at), message_id),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="message.edited",
                room_id=room.room_id,
                at=at,
                message_id=message_id,
            )
            return _message_from_row(
                db.execute(
                    "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
                ).fetchone()
            )

    def delete_message(
        self,
        actor: ChatActor,
        message_id: str,
        *,
        reason: str | None = None,
    ) -> ChatMessage:
        _text_id(message_id, "message_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            row = db.execute(
                "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise LookupError("message does not exist")
            room = self._room(db, row["room_id"])
            self._require_active(db, room.room_id, actor)
            permitted = (
                row["sender_id"] == actor.actor_id
                or actor.kind is ActorKind.OWNER
                or room.owner_core_id == actor.actor_id
            )
            if not permitted:
                raise PermissionError("actor may not tombstone this message")
            if row["deleted_at"] is not None:
                return _message_from_row(row)
            db.execute(
                """
                UPDATE chat_message
                SET body='', deleted_at=?, deleted_by=?, revision=revision+1
                WHERE message_id=?
                """,
                (_iso(at), actor.actor_id, message_id),
            )
            self._audit(
                db,
                actor_id=actor.actor_id,
                event_type="message.tombstoned",
                room_id=room.room_id,
                at=at,
                message_id=message_id,
                reason=reason,
            )
            return _message_from_row(
                db.execute(
                    "SELECT * FROM chat_message WHERE message_id=?", (message_id,)
                ).fetchone()
            )

    # ------------------------------------------------------------------
    # Per-room cursors and drafts
    # ------------------------------------------------------------------
    def set_cursor(
        self, actor: ChatActor, room_id: str, sequence: int
    ) -> int:
        _text_id(room_id, "room_id")
        _positive_int(sequence, "sequence", minimum=0)
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            membership = self._require_active(db, room_id, actor)
            floor = self._visible_floor(room, membership)
            if sequence > room.sequence:
                raise ValueError("cursor cannot exceed the room sequence")
            if sequence < floor - 1:
                sequence = floor - 1
            db.execute(
                """
                INSERT INTO chat_cursor(actor_id, room_id, last_read_sequence, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(actor_id, room_id) DO UPDATE SET
                    last_read_sequence=excluded.last_read_sequence,
                    updated_at=excluded.updated_at
                """,
                (actor.actor_id, room_id, sequence, _iso(at)),
            )
            return sequence

    def cursor(self, actor: ChatActor, room_id: str) -> int:
        _text_id(room_id, "room_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            self._room(db, room_id)
            self._require_active(db, room_id, actor)
            row = db.execute(
                "SELECT last_read_sequence FROM chat_cursor WHERE actor_id=? AND room_id=?",
                (actor.actor_id, room_id),
            ).fetchone()
            return 0 if row is None else row[0]

    def save_draft(
        self,
        actor: ChatActor,
        room_id: str,
        body: str,
        *,
        reply_to: str | None = None,
    ) -> Draft | None:
        _text_id(room_id, "room_id")
        if not isinstance(body, str):
            raise TypeError("body must be text")
        if len(body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("draft body exceeds the bounded maximum")
        if reply_to is not None:
            _text_id(reply_to, "reply_to")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            room = self._room(db, room_id)
            membership = self._require_active(db, room_id, actor)
            if not body.strip():
                db.execute(
                    "DELETE FROM chat_draft WHERE actor_id=? AND room_id=?",
                    (actor.actor_id, room_id),
                )
                return None
            self._validate_reply(
                db,
                room=room,
                actor_id=actor.actor_id,
                membership=membership,
                reply_to=reply_to,
            )
            db.execute(
                """
                INSERT INTO chat_draft(actor_id, room_id, body, reply_to, updated_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(actor_id, room_id) DO UPDATE SET
                    body=excluded.body,
                    reply_to=excluded.reply_to,
                    updated_at=excluded.updated_at
                """,
                (actor.actor_id, room_id, body, reply_to, _iso(at)),
            )
            return Draft(
                actor_id=actor.actor_id,
                room_id=room_id,
                body=body,
                reply_to=reply_to,
                updated_at=at,
            )

    def clear_draft(self, actor: ChatActor, room_id: str) -> None:
        self.save_draft(actor, room_id, "")

    def draft(self, actor: ChatActor, room_id: str) -> Draft | None:
        _text_id(room_id, "room_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            self._room(db, room_id)
            self._require_active(db, room_id, actor)
            row = db.execute(
                "SELECT * FROM chat_draft WHERE actor_id=? AND room_id=?",
                (actor.actor_id, room_id),
            ).fetchone()
        if row is None:
            return None
        return Draft(
            actor_id=row["actor_id"],
            room_id=row["room_id"],
            body=row["body"],
            reply_to=row["reply_to"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # Durable outbox and audit
    # ------------------------------------------------------------------
    def outbox(
        self,
        actor: ChatActor,
        *,
        destination_core_id: str | None = None,
    ) -> tuple[OutboxEntry, ...]:
        if destination_core_id is not None:
            _text_id(destination_core_id, "destination_core_id")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            if actor.kind is ActorKind.CORE:
                if destination_core_id not in (None, actor.actor_id):
                    raise PermissionError("Core may only inspect its own outbox")
                destination_core_id = actor.actor_id
            parameters: list[object] = []
            sql = "SELECT * FROM chat_outbox"
            if destination_core_id is not None:
                sql += " WHERE destination_core_id=?"
                parameters.append(destination_core_id)
            sql += " ORDER BY created_at, outbox_id"
            rows = db.execute(sql, parameters).fetchall()
            return tuple(
                OutboxEntry(
                    outbox_id=row["outbox_id"],
                    message_id=row["message_id"],
                    room_id=row["room_id"],
                    destination_core_id=row["destination_core_id"],
                    destination_platform_id=row["destination_platform_id"],
                    status=row["status"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            )

    def mark_outbox_sent(self, actor: ChatActor, outbox_id: str) -> None:
        _text_id(outbox_id, "outbox_id")
        at = self._now()
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if actor.kind is not ActorKind.OWNER:
                raise PermissionError("only the Platform owner may mark transport progress")
            changed = db.execute(
                """
                UPDATE chat_outbox SET status='SENT', sent_at=?
                WHERE outbox_id=? AND status='QUEUED'
                """,
                (_iso(at), outbox_id),
            )
            if changed.rowcount != 1:
                raise LookupError("queued outbox entry does not exist")

    def audit_events(
        self,
        actor: ChatActor,
        *,
        room_id: str | None = None,
        since_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[ChatAuditEvent, ...]:
        if room_id is not None:
            _text_id(room_id, "room_id")
        _positive_int(since_sequence, "since_sequence", minimum=0)
        _positive_int(limit, "limit")
        if limit > 500:
            raise ValueError("limit must be <= 500")
        with self._store.reader() as db:
            self._authorize_actor(db, actor)
            if actor.kind is ActorKind.CORE:
                if room_id is None:
                    raise PermissionError("Core audit access requires an explicit room")
                self._require_active(db, room_id, actor)
            rows = db.execute(
                """
                SELECT * FROM safe_audit_event
                WHERE sequence>? AND event_type LIKE 'chat.%'
                ORDER BY sequence ASC
                """,
                (since_sequence,),
            ).fetchall()
        events: list[ChatAuditEvent] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if room_id is not None and payload.get("room_id") != room_id:
                continue
            events.append(
                ChatAuditEvent(
                    sequence=row["sequence"],
                    event_id=row["event_id"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    actor_id=row["actor_id"],
                    event_type=row["event_type"],
                    payload=payload,
                )
            )
            if len(events) >= limit:
                break
        return tuple(events)

    def verify_audit(self) -> tuple[bool, str | None]:
        return self._store.audit.verify()

    # ------------------------------------------------------------------
    # Retention and expiry
    # ------------------------------------------------------------------
    def apply_retention(
        self,
        actor: ChatActor,
        *,
        now: datetime | None = None,
    ) -> RetentionResult:
        at = self._now() if now is None else _aware(now, "now")
        deleted_messages = 0
        expired_invitations = 0
        with self._store.transaction() as db:
            self._authorize_actor(db, actor)
            if actor.kind is not ActorKind.OWNER:
                raise PermissionError("only the Platform owner may run retention")
            pending = db.execute(
                """
                SELECT * FROM chat_invitation
                WHERE status=? AND expires_at IS NOT NULL AND expires_at<?
                ORDER BY created_at
                """,
                (InvitationStatus.PENDING.value, _iso(at)),
            ).fetchall()
            for row in pending:
                invitation = _invitation_from_row(row)
                room = self._room(db, invitation.room_id)
                epoch = self._bump_epoch(db, room.room_id)
                db.execute(
                    "UPDATE chat_invitation SET status=?, resolved_at=? WHERE invite_id=?",
                    (
                        InvitationStatus.EXPIRED.value,
                        _iso(at),
                        invitation.invite_id,
                    ),
                )
                db.execute(
                    """
                    UPDATE chat_membership
                    SET status=?, epoch=?, joined_at=NULL,
                        history_from_sequence=NULL, removed_by=?, left_at=?,
                        updated_at=?
                    WHERE room_id=? AND core_id=? AND status=?
                    """,
                    (
                        MembershipStatus.EXPIRED.value,
                        epoch,
                        "system:expiry",
                        _iso(at),
                        _iso(at),
                        room.room_id,
                        invitation.invitee_id,
                        MembershipStatus.INVITED.value,
                    ),
                )
                self._audit(
                    db,
                    actor_id="system:expiry",
                    event_type="membership.expired",
                    room_id=room.room_id,
                    at=at,
                    target_id=invitation.invitee_id,
                    invite_id=invitation.invite_id,
                    epoch=epoch,
                )
                expired_invitations += 1
            rooms = db.execute(
                "SELECT * FROM chat_room WHERE retention_seconds IS NOT NULL"
            ).fetchall()
            for room_row in rooms:
                room = _room_from_row(room_row)
                cutoff = at - timedelta(seconds=room.retention_seconds or 0)
                stale = db.execute(
                    """
                    SELECT message_id FROM chat_message
                    WHERE room_id=? AND stored_at<?
                    """,
                    (room.room_id, _iso(cutoff)),
                ).fetchall()
                if not stale:
                    continue
                ids = [row["message_id"] for row in stale]
                placeholders = ",".join("?" for _ in ids)
                db.execute(
                    f"DELETE FROM chat_delivery WHERE message_id IN ({placeholders})",
                    ids,
                )
                db.execute(
                    f"DELETE FROM chat_outbox WHERE message_id IN ({placeholders})",
                    ids,
                )
                db.execute(
                    f"DELETE FROM chat_message WHERE message_id IN ({placeholders})",
                    ids,
                )
                self._audit(
                    db,
                    actor_id=actor.actor_id,
                    event_type="retention.cleanup",
                    room_id=room.room_id,
                    at=at,
                    deleted_messages=len(ids),
                    cutoff=_iso(cutoff),
                )
                deleted_messages += len(ids)
        return RetentionResult(
            deleted_messages=deleted_messages,
            expired_invitations=expired_invitations,
        )


__all__ = ["ChatEngine"]
