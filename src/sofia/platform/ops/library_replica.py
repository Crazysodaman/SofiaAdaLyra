"""D028 read-only logical Library replica synchronization.

A replica authenticates the configured primary, verifies the existing signed
immutable publisher index, then fetches only exact public/permitted CAS objects
by signed digest through the existing bounded chunk transport. It reuses the
canonical Platform-local SQLite state and quarantine receiver. It cannot claim
a primary epoch, write catalog metadata, sign packages, approve owner actions
or serve protected Core/private state.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
import sqlite3
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_signed_index import (
    VerifiedLibraryIndex, verify_signed_library_index,
)
from sofia.platform.ops.library_signed_selection import (
    _ITEM_KEYS, _SOURCE_KEYS,
)
from sofia.platform.ops.library_tls_chunk_transport import MAX_CHUNK
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks
from sofia.platform.state.local_store import PlatformLocalStore

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX = 2**53 - 1
_REPLICA_STATES = frozenset({
    "UNKNOWN", "SYNCING", "SYNCED", "STALE", "OFFLINE", "NEEDS_RESEED", "REVOKED",
})


class LibraryReplicaDenied(PermissionError):
    """The configured primary, signed index or object is not replica-safe."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LibraryReplicaDenied("trusted timezone-aware replica clock required")
    return value.astimezone(timezone.utc)


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise LibraryReplicaDenied(f"bounded {label} required")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or not 1 <= value <= _MAX:
        raise LibraryReplicaDenied(f"bounded {label} required")
    return value


def _error_code(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not 1 <= len(value) <= 64:
        raise LibraryReplicaDenied("bounded replica error code required")
    return value


@dataclass(frozen=True, slots=True)
class LibraryReplicaState:
    logical_library_id: str
    replica_platform_id: str
    primary_platform_id: str
    state: str
    last_primary_epoch: int | None
    last_catalog_revision: int | None
    last_index_sha256: str | None
    signed_index: bytes | None
    fresh_until: datetime | None
    expires_at: datetime | None
    last_synced_at: datetime | None
    last_error_code: str | None
    updated_at: datetime

    @property
    def read_only(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class ReplicaObjectResult:
    content_sha256: str
    size_bytes: int
    offset: int
    complete: bool
    path: object | None


class LibraryReplicaStateStore:
    """Durable replica evidence in the one existing Platform-local SQLite file."""

    def __init__(
        self, storage: PlatformLocalStore, *, logical_library_id: str,
        replica_platform_id: str, primary_platform_id: str | None = None,
    ) -> None:
        if not isinstance(storage, PlatformLocalStore):
            raise LibraryReplicaDenied("existing Platform-local SQLite state required")
        self.storage = storage
        self.logical_library_id = _identifier(
            logical_library_id, "logical Library identity"
        )
        self.replica_platform_id = _identifier(
            replica_platform_id, "replica Platform identity"
        )
        self.primary_platform_id = (
            None if primary_platform_id is None
            else _identifier(primary_platform_id, "primary Platform identity")
        )
        if self.primary_platform_id == self.replica_platform_id:
            raise LibraryReplicaDenied("replica must differ from its primary")

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.execute("""
            CREATE TABLE IF NOT EXISTS platform_library_replica_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                logical_library_id TEXT NOT NULL,
                replica_platform_id TEXT NOT NULL,
                primary_platform_id TEXT NOT NULL,
                state TEXT NOT NULL,
                last_primary_epoch INTEGER,
                last_catalog_revision INTEGER,
                last_index_sha256 TEXT,
                signed_index BLOB,
                fresh_until TEXT,
                expires_at TEXT,
                last_synced_at TEXT,
                last_error_code TEXT,
                read_only INTEGER NOT NULL CHECK(read_only=1),
                updated_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _table_exists(db: sqlite3.Connection) -> bool:
        return db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='platform_library_replica_state'"
        ).fetchone() is not None

    @staticmethod
    def _time(value: object) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)

    def _decode(self, row: sqlite3.Row) -> LibraryReplicaState:
        try:
            state = LibraryReplicaState(
                logical_library_id=row["logical_library_id"],
                replica_platform_id=row["replica_platform_id"],
                primary_platform_id=row["primary_platform_id"],
                state=row["state"],
                last_primary_epoch=row["last_primary_epoch"],
                last_catalog_revision=row["last_catalog_revision"],
                last_index_sha256=row["last_index_sha256"],
                signed_index=(
                    None if row["signed_index"] is None
                    else bytes(row["signed_index"])
                ),
                fresh_until=self._time(row["fresh_until"]),
                expires_at=self._time(row["expires_at"]),
                last_synced_at=self._time(row["last_synced_at"]),
                last_error_code=row["last_error_code"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise LibraryReplicaDenied("corrupt read-only replica state") from exc
        if state.logical_library_id != self.logical_library_id:
            raise LibraryReplicaDenied("replica state belongs to another logical Library")
        if state.replica_platform_id != self.replica_platform_id:
            raise LibraryReplicaDenied("replica state belongs to another installed Platform")
        if (self.primary_platform_id is not None
                and state.primary_platform_id != self.primary_platform_id):
            raise LibraryReplicaDenied("replica state belongs to another primary")
        return state

    def _read(self, db: sqlite3.Connection) -> LibraryReplicaState | None:
        if not self._table_exists(db):
            return None
        row = db.execute(
            "SELECT logical_library_id,replica_platform_id,primary_platform_id,"
            "state,last_primary_epoch,last_catalog_revision,last_index_sha256,"
            "signed_index,fresh_until,expires_at,last_synced_at,last_error_code,"
            "updated_at FROM platform_library_replica_state WHERE singleton=1"
        ).fetchone()
        return None if row is None else self._decode(row)

    def current(self) -> LibraryReplicaState | None:
        with closing(self.storage.connect()) as db:
            db.row_factory = sqlite3.Row
            return self._read(db)

    def record_index(
        self, *, index: VerifiedLibraryIndex, raw_signed_index: bytes,
        primary_epoch: int, now: datetime,
    ) -> LibraryReplicaState:
        if not isinstance(index, VerifiedLibraryIndex):
            raise LibraryReplicaDenied("independently verified signed index required")
        if (type(raw_signed_index) is not bytes
                or sha256(raw_signed_index).hexdigest() != index.signed_index_sha256):
            raise LibraryReplicaDenied("exact verified signed index bytes required")
        epoch = _positive(primary_epoch, "primary epoch")
        moment = _utc(now)
        fresh_until = _utc(datetime.fromisoformat(
            index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
        ))
        expires_at = index.expires_at
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                self._create_schema(db)
                current = self._read(db)
                if current is not None:
                    if current.primary_platform_id != index.source_platform_id:
                        raise LibraryReplicaDenied(
                            "signed index source differs from configured primary"
                        )
                    if (current.last_primary_epoch is not None
                            and epoch < current.last_primary_epoch):
                        raise LibraryReplicaDenied("primary epoch rollback denied")
                    if (current.last_catalog_revision is not None
                            and index.catalog_revision < current.last_catalog_revision):
                        raise LibraryReplicaDenied("catalog revision rollback denied")
                    if (current.last_catalog_revision == index.catalog_revision
                            and current.last_index_sha256
                            != index.signed_index_sha256):
                        raise LibraryReplicaDenied(
                            "conflicting signed index at one replica revision"
                        )
                db.execute("""
                    INSERT INTO platform_library_replica_state (
                        singleton,logical_library_id,replica_platform_id,
                        primary_platform_id,state,last_primary_epoch,
                        last_catalog_revision,last_index_sha256,signed_index,
                        fresh_until,expires_at,last_synced_at,last_error_code,
                        read_only,updated_at
                    ) VALUES (1,?,?,?,'SYNCED',?,?,?,?,?,?,?,NULL,1,?)
                    ON CONFLICT(singleton) DO UPDATE SET
                        primary_platform_id=excluded.primary_platform_id,
                        state=excluded.state,
                        last_primary_epoch=excluded.last_primary_epoch,
                        last_catalog_revision=excluded.last_catalog_revision,
                        last_index_sha256=excluded.last_index_sha256,
                        signed_index=excluded.signed_index,
                        fresh_until=excluded.fresh_until,
                        expires_at=excluded.expires_at,
                        last_synced_at=excluded.last_synced_at,
                        last_error_code=NULL,
                        read_only=1,
                        updated_at=excluded.updated_at
                """, (
                    self.logical_library_id, self.replica_platform_id,
                    index.source_platform_id, epoch, index.catalog_revision,
                    index.signed_index_sha256, raw_signed_index,
                    fresh_until.isoformat(), expires_at.isoformat(),
                    moment.isoformat(), moment.isoformat(),
                ))
                result = self._read(db)
                if result is None:
                    raise LibraryReplicaDenied("replica index commit was not durable")
                return result

    def record_state(
        self, *, state: str, now: datetime, error_code: str | None = None,
    ) -> LibraryReplicaState:
        if type(state) is not str or state not in _REPLICA_STATES:
            raise LibraryReplicaDenied("unknown replica state")
        moment = _utc(now)
        code = _error_code(error_code)
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                self._create_schema(db)
                current = self._read(db)
                if current is None:
                    primary = self.primary_platform_id
                    if primary is None:
                        raise LibraryReplicaDenied(
                            "configured primary required before replica state exists"
                        )
                    db.execute("""
                        INSERT INTO platform_library_replica_state (
                            singleton,logical_library_id,replica_platform_id,
                            primary_platform_id,state,last_primary_epoch,
                            last_catalog_revision,last_index_sha256,signed_index,
                            fresh_until,expires_at,last_synced_at,last_error_code,
                            read_only,updated_at
                        ) VALUES (1,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,
                                  NULL,?,1,?)
                    """, (
                        self.logical_library_id, self.replica_platform_id,
                        primary, state, code, moment.isoformat(),
                    ))
                else:
                    db.execute("""
                        UPDATE platform_library_replica_state SET
                            state=?,last_error_code=?,read_only=1,updated_at=?
                        WHERE singleton=1
                    """, (state, code, moment.isoformat()))
                result = self._read(db)
                if result is None:
                    raise LibraryReplicaDenied("replica state commit was not durable")
                return result

    def status(self, *, now: datetime) -> dict[str, object]:
        moment = _utc(now)
        row = self.current()
        base = {
            "schema": "aegis.library.replica-status.v1",
            "logical_library_id": self.logical_library_id,
            "replica_platform_id": self.replica_platform_id,
            "read_only": True,
            "install_executed": False,
            "core_activated": False,
        }
        if row is None:
            return {
                **base, "state": "UNKNOWN", "primary_platform_id": self.primary_platform_id,
                "last_primary_epoch": None, "last_catalog_revision": None,
                "last_index_sha256": None, "last_synced_at": None,
                "last_error_code": None,
            }
        state = row.state
        if state == "SYNCED":
            if (row.fresh_until is None or row.expires_at is None
                    or moment >= row.fresh_until or moment >= row.expires_at):
                state = "STALE"
        elif state not in _REPLICA_STATES:
            state = "UNKNOWN"
        return {
            **base,
            "state": state,
            "primary_platform_id": row.primary_platform_id,
            "last_primary_epoch": row.last_primary_epoch,
            "last_catalog_revision": row.last_catalog_revision,
            "last_index_sha256": row.last_index_sha256,
            "last_synced_at": (
                None if row.last_synced_at is None else row.last_synced_at.isoformat()
            ),
            "last_error_code": row.last_error_code,
        }


class LibraryReplica:
    """Read-only replica synchronizer; never a primary or signing authority."""

    def __init__(
        self, *,
        state_store: LibraryReplicaStateStore,
        receiver: ChunkedArtifactReceiver,
        logical_library_id: str,
        replica_platform_id: str,
        primary_platform_id: str,
        trusted_publisher_public_key: bytes,
        expected_publisher_key_sha256: str,
        expected_catalog_generation: int,
        minimum_catalog_revision: int,
        authenticate_primary: Callable[[str], bool],
        publisher_key_current: Callable[[str], bool],
        stop_active: Callable[[], bool],
        source_allowed: Callable[[PinnedChunkTransfer], bool],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(state_store, LibraryReplicaStateStore):
            raise LibraryReplicaDenied("canonical replica state store required")
        if not isinstance(receiver, ChunkedArtifactReceiver):
            raise LibraryReplicaDenied("canonical quarantine receiver required")
        if (type(trusted_publisher_public_key) is not bytes
                or len(trusted_publisher_public_key) != 32):
            raise LibraryReplicaDenied("independent 32-byte Ed25519 publisher key required")
        if (type(expected_publisher_key_sha256) is not str
                or _SHA.fullmatch(expected_publisher_key_sha256) is None
                or sha256(trusted_publisher_public_key).hexdigest()
                != expected_publisher_key_sha256):
            raise LibraryReplicaDenied("independent trusted publisher root differs")
        _positive(expected_catalog_generation, "catalog generation")
        _positive(minimum_catalog_revision, "minimum catalog revision")
        for callback in (
            authenticate_primary, publisher_key_current, stop_active, source_allowed,
        ):
            if not callable(callback):
                raise LibraryReplicaDenied("canonical replica authority callbacks required")
        if clock is not None and not callable(clock):
            raise LibraryReplicaDenied("trusted replica clock required")
        self.state_store = state_store
        self.receiver = receiver
        self.logical_library_id = _identifier(
            logical_library_id, "logical Library identity"
        )
        self.replica_platform_id = _identifier(
            replica_platform_id, "replica Platform identity"
        )
        self.primary_platform_id = _identifier(
            primary_platform_id, "primary Platform identity"
        )
        if self.primary_platform_id == self.replica_platform_id:
            raise LibraryReplicaDenied("replica must differ from the primary")
        self.trusted_publisher_public_key = trusted_publisher_public_key
        self.expected_publisher_key_sha256 = expected_publisher_key_sha256
        self.expected_catalog_generation = expected_catalog_generation
        self.minimum_catalog_revision = minimum_catalog_revision
        self._authenticate = authenticate_primary
        self._publisher_current = publisher_key_current
        self._stop = stop_active
        self._source_allowed = source_allowed
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def read_only(self) -> bool:
        return True

    def _now(self, now: datetime | None) -> datetime:
        return _utc(self._clock() if now is None else now)

    def _require_primary(self, now: datetime, *, record: bool = True) -> None:
        if self._stop() is True:
            raise LibraryReplicaDenied("operator STOP prevents replica synchronization")
        if self._authenticate(self.primary_platform_id) is not True:
            if record:
                self.state_store.record_state(
                    state="OFFLINE", now=now, error_code="PRIMARY_NOT_AUTHENTICATED",
                )
            raise LibraryReplicaDenied("configured primary authentication unavailable")
        if self._publisher_current(self.expected_publisher_key_sha256) is not True:
            if record:
                self.state_store.record_state(
                    state="REVOKED", now=now, error_code="PUBLISHER_REVOKED",
                )
            raise LibraryReplicaDenied("publisher root revoked or unavailable")

    @staticmethod
    def _index_source_current(index: VerifiedLibraryIndex, now: datetime) -> None:
        source = index.catalog["source"]
        if (type(source) is not dict or set(source) != _SOURCE_KEYS
                or source["kind"] not in {"OWNER_SELECTED_HUB", "AUTHORIZED_PEER"}
                or source["status"] != "CURRENT"):
            raise LibraryReplicaDenied("signed index source is not a current primary")
        try:
            observed = datetime.fromisoformat(
                source["last_observed_at"].replace("Z", "+00:00")
            )
        except (TypeError, ValueError) as exc:
            raise LibraryReplicaDenied("signed source observation invalid") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise LibraryReplicaDenied("signed source observation lacks timezone")
        observed = observed.astimezone(timezone.utc)
        if observed > now or now - observed > timedelta(minutes=5):
            raise LibraryReplicaDenied("signed primary observation is not current")

    @staticmethod
    def _index_items(index: VerifiedLibraryIndex, now: datetime) -> None:
        if (now >= index.expires_at
                or now >= datetime.fromisoformat(
                    index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)):
            raise LibraryReplicaDenied("signed primary index is stale")
        page = index.catalog["page"]
        if (type(page) is not dict
                or set(page) != {"limit", "next_cursor", "cursor_state"}
                or page["cursor_state"] != "CURRENT"
                or type(page["limit"]) is not int
                or not 1 <= page["limit"] <= 128
                or len(index.catalog["items"]) > page["limit"]):
            raise LibraryReplicaDenied("signed primary catalog page is stale or unbounded")
        for row in index.catalog["items"]:
            if type(row) is not dict or set(row) != _ITEM_KEYS:
                raise LibraryReplicaDenied("unexpected signed catalog item schema")
            if (row["license_distribution"] != "permitted"
                    or row["data_class"] != "public"
                    or row["distribution_allowed"] is not True):
                raise LibraryReplicaDenied(
                    "license-blocked or protected artifact cannot replicate"
                )
            if (type(row["content_digest"]) is not str
                    or _SHA.fullmatch(row["content_digest"]) is None
                    or type(row["manifest_digest"]) is not str
                    or _SHA.fullmatch(row["manifest_digest"]) is None
                    or type(row["revision"]) is not int
                    or not 1 <= row["revision"] <= _MAX
                    or type(row["size_bytes"]) is not int
                    or not 1 <= row["size_bytes"] <= _MAX):
                raise LibraryReplicaDenied("signed catalog item digest or size invalid")

    def sync_index(
        self, raw_signed_index: bytes, *, now: datetime | None = None,
        primary_epoch: int | None = None,
    ) -> VerifiedLibraryIndex:
        moment = self._now(now)
        self._require_primary(moment)
        current = self.state_store.current()
        floor = max(
            self.minimum_catalog_revision,
            0 if current is None or current.last_catalog_revision is None
            else current.last_catalog_revision,
        )
        try:
            index = verify_signed_library_index(
                raw_signed_index,
                trusted_publisher_public_key=self.trusted_publisher_public_key,
                expected_publisher_key_sha256=self.expected_publisher_key_sha256,
                expected_source_platform_id=self.primary_platform_id,
                expected_target_platform_id=self.replica_platform_id,
                expected_catalog_generation=self.expected_catalog_generation,
                minimum_catalog_revision=floor,
                now=moment,
                publisher_key_current=self._publisher_current,
            )
        except PermissionError:
            self.state_store.record_state(
                state="UNKNOWN", now=moment, error_code="SIGNED_INDEX_REJECTED",
            )
            raise
        if (index.source_platform_id != self.primary_platform_id
                or index.target_platform_id != self.replica_platform_id):
            raise LibraryReplicaDenied("signed index audience differs from replica")
        self._index_source_current(index, moment)
        self._index_items(index, moment)
        epoch = 1 if primary_epoch is None else _positive(
            primary_epoch, "primary epoch"
        )
        if current is not None and current.last_primary_epoch is not None:
            if primary_epoch is None:
                epoch = current.last_primary_epoch
        self.state_store.record_index(
            index=index, raw_signed_index=raw_signed_index,
            primary_epoch=epoch, now=moment,
        )
        return index

    def _current_index(
        self, now: datetime,
    ) -> tuple[LibraryReplicaState, VerifiedLibraryIndex]:
        current = self.state_store.current()
        if current is None or current.signed_index is None:
            self.state_store.record_state(
                state="UNKNOWN", now=now, error_code="NO_VERIFIED_INDEX",
            )
            raise LibraryReplicaDenied("no verified primary index is available")
        try:
            index = verify_signed_library_index(
                current.signed_index,
                trusted_publisher_public_key=self.trusted_publisher_public_key,
                expected_publisher_key_sha256=self.expected_publisher_key_sha256,
                expected_source_platform_id=self.primary_platform_id,
                expected_target_platform_id=self.replica_platform_id,
                expected_catalog_generation=self.expected_catalog_generation,
                minimum_catalog_revision=max(
                    self.minimum_catalog_revision,
                    0 if current.last_catalog_revision is None
                    else current.last_catalog_revision,
                ),
                now=now, publisher_key_current=self._publisher_current,
            )
            self._index_source_current(index, now)
            self._index_items(index, now)
        except PermissionError as exc:
            self.state_store.record_state(
                state="STALE", now=now, error_code="INDEX_NO_LONGER_CURRENT",
            )
            raise LibraryReplicaDenied(
                "verified primary index is no longer current"
            ) from exc
        return current, index

    def _verify_transfer(self, transfer: PinnedChunkTransfer) -> None:
        if not isinstance(transfer, PinnedChunkTransfer):
            raise LibraryReplicaDenied("typed pinned object transfer required")
        if (transfer.source_platform_id != self.primary_platform_id
                or transfer.target_platform_id != self.replica_platform_id):
            raise LibraryReplicaDenied("transfer source/target differs from replica binding")
        if (transfer.license_distribution != "permitted"
                or transfer.data_class != "public"):
            raise LibraryReplicaDenied(
                "license-blocked or protected object cannot replicate"
            )
        if self._source_allowed(transfer) is not True:
            raise LibraryReplicaDenied("signed source or license policy denied object")

    @staticmethod
    def _matching_item(
        index: VerifiedLibraryIndex, transfer: PinnedChunkTransfer,
    ) -> dict:
        matches = [
            row for row in index.catalog["items"]
            if row["content_digest"] == transfer.content_sha256
        ]
        if len(matches) != 1:
            raise LibraryReplicaDenied(
                "exact signed catalog object missing or ambiguous"
            )
        row = matches[0]
        if (transfer.catalog_revision != index.catalog_revision
                or row["manifest_digest"] != transfer.manifest_sha256
                or row["size_bytes"] != transfer.size_bytes
                or row["kind"] != transfer.artifact_kind
                or row["revision"] > index.catalog_revision
                or row["license_distribution"] != transfer.license_distribution
                or row["data_class"] != transfer.data_class
                or row["distribution_allowed"] is not True):
            raise LibraryReplicaDenied(
                "pinned transfer differs from exact signed catalog object"
            )
        return row

    def _authorizer(self, transfer: PinnedChunkTransfer, now: datetime):
        self._require_primary(now, record=False)
        _, index = self._current_index(now)
        self._matching_item(index, transfer)

        def current(candidate: PinnedChunkTransfer) -> bool:
            if candidate != transfer:
                raise LibraryReplicaDenied("transfer changed during replica read")
            current_moment = self._now(None)
            self._require_primary(current_moment, record=False)
            _, latest = self._current_index(current_moment)
            self._matching_item(latest, candidate)
            return True

        return current

    def append_chunk(
        self, transfer: PinnedChunkTransfer, *, offset: int, chunk: bytes,
        now: datetime | None = None,
    ) -> int:
        """Append one bounded chunk; duplicates/overlaps are rejected by cursor."""
        moment = self._now(now)
        self._verify_transfer(transfer)
        if type(chunk) is not bytes or not chunk:
            raise LibraryReplicaDenied("bounded replica chunk bytes required")
        authorize = self._authorizer(transfer, moment)
        return self.receiver.append_chunk(
            transfer, offset=offset, chunk=chunk,
            chunk_sha256=sha256(chunk).hexdigest(), authorize=authorize,
        )

    def sync_object(
        self, transfer: PinnedChunkTransfer, *, now: datetime | None = None,
        read_chunk: Callable[[int, int], bytes] | None = None,
        open_enrolled_tls: Callable[[], object] | None = None,
        expected_peer_certificate_sha256: str | None = None,
        authorize_peer: Callable | None = None,
        chunk_bytes: int = MAX_CHUNK, max_chunks: int = 128,
    ) -> ReplicaObjectResult:
        """Fetch exact CAS bytes, preserving durable resume on interruption."""
        moment = self._now(now)
        self._require_primary(moment)
        self._verify_transfer(transfer)
        if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= MAX_CHUNK:
            raise LibraryReplicaDenied("bounded replica chunk size required")
        if type(max_chunks) is not int or not 1 <= max_chunks <= 10000:
            raise LibraryReplicaDenied("bounded replica chunk budget required")
        self._current_index(moment)
        authorize = self._authorizer(transfer, moment)
        offset = self.receiver.received_bytes(transfer, authorize=authorize)
        try:
            if open_enrolled_tls is not None:
                if (type(expected_peer_certificate_sha256) is not str
                        or _SHA.fullmatch(expected_peer_certificate_sha256) is None
                        or not callable(authorize_peer)):
                    raise LibraryReplicaDenied(
                        "exact enrolled TLS peer and authorization required"
                    )
                offset = fetch_resumable_chunks(
                    transfer=transfer, receiver=self.receiver,
                    open_enrolled_tls=open_enrolled_tls,
                    expected_peer_certificate_sha256=expected_peer_certificate_sha256,
                    authorize_peer=authorize_peer,
                    publisher_current=lambda candidate: (
                        self._is_current(candidate, moment)
                    ),
                    chunk_bytes=chunk_bytes, max_chunks=max_chunks,
                    start_offset=offset,
                )
            else:
                if not callable(read_chunk):
                    raise LibraryReplicaDenied(
                        "authenticated primary chunk reader or enrolled TLS required"
                    )
                for _ in range(max_chunks):
                    if offset == transfer.size_bytes:
                        break
                    current_authorize = self._authorizer(transfer, moment)
                    length = min(chunk_bytes, transfer.size_bytes - offset)
                    data = read_chunk(offset, length)
                    if type(data) is not bytes or len(data) != length:
                        raise LibraryReplicaDenied(
                            "primary returned a non-bounded replica chunk"
                        )
                    offset = self.receiver.append_chunk(
                        transfer, offset=offset, chunk=data,
                        chunk_sha256=sha256(data).hexdigest(),
                        authorize=current_authorize,
                    )
        except (ConnectionError, TimeoutError, OSError):
            self.state_store.record_state(
                state="OFFLINE", now=moment, error_code="PRIMARY_TRANSFER_INTERRUPTED",
            )
            raise
        if offset == transfer.size_bytes:
            path = self.receiver.finalize(transfer, authorize=self._authorizer(
                transfer, moment,
            ))
            self.state_store.record_state(state="SYNCED", now=moment)
            return ReplicaObjectResult(
                content_sha256=transfer.content_sha256,
                size_bytes=transfer.size_bytes, offset=offset,
                complete=True, path=path,
            )
        self.state_store.record_state(
            state="SYNCING", now=moment, error_code="RESUME_REQUIRED",
        )
        return ReplicaObjectResult(
            content_sha256=transfer.content_sha256,
            size_bytes=transfer.size_bytes, offset=offset,
            complete=False, path=None,
        )

    def _is_current(self, transfer: PinnedChunkTransfer, now: datetime) -> bool:
        try:
            self._authorizer(transfer, now)
            return True
        except (PermissionError, ValueError, OSError, RuntimeError):
            return False

    def mark_disconnected(
        self, *, state: str = "OFFLINE", now: datetime | None = None,
        error_code: str = "PRIMARY_DISCONNECTED",
    ) -> dict[str, object]:
        if state not in {"OFFLINE", "STALE", "UNKNOWN"}:
            raise LibraryReplicaDenied("only truthful disconnected replica states allowed")
        moment = self._now(now)
        self.state_store.record_state(
            state=state, now=moment, error_code=error_code,
        )
        return self.status(now=moment)

    def status(self, *, now: datetime | None = None) -> dict[str, object]:
        return self.state_store.status(now=self._now(now))
