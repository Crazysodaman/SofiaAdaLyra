"""Durable local federation state: peers, rooms, outbox, inbox and STOP.

This store is deliberately local.  It records only observed/authorized state
for one Platform instance; it is not a shared social database and it never
imports another Core's memory.  Every consequential method enforces the
exact identity, generation, peer state, room epoch and recipient scope it was
given.  SQLite durability is used for at-least-once delivery reconciliation.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import UUID, uuid4

from sofia.platform.federation.errors import (
    FederationConflict,
    FederationIdentityError,
    FederationPeerError,
    FederationReplay,
    FederationRoomError,
)
from sofia.platform.federation.models import (
    ContactDirection,
    DeliveryStatus,
    InboxRecord,
    OutboxRecord,
    PeerRecord,
    PeerState,
)
from sofia.platform.social.contracts import (
    CoreIdentity,
    MembershipStatus,
    RoomId,
    RoomKind,
    RoomMembership,
    canonical_json,
)
from sofia.platform.federation.envelope import PeerEnvelope


_DIGEST_LEN = 64
_TERMINAL_OUTBOX = frozenset({
    DeliveryStatus.ACCEPTED,
    DeliveryStatus.DECLINED,
    DeliveryStatus.DENIED,
    DeliveryStatus.EXPIRED,
    DeliveryStatus.HANDLED,
})
_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.QUEUED: frozenset({
        DeliveryStatus.SENT_UNCONFIRMED,
        DeliveryStatus.RECEIVED,
        DeliveryStatus.DENIED,
        DeliveryStatus.EXPIRED,
        DeliveryStatus.OUTCOME_UNKNOWN,
    }),
    DeliveryStatus.SENT_UNCONFIRMED: frozenset({
        DeliveryStatus.RECEIVED,
        DeliveryStatus.ACCEPTED,
        DeliveryStatus.DECLINED,
        DeliveryStatus.DENIED,
        DeliveryStatus.EXPIRED,
        DeliveryStatus.HANDLED,
        DeliveryStatus.OUTCOME_UNKNOWN,
    }),
    DeliveryStatus.RECEIVED: frozenset({
        DeliveryStatus.ACCEPTED,
        DeliveryStatus.DECLINED,
        DeliveryStatus.DENIED,
        DeliveryStatus.HANDLED,
        DeliveryStatus.EXPIRED,
        DeliveryStatus.OUTCOME_UNKNOWN,
    }),
    DeliveryStatus.OUTCOME_UNKNOWN: frozenset({
        DeliveryStatus.RECEIVED,
        DeliveryStatus.ACCEPTED,
        DeliveryStatus.DECLINED,
        DeliveryStatus.DENIED,
        DeliveryStatus.HANDLED,
        DeliveryStatus.EXPIRED,
    }),
}


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("stored timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _trust_anchor(value: object) -> str:
    if not isinstance(value, str) or len(value) != _DIGEST_LEN:
        raise ValueError("trust anchor must be an exact lowercase SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("trust anchor must be hexadecimal") from exc
    if value.lower() != value:
        raise ValueError("trust anchor must be lowercase")
    return value


class FederationState:
    """One Platform's durable federation store."""

    def __init__(self, state_path: Path | str) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("an on-disk SQLite state path is required")
        if str(state_path) == ":memory:":
            raise ValueError("in-memory state cannot provide durable federation evidence")
        target = Path(state_path).resolve()
        if not target.parent.is_dir():
            raise FileNotFoundError("federation state parent directory must exist")
        self.path = target
        self._db = sqlite3.connect(str(target), timeout=5.0, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout = 5000")
        self._db.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "FederationState":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        else:
            self._db.execute("COMMIT")

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS local_identity (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                core_id TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                generation INTEGER NOT NULL CHECK (generation >= 1),
                display_name TEXT NOT NULL,
                trust_anchor TEXT NOT NULL,
                lease_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS writer_binding (
                core_id TEXT PRIMARY KEY,
                platform_id TEXT NOT NULL,
                generation INTEGER NOT NULL CHECK (generation >= 1),
                lease_id TEXT NOT NULL,
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS peer (
                peer_id TEXT PRIMARY KEY,
                invitation_id TEXT NOT NULL,
                remote_platform_id TEXT NOT NULL,
                remote_core_id TEXT NOT NULL,
                remote_generation INTEGER NOT NULL CHECK (remote_generation >= 1),
                display_name TEXT NOT NULL,
                trust_anchor TEXT NOT NULL,
                state TEXT NOT NULL,
                outbound_allowed INTEGER NOT NULL CHECK (outbound_allowed IN (0, 1)),
                inbound_allowed INTEGER NOT NULL CHECK (inbound_allowed IN (0, 1)),
                revision INTEGER NOT NULL CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                UNIQUE (remote_platform_id, remote_core_id)
            );
            CREATE TABLE IF NOT EXISTS room (
                room_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS membership (
                room_id TEXT NOT NULL,
                core_id TEXT NOT NULL,
                epoch INTEGER NOT NULL CHECK (epoch >= 1),
                status TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                history_from_sequence INTEGER NOT NULL CHECK (history_from_sequence >= 0),
                PRIMARY KEY (room_id, core_id),
                FOREIGN KEY (room_id) REFERENCES room(room_id)
            );
            CREATE TABLE IF NOT EXISTS outgoing_sequence (
                room_id TEXT NOT NULL,
                core_id TEXT NOT NULL,
                next_sequence INTEGER NOT NULL CHECK (next_sequence >= 1),
                PRIMARY KEY (room_id, core_id)
            );
            CREATE TABLE IF NOT EXISTS incoming_sequence (
                room_id TEXT NOT NULL,
                source_core_id TEXT NOT NULL,
                last_sequence INTEGER NOT NULL CHECK (last_sequence >= 1),
                PRIMARY KEY (room_id, source_core_id)
            );
            CREATE TABLE IF NOT EXISTS outbox (
                message_id TEXT PRIMARY KEY,
                destination_platform_id TEXT NOT NULL,
                destination_core_id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                idempotency_key TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                UNIQUE (destination_platform_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS inbox (
                message_id TEXT PRIMARY KEY,
                source_platform_id TEXT NOT NULL,
                source_core_id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                status TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                detail TEXT,
                received_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                UNIQUE (source_platform_id, source_core_id, message_id)
            );
            CREATE TABLE IF NOT EXISTS security_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                stopped INTEGER NOT NULL CHECK (stopped IN (0, 1)),
                updated_at TEXT NOT NULL
            );
            """
        )

    # ------------------------------------------------------------------
    # Local identity and writer isolation
    # ------------------------------------------------------------------
    def set_local_identity(
        self, identity: CoreIdentity, *, trust_anchor: str, lease_id: str = "local-writer",
    ) -> None:
        if not isinstance(identity, CoreIdentity):
            raise TypeError("identity must be CoreIdentity")
        anchor = _trust_anchor(trust_anchor)
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        with self._transaction():
            row = self._db.execute("SELECT * FROM local_identity WHERE singleton = 1").fetchone()
            if row is not None:
                if (
                    row["core_id"] != str(identity.core_id)
                    or row["platform_id"] != identity.platform_id
                ):
                    raise FederationIdentityError(
                        "local Core identity is already bound to another exact Platform"
                    )
                if row["trust_anchor"] != anchor:
                    raise FederationConflict("local trust anchor is already pinned")
                if row["generation"] != identity.generation:
                    raise FederationIdentityError(
                        "local writer generation must advance explicitly"
                    )
                return
            now = datetime.now(timezone.utc)
            self._db.execute(
                """INSERT INTO local_identity
                   (singleton, core_id, platform_id, generation, display_name,
                    trust_anchor, lease_id, updated_at)
                   VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(identity.core_id), identity.platform_id, identity.generation,
                    identity.display_name, anchor, lease_id, _iso(now),
                ),
            )
            self._claim_writer_row(
                identity.core_id, identity.platform_id, identity.generation, lease_id, now,
            )

    def _claim_writer_row(
        self, core_id: UUID, platform_id: str, generation: int, lease_id: str, now: datetime,
    ) -> None:
        row = self._db.execute(
            "SELECT * FROM writer_binding WHERE core_id = ?", (str(core_id),),
        ).fetchone()
        if row is None:
            self._db.execute(
                """INSERT INTO writer_binding
                   (core_id, platform_id, generation, lease_id, active, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (str(core_id), platform_id, generation, lease_id, _iso(now)),
            )
            return
        if row["platform_id"] != platform_id:
            raise FederationIdentityError("writer lineage is fenced to another Platform")
        if generation < row["generation"]:
            raise FederationIdentityError("stale writer generation refused")
        if generation == row["generation"] and row["lease_id"] != lease_id:
            raise FederationIdentityError("another writer lease holds this generation")
        if generation > row["generation"]:
            self._db.execute(
                """UPDATE writer_binding
                   SET generation = ?, lease_id = ?, active = 1, updated_at = ?
                   WHERE core_id = ?""",
                (generation, lease_id, _iso(now), str(core_id)),
            )

    def local_identity(self) -> tuple[CoreIdentity, str]:
        row = self._db.execute("SELECT * FROM local_identity WHERE singleton = 1").fetchone()
        if row is None:
            raise FederationIdentityError("no local Core identity is active")
        identity = CoreIdentity(
            core_id=UUID(row["core_id"]),
            platform_id=row["platform_id"],
            generation=row["generation"],
            display_name=row["display_name"],
        )
        return identity, row["trust_anchor"]

    def writer_generation(self) -> int:
        return self.local_identity()[0].generation

    def advance_local_generation(self, generation: int) -> CoreIdentity:
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be a positive integer")
        with self._transaction():
            row = self._db.execute("SELECT * FROM local_identity WHERE singleton = 1").fetchone()
            if row is None:
                raise FederationIdentityError("no local Core identity is active")
            if generation <= row["generation"]:
                raise FederationIdentityError("writer generation must strictly advance")
            now = datetime.now(timezone.utc)
            self._db.execute(
                "UPDATE local_identity SET generation = ?, updated_at = ? WHERE singleton = 1",
                (generation, _iso(now)),
            )
            self._db.execute(
                """UPDATE writer_binding SET generation = ?, active = 1, updated_at = ?
                   WHERE core_id = ?""",
                (generation, _iso(now), row["core_id"]),
            )
        return self.local_identity()[0]

    def assert_local_writer(self, *, core_id: UUID, platform_id: str, generation: int) -> None:
        row = self._db.execute(
            "SELECT * FROM writer_binding WHERE core_id = ?", (str(core_id),),
        ).fetchone()
        if row is None or row["active"] != 1:
            raise FederationIdentityError("no active writer binding for this Core")
        if row["platform_id"] != platform_id or row["generation"] != generation:
            raise FederationIdentityError("writer binding does not match this exact generation")

    # ------------------------------------------------------------------
    # Peer enrollment and per-direction authorization
    # ------------------------------------------------------------------
    def _peer_from_row(self, row: sqlite3.Row) -> PeerRecord:
        return PeerRecord(
            peer_id=UUID(row["peer_id"]),
            remote_platform_id=row["remote_platform_id"],
            remote_core_id=UUID(row["remote_core_id"]),
            remote_generation=row["remote_generation"],
            display_name=row["display_name"],
            trust_anchor=row["trust_anchor"],
            state=PeerState(row["state"]),
            outbound_allowed=bool(row["outbound_allowed"]),
            inbound_allowed=bool(row["inbound_allowed"]),
            revision=row["revision"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
            expires_at=_parse(row["expires_at"]),
        )

    def peer_by_id(self, peer_id: UUID) -> PeerRecord | None:
        row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
        return None if row is None else self._peer_from_row(row)

    def peer_by_identity(self, platform_id: str, core_id: UUID) -> PeerRecord | None:
        row = self._db.execute(
            "SELECT * FROM peer WHERE remote_platform_id = ? AND remote_core_id = ?",
            (platform_id, str(core_id)),
        ).fetchone()
        return None if row is None else self._peer_from_row(row)

    def list_peers(self) -> tuple[PeerRecord, ...]:
        rows = self._db.execute("SELECT * FROM peer ORDER BY created_at, peer_id").fetchall()
        return tuple(self._peer_from_row(row) for row in rows)

    def request_peer(
        self,
        remote: CoreIdentity,
        *,
        trust_anchor: str,
        direction: ContactDirection,
        expires_at: datetime,
        now: datetime,
    ) -> PeerRecord:
        if not isinstance(remote, CoreIdentity):
            raise TypeError("remote must be CoreIdentity")
        if not isinstance(direction, ContactDirection):
            raise TypeError("direction must be ContactDirection")
        anchor = _trust_anchor(trust_anchor)
        expiry = _utc(expires_at, "expires_at")
        moment = _utc(now, "now")
        if expiry <= moment:
            raise ValueError("peer enrollment expiry must be in the future")
        identity, _ = self.local_identity()
        if remote.core_id == identity.core_id:
            raise FederationIdentityError(
                "a Core identity cannot be enrolled as its own remote peer"
            )
        with self._transaction():
            conflicting = self._db.execute(
                """SELECT remote_platform_id FROM peer
                   WHERE remote_core_id = ? AND remote_platform_id != ?""",
                (str(remote.core_id), remote.platform_id),
            ).fetchone()
            if conflicting is not None:
                raise FederationIdentityError(
                    "this Core identity is already bound to another exact Platform"
                )
            existing = self._db.execute(
                "SELECT * FROM peer WHERE remote_platform_id = ? AND remote_core_id = ?",
                (remote.platform_id, str(remote.core_id)),
            ).fetchone()
            if existing is not None:
                existing_state = PeerState(existing["state"])
                expected = (
                    PeerState.PENDING_OUTBOUND
                    if direction is ContactDirection.OUTBOUND
                    else PeerState.PENDING_INBOUND
                )
                if (
                    existing_state is expected
                    and existing["remote_generation"] == remote.generation
                    and existing["trust_anchor"] == anchor
                ):
                    return self._peer_from_row(existing)
                raise FederationConflict(
                    "peer is already enrolled; trust or generation changes require "
                    "explicit re-enrollment"
                )
            peer_id = uuid4()
            self._db.execute(
                """INSERT INTO peer
                   (peer_id, invitation_id, remote_platform_id, remote_core_id,
                    remote_generation, display_name, trust_anchor, state,
                    outbound_allowed, inbound_allowed, revision, created_at,
                    updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1, ?, ?, ?)""",
                (
                    str(peer_id), str(uuid4()), remote.platform_id, str(remote.core_id),
                    remote.generation, remote.display_name, anchor,
                    PeerState.PENDING_OUTBOUND.value
                    if direction is ContactDirection.OUTBOUND
                    else PeerState.PENDING_INBOUND.value,
                    _iso(moment), _iso(moment), _iso(expiry),
                ),
            )
            row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
            return self._peer_from_row(row)

    def _update_peer(
        self, peer_id: UUID, *, state: PeerState, outbound: bool, inbound: bool,
        now: datetime,
    ) -> PeerRecord:
        with self._transaction():
            row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
            if row is None:
                raise FederationPeerError("peer is not enrolled")
            self._db.execute(
                """UPDATE peer
                   SET state = ?, outbound_allowed = ?, inbound_allowed = ?,
                       revision = revision + 1, updated_at = ?
                   WHERE peer_id = ?""",
                (state.value, int(outbound), int(inbound), _iso(now), str(peer_id)),
            )
            updated = self._db.execute(
                "SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),),
            ).fetchone()
            return self._peer_from_row(updated)

    def accept_peer(
        self, peer_id: UUID, *, outbound: bool, inbound: bool, now: datetime,
    ) -> PeerRecord:
        if type(outbound) is not bool or type(inbound) is not bool:
            raise TypeError("direction consent must be boolean")
        row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
        if row is None:
            raise FederationPeerError("peer is not enrolled")
        if PeerState(row["state"]) not in {
            PeerState.PENDING_OUTBOUND, PeerState.PENDING_INBOUND, PeerState.ACTIVE,
        }:
            raise FederationPeerError("only a pending or active peer can be accepted")
        return self._update_peer(
            peer_id, state=PeerState.ACTIVE, outbound=outbound, inbound=inbound, now=now,
        )

    def deny_peer(self, peer_id: UUID, *, now: datetime) -> PeerRecord:
        return self._update_peer(
            peer_id, state=PeerState.DENIED, outbound=False, inbound=False, now=now,
        )

    def block_peer(self, peer_id: UUID, *, now: datetime) -> PeerRecord:
        return self._update_peer(
            peer_id, state=PeerState.BLOCKED, outbound=False, inbound=False, now=now,
        )

    def revoke_peer(self, peer_id: UUID, *, now: datetime) -> PeerRecord:
        return self._update_peer(
            peer_id, state=PeerState.REVOKED, outbound=False, inbound=False, now=now,
        )

    def update_peer_generation(
        self, peer_id: UUID, *, generation: int, now: datetime,
    ) -> PeerRecord:
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be a positive integer")
        with self._transaction():
            row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
            if row is None:
                raise FederationPeerError("peer is not enrolled")
            if generation <= row["remote_generation"]:
                raise FederationIdentityError("peer generation must strictly advance")
            if PeerState(row["state"]) is PeerState.REVOKED:
                raise FederationPeerError("a revoked peer cannot rotate generation in place")
            self._db.execute(
                """UPDATE peer SET remote_generation = ?, revision = revision + 1,
                   updated_at = ? WHERE peer_id = ?""",
                (generation, _iso(now), str(peer_id)),
            )
            updated = self._db.execute(
                "SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),),
            ).fetchone()
            return self._peer_from_row(updated)

    def assert_peer_authorized(
        self, peer_id: UUID, *, direction: ContactDirection, now: datetime,
        authenticated_platform_id: str | None = None,
        authenticated_core_id: UUID | None = None,
        authenticated_generation: int | None = None,
        authenticated_trust_anchor: str | None = None,
    ) -> PeerRecord:
        row = self._db.execute("SELECT * FROM peer WHERE peer_id = ?", (str(peer_id),)).fetchone()
        if row is None:
            raise FederationPeerError("peer is not enrolled")
        peer = self._peer_from_row(row)
        if peer.state is not PeerState.ACTIVE:
            raise FederationPeerError(f"peer state {peer.state.value} does not permit contact")
        allowed = peer.outbound_allowed if direction is ContactDirection.OUTBOUND else peer.inbound_allowed
        if not allowed:
            raise FederationPeerError(f"{direction.value} contact is not authorized for this peer")
        if peer.expires_at <= _utc(now, "now"):
            raise FederationPeerError("peer trust enrollment has expired")
        if authenticated_platform_id is not None and authenticated_platform_id != peer.remote_platform_id:
            raise FederationIdentityError("authenticated Platform does not match the enrolled peer")
        if authenticated_core_id is not None and authenticated_core_id != peer.remote_core_id:
            raise FederationIdentityError("authenticated Core does not match the enrolled peer")
        if authenticated_generation is not None and authenticated_generation != peer.remote_generation:
            raise FederationIdentityError("authenticated writer generation is stale or unknown")
        if (
            authenticated_trust_anchor is not None
            and authenticated_trust_anchor != peer.trust_anchor
        ):
            raise FederationIdentityError("authenticated trust anchor does not match the pin")
        return peer

    # ------------------------------------------------------------------
    # Rooms and membership epochs
    # ------------------------------------------------------------------
    def create_room(self, room_id: RoomId, *, kind: RoomKind, now: datetime) -> None:
        if not isinstance(room_id, RoomId) or not isinstance(kind, RoomKind):
            raise TypeError("typed room id and kind are required")
        with self._transaction():
            row = self._db.execute("SELECT kind FROM room WHERE room_id = ?", (room_id.value,)).fetchone()
            if row is not None:
                if row["kind"] != kind.value:
                    raise FederationRoomError("room already exists with another kind")
                return
            self._db.execute(
                "INSERT INTO room (room_id, kind, created_at) VALUES (?, ?, ?)",
                (room_id.value, kind.value, _iso(now)),
            )

    def room_kind(self, room_id: RoomId) -> RoomKind:
        row = self._db.execute("SELECT kind FROM room WHERE room_id = ?", (room_id.value,)).fetchone()
        if row is None:
            raise FederationRoomError("unknown room")
        return RoomKind(row["kind"])

    def set_membership(
        self,
        room_id: RoomId,
        core_id: UUID,
        *,
        status: MembershipStatus,
        history_from_sequence: int,
        now: datetime,
        joined_at: datetime | None = None,
    ) -> RoomMembership:
        if not isinstance(room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        if not isinstance(core_id, UUID) or core_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        if not isinstance(status, MembershipStatus):
            raise TypeError("status must be MembershipStatus")
        if type(history_from_sequence) is not int or history_from_sequence < 0:
            raise ValueError("history_from_sequence must be nonnegative")
        moment = _utc(now, "now")
        with self._transaction():
            room = self._db.execute("SELECT kind FROM room WHERE room_id = ?", (room_id.value,)).fetchone()
            if room is None:
                raise FederationRoomError("unknown room")
            row = self._db.execute(
                "SELECT * FROM membership WHERE room_id = ? AND core_id = ?",
                (room_id.value, str(core_id)),
            ).fetchone()
            if row is None:
                epoch = 1
                joined = _utc(joined_at, "joined_at") if joined_at is not None else moment
                self._db.execute(
                    """INSERT INTO membership
                       (room_id, core_id, epoch, status, joined_at, history_from_sequence)
                       VALUES (?, ?, 1, ?, ?, ?)""",
                    (room_id.value, str(core_id), status.value, _iso(joined), history_from_sequence),
                )
            else:
                epoch = row["epoch"] + 1
                joined = _parse(row["joined_at"])
                if joined_at is not None:
                    joined = _utc(joined_at, "joined_at")
                self._db.execute(
                    """UPDATE membership
                       SET epoch = ?, status = ?, joined_at = ?, history_from_sequence = ?
                       WHERE room_id = ? AND core_id = ?""",
                    (
                        epoch, status.value, _iso(joined), history_from_sequence,
                        room_id.value, str(core_id),
                    ),
                )
            return RoomMembership(
                room_id=room_id, core_id=core_id, epoch=epoch, status=status,
                joined_at=joined, history_from_sequence=history_from_sequence,
            )

    def membership(self, room_id: RoomId, core_id: UUID) -> RoomMembership | None:
        row = self._db.execute(
            "SELECT * FROM membership WHERE room_id = ? AND core_id = ?",
            (room_id.value, str(core_id)),
        ).fetchone()
        if row is None:
            return None
        return RoomMembership(
            room_id=room_id,
            core_id=core_id,
            epoch=row["epoch"],
            status=MembershipStatus(row["status"]),
            joined_at=_parse(row["joined_at"]),
            history_from_sequence=row["history_from_sequence"],
        )

    def require_active_member(self, room_id: RoomId, core_id: UUID) -> RoomMembership:
        membership = self.membership(room_id, core_id)
        if membership is None:
            raise FederationRoomError("Core is not a member of this room")
        if membership.status is not MembershipStatus.ACTIVE:
            raise FederationRoomError("Core membership is not active")
        return membership

    def active_members(self, room_id: RoomId) -> tuple[RoomMembership, ...]:
        rows = self._db.execute(
            "SELECT * FROM membership WHERE room_id = ? AND status = ? ORDER BY core_id",
            (room_id.value, MembershipStatus.ACTIVE.value),
        ).fetchall()
        return tuple(
            RoomMembership(
                room_id=room_id,
                core_id=UUID(row["core_id"]),
                epoch=row["epoch"],
                status=MembershipStatus(row["status"]),
                joined_at=_parse(row["joined_at"]),
                history_from_sequence=row["history_from_sequence"],
            )
            for row in rows
        )

    # ------------------------------------------------------------------
    # Sequence allocation and replay bounds
    # ------------------------------------------------------------------
    def allocate_outgoing_sequence(self, room_id: RoomId, core_id: UUID) -> int:
        with self._transaction():
            row = self._db.execute(
                "SELECT next_sequence FROM outgoing_sequence WHERE room_id = ? AND core_id = ?",
                (room_id.value, str(core_id)),
            ).fetchone()
            sequence = 1 if row is None else row["next_sequence"]
            if row is None:
                self._db.execute(
                    """INSERT INTO outgoing_sequence (room_id, core_id, next_sequence)
                       VALUES (?, ?, ?)""",
                    (room_id.value, str(core_id), sequence + 1),
                )
            else:
                self._db.execute(
                    """UPDATE outgoing_sequence SET next_sequence = ?
                       WHERE room_id = ? AND core_id = ?""",
                    (sequence + 1, room_id.value, str(core_id)),
                )
            return sequence

    def assert_next_incoming_sequence(self, room_id: RoomId, source_core_id: UUID, sequence: int) -> None:
        row = self._db.execute(
            "SELECT last_sequence FROM incoming_sequence WHERE room_id = ? AND source_core_id = ?",
            (room_id.value, str(source_core_id)),
        ).fetchone()
        last = 0 if row is None else row["last_sequence"]
        if sequence <= last:
            raise FederationReplay("message sequence is not greater than the last accepted sequence")

    # ------------------------------------------------------------------
    # Outbox
    # ------------------------------------------------------------------
    def _outbox_from_row(self, row: sqlite3.Row) -> OutboxRecord:
        return OutboxRecord(
            message_id=UUID(row["message_id"]),
            destination_platform_id=row["destination_platform_id"],
            destination_core_id=UUID(row["destination_core_id"]),
            room_id=RoomId(row["room_id"]),
            sequence=row["sequence"],
            idempotency_key=row["idempotency_key"],
            payload_digest=row["payload_digest"],
            status=DeliveryStatus(row["status"]),
            attempts=row["attempts"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
            expires_at=_parse(row["expires_at"]),
            envelope_json=row["envelope_json"],
        )

    def outbox_by_idempotency(self, destination_platform_id: str, key: str) -> OutboxRecord | None:
        row = self._db.execute(
            "SELECT * FROM outbox WHERE destination_platform_id = ? AND idempotency_key = ?",
            (destination_platform_id, key),
        ).fetchone()
        return None if row is None else self._outbox_from_row(row)

    def outbox_record(self, message_id: UUID) -> OutboxRecord | None:
        row = self._db.execute(
            "SELECT * FROM outbox WHERE message_id = ?", (str(message_id),),
        ).fetchone()
        return None if row is None else self._outbox_from_row(row)

    def enqueue_outbox(self, envelope: PeerEnvelope, *, now: datetime) -> tuple[OutboxRecord, bool]:
        if not isinstance(envelope, PeerEnvelope):
            raise TypeError("envelope must be PeerEnvelope")
        serialized = canonical_json(envelope.to_payload())
        moment = _utc(now, "now")
        with self._transaction():
            existing = self._db.execute(
                """SELECT * FROM outbox
                   WHERE destination_platform_id = ? AND idempotency_key = ?""",
                (envelope.destination_platform_id, envelope.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["payload_digest"] != envelope.payload_digest:
                    raise FederationConflict(
                        "idempotency key was reused with different message content"
                    )
                return self._outbox_from_row(existing), True
            same_message = self._db.execute(
                "SELECT * FROM outbox WHERE message_id = ?", (str(envelope.message_id),),
            ).fetchone()
            if same_message is not None:
                if (
                    same_message["destination_platform_id"] != envelope.destination_platform_id
                    or same_message["destination_core_id"] != str(envelope.destination_core_id)
                ):
                    raise FederationConflict(
                        "message id is already bound to another destination"
                    )
                if same_message["payload_digest"] != envelope.payload_digest:
                    raise FederationConflict("message id was reused with different content")
                return self._outbox_from_row(same_message), True
            self._db.execute(
                """INSERT INTO outbox
                   (message_id, destination_platform_id, destination_core_id, room_id,
                    sequence, idempotency_key, payload_digest, status, attempts,
                    created_at, updated_at, expires_at, envelope_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                (
                    str(envelope.message_id), envelope.destination_platform_id,
                    str(envelope.destination_core_id), envelope.message.room_id.value,
                    envelope.message.sequence, envelope.idempotency_key,
                    envelope.payload_digest, DeliveryStatus.QUEUED.value,
                    _iso(moment), _iso(moment), _iso(envelope.expires_at), serialized,
                ),
            )
            row = self._db.execute(
                "SELECT * FROM outbox WHERE message_id = ?", (str(envelope.message_id),),
            ).fetchone()
            return self._outbox_from_row(row), False

    def _set_outbox_status(
        self, message_id: UUID, status: DeliveryStatus, *, detail: str | None,
        now: datetime, increment_attempts: bool = False,
    ) -> OutboxRecord:
        with self._transaction():
            row = self._db.execute(
                "SELECT * FROM outbox WHERE message_id = ?", (str(message_id),),
            ).fetchone()
            if row is None:
                raise FederationPeerError("outbox message is unknown")
            current = DeliveryStatus(row["status"])
            if current is status:
                if increment_attempts:
                    self._db.execute(
                        "UPDATE outbox SET attempts = attempts + 1, updated_at = ? WHERE message_id = ?",
                        (_iso(now), str(message_id)),
                    )
                updated = self._db.execute(
                    "SELECT * FROM outbox WHERE message_id = ?", (str(message_id),),
                ).fetchone()
                return self._outbox_from_row(updated)
            if current in _TERMINAL_OUTBOX:
                raise FederationConflict(
                    f"outbox status {current.value} is terminal and cannot become {status.value}"
                )
            if status not in _TRANSITIONS.get(current, frozenset()):
                raise FederationConflict(
                    f"outbox status cannot transition from {current.value} to {status.value}"
                )
            self._db.execute(
                """UPDATE outbox
                   SET status = ?, detail = ?, updated_at = ?,
                       attempts = attempts + ?
                   WHERE message_id = ?""",
                (
                    status.value, detail, _iso(now), 1 if increment_attempts else 0,
                    str(message_id),
                ),
            )
            updated = self._db.execute(
                "SELECT * FROM outbox WHERE message_id = ?", (str(message_id),),
            ).fetchone()
            return self._outbox_from_row(updated)

    def record_send_attempt(self, message_id: UUID, *, outcome: str, detail: str | None, now: datetime) -> OutboxRecord:
        if outcome == "DELIVERED":
            return self._set_outbox_status(
                message_id, DeliveryStatus.RECEIVED, detail=detail, now=now,
                increment_attempts=True,
            )
        if outcome == "UNCERTAIN":
            current = self.outbox_record(message_id)
            if current is None:
                raise FederationPeerError("outbox message is unknown")
            target = (
                DeliveryStatus.OUTCOME_UNKNOWN
                if current.status is DeliveryStatus.OUTCOME_UNKNOWN
                else DeliveryStatus.SENT_UNCONFIRMED
            )
            return self._set_outbox_status(
                message_id, target, detail=detail, now=now, increment_attempts=True,
            )
        if outcome == "REJECTED":
            return self._set_outbox_status(
                message_id, DeliveryStatus.DENIED, detail=detail, now=now,
                increment_attempts=True,
            )
        raise ValueError("unknown transport outcome")

    def record_recipient_ack(
        self, message_id: UUID, status: DeliveryStatus, *, detail: str | None, now: datetime,
    ) -> OutboxRecord:
        if status not in _TERMINAL_OUTBOX:
            raise ValueError("recipient acknowledgment must be terminal")
        return self._set_outbox_status(message_id, status, detail=detail, now=now)

    def reconcile_outbox_received(self, message_id: UUID, *, now: datetime) -> OutboxRecord:
        """Mark an uncertain/queued send as transport-received, never accepted."""
        return self._set_outbox_status(
            message_id, DeliveryStatus.RECEIVED,
            detail="reconciled transport receipt", now=now,
        )

    def mark_outbox_expired(self, now: datetime) -> int:
        with self._transaction():
            rows = self._db.execute(
                "SELECT message_id FROM outbox WHERE status IN (?, ?, ?) AND expires_at <= ?",
                (
                    DeliveryStatus.QUEUED.value, DeliveryStatus.SENT_UNCONFIRMED.value,
                    DeliveryStatus.OUTCOME_UNKNOWN.value, _iso(now),
                ),
            ).fetchall()
            for row in rows:
                self._db.execute(
                    "UPDATE outbox SET status = ?, updated_at = ? WHERE message_id = ?",
                    (DeliveryStatus.EXPIRED.value, _iso(now), row["message_id"]),
                )
            return len(rows)

    def list_outbox(self, *, limit: int = 1000) -> tuple[OutboxRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("limit must be in 1..100000")
        rows = self._db.execute(
            "SELECT * FROM outbox ORDER BY created_at, message_id LIMIT ?", (limit,),
        ).fetchall()
        return tuple(self._outbox_from_row(row) for row in rows)

    def pending_outbox(self, *, now: datetime, limit: int = 1000) -> tuple[OutboxRecord, ...]:
        rows = self._db.execute(
            """SELECT * FROM outbox
               WHERE status IN (?, ?, ?) AND expires_at > ?
               ORDER BY created_at, message_id LIMIT ?""",
            (
                DeliveryStatus.QUEUED.value, DeliveryStatus.SENT_UNCONFIRMED.value,
                DeliveryStatus.OUTCOME_UNKNOWN.value, _iso(now), limit,
            ),
        ).fetchall()
        return tuple(self._outbox_from_row(row) for row in rows)

    # ------------------------------------------------------------------
    # Inbox, deduplication and replay defense
    # ------------------------------------------------------------------
    def _inbox_from_row(self, row: sqlite3.Row) -> InboxRecord:
        return InboxRecord(
            message_id=UUID(row["message_id"]),
            source_platform_id=row["source_platform_id"],
            source_core_id=UUID(row["source_core_id"]),
            room_id=RoomId(row["room_id"]),
            sequence=row["sequence"],
            status=DeliveryStatus(row["status"]),
            payload_digest=row["payload_digest"],
            received_at=_parse(row["received_at"]),
            updated_at=_parse(row["updated_at"]),
            envelope_json=row["envelope_json"],
        )

    def record_inbound(self, envelope: PeerEnvelope, *, now: datetime) -> tuple[InboxRecord, bool]:
        if not isinstance(envelope, PeerEnvelope):
            raise TypeError("envelope must be PeerEnvelope")
        serialized = canonical_json(envelope.to_payload())
        moment = _utc(now, "now")
        with self._transaction():
            existing = self._db.execute(
                """SELECT * FROM inbox
                   WHERE source_platform_id = ? AND source_core_id = ? AND message_id = ?""",
                (
                    envelope.source_platform_id, str(envelope.source_core_id),
                    str(envelope.message_id),
                ),
            ).fetchone()
            if existing is not None:
                if existing["payload_digest"] != envelope.payload_digest:
                    raise FederationReplay("message id was reused with different content")
                return self._inbox_from_row(existing), True
            other_source = self._db.execute(
                "SELECT source_platform_id, source_core_id FROM inbox WHERE message_id = ?",
                (str(envelope.message_id),),
            ).fetchone()
            if other_source is not None:
                raise FederationReplay(
                    "message id is already recorded from another source identity"
                )
            seq_row = self._db.execute(
                """SELECT last_sequence FROM incoming_sequence
                   WHERE room_id = ? AND source_core_id = ?""",
                (envelope.message.room_id.value, str(envelope.source_core_id)),
            ).fetchone()
            last = 0 if seq_row is None else seq_row["last_sequence"]
            if envelope.message.sequence <= last:
                raise FederationReplay("message sequence is not greater than the last accepted sequence")
            self._db.execute(
                """INSERT INTO inbox
                   (message_id, source_platform_id, source_core_id, room_id, sequence,
                    status, payload_digest, received_at, updated_at, envelope_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(envelope.message_id), envelope.source_platform_id,
                    str(envelope.source_core_id), envelope.message.room_id.value,
                    envelope.message.sequence, DeliveryStatus.RECEIVED.value,
                    envelope.payload_digest, _iso(moment), _iso(moment), serialized,
                ),
            )
            if seq_row is None:
                self._db.execute(
                    """INSERT INTO incoming_sequence (room_id, source_core_id, last_sequence)
                       VALUES (?, ?, ?)""",
                    (envelope.message.room_id.value, str(envelope.source_core_id), envelope.message.sequence),
                )
            else:
                self._db.execute(
                    """UPDATE incoming_sequence SET last_sequence = ?
                       WHERE room_id = ? AND source_core_id = ?""",
                    (
                        envelope.message.sequence, envelope.message.room_id.value,
                        str(envelope.source_core_id),
                    ),
                )
            row = self._db.execute(
                "SELECT * FROM inbox WHERE message_id = ?", (str(envelope.message_id),),
            ).fetchone()
            return self._inbox_from_row(row), False

    def inbox_record(self, message_id: UUID) -> InboxRecord | None:
        row = self._db.execute(
            "SELECT * FROM inbox WHERE message_id = ?", (str(message_id),),
        ).fetchone()
        return None if row is None else self._inbox_from_row(row)

    def list_inbox(self, *, limit: int = 1000) -> tuple[InboxRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("limit must be in 1..100000")
        rows = self._db.execute(
            "SELECT * FROM inbox ORDER BY received_at, message_id LIMIT ?", (limit,),
        ).fetchall()
        return tuple(self._inbox_from_row(row) for row in rows)

    def decide_inbound(
        self, message_id: UUID, status: DeliveryStatus, *, detail: str | None, now: datetime,
    ) -> InboxRecord:
        if status not in {
            DeliveryStatus.ACCEPTED,
            DeliveryStatus.DECLINED,
            DeliveryStatus.DENIED,
            DeliveryStatus.HANDLED,
            DeliveryStatus.EXPIRED,
        }:
            raise ValueError("inbound decision must be a terminal status")
        with self._transaction():
            row = self._db.execute(
                "SELECT * FROM inbox WHERE message_id = ?", (str(message_id),),
            ).fetchone()
            if row is None:
                raise FederationPeerError("inbound message is unknown")
            current = DeliveryStatus(row["status"])
            if current is status:
                return self._inbox_from_row(row)
            if current is not DeliveryStatus.RECEIVED:
                raise FederationConflict(
                    f"inbound status {current.value} is already terminal"
                )
            self._db.execute(
                "UPDATE inbox SET status = ?, detail = ?, updated_at = ? WHERE message_id = ?",
                (status.value, detail, _iso(now), str(message_id)),
            )
            updated = self._db.execute(
                "SELECT * FROM inbox WHERE message_id = ?", (str(message_id),),
            ).fetchone()
            return self._inbox_from_row(updated)

    # ------------------------------------------------------------------
    # Emergency STOP
    # ------------------------------------------------------------------
    def engage_stop(self, *, now: datetime) -> None:
        with self._transaction():
            self._db.execute(
                """INSERT INTO security_state (singleton, stopped, updated_at)
                   VALUES (1, 1, ?)
                   ON CONFLICT(singleton) DO UPDATE SET stopped = 1, updated_at = excluded.updated_at""",
                (_iso(now),),
            )

    def clear_stop(self, *, now: datetime) -> None:
        with self._transaction():
            self._db.execute(
                """INSERT INTO security_state (singleton, stopped, updated_at)
                   VALUES (1, 0, ?)
                   ON CONFLICT(singleton) DO UPDATE SET stopped = 0, updated_at = excluded.updated_at""",
                (_iso(now),),
            )

    def is_stopped(self) -> bool:
        row = self._db.execute(
            "SELECT stopped FROM security_state WHERE singleton = 1",
        ).fetchone()
        return bool(row["stopped"]) if row is not None else False

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def counts(self) -> dict[str, int]:
        return {
            table: self._db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for table in ("peer", "room", "membership", "outbox", "inbox")
        }

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
