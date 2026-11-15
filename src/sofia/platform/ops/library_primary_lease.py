"""D028 single-primary logical Library role, epoch, revision and fence record.

This stores the one logical private Library's writer identity in the EXISTING
Platform-local SQLite state. It creates no second authority database, signer,
owner approval or network endpoint. A live primary epoch/lease denies any
second host claim. Expiry does not fail over automatically; promotion requires
an explicit current SAFE authorization callback and exact old-primary fence
evidence supplied by the caller.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re
import secrets
import sqlite3
from typing import Callable

from sofia.platform.state.local_store import PlatformLocalStore

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z0-9_]{1,64}\Z")
_MAX = 2**53 - 1
_ROLES = frozenset({"PRIMARY", "READ_REPLICA", "FENCED"})


class LibraryPrimaryDenied(PermissionError):
    """The logical Library has no current primary writer authority."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LibraryPrimaryDenied("trusted timezone-aware Library clock required")
    return value.astimezone(timezone.utc)


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise LibraryPrimaryDenied(f"bounded {label} required")
    return value


def _positive(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or not minimum <= value <= _MAX:
        raise LibraryPrimaryDenied(f"bounded {label} required")
    return value


def _token_text(value: object) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise LibraryPrimaryDenied("current 256-bit writer token required")
    return value


def _lease_seconds(value: object) -> int:
    if type(value) is not int or not 5 <= value <= 300:
        raise LibraryPrimaryDenied("bounded primary lease duration required")
    return value


@dataclass(frozen=True, slots=True)
class PrimaryFenceReceipt:
    """Exact old-primary fence evidence; never a new owner grant."""

    logical_library_id: str
    old_primary_host_id: str
    old_primary_platform_id: str
    old_primary_epoch: int
    old_writer_token_sha256: str
    fenced_at: datetime
    reason: str

    def __post_init__(self) -> None:
        _identifier(self.logical_library_id, "logical Library identity")
        _identifier(self.old_primary_host_id, "old primary host identity")
        _identifier(self.old_primary_platform_id, "old primary Platform identity")
        _positive(self.old_primary_epoch, "old primary epoch")
        if type(self.old_writer_token_sha256) is not str or _SHA.fullmatch(
            self.old_writer_token_sha256
        ) is None:
            raise LibraryPrimaryDenied("old writer token digest required")
        _utc(self.fenced_at)
        if type(self.reason) is not str or _REASON.fullmatch(self.reason) is None:
            raise LibraryPrimaryDenied("bounded fence reason required")

    @property
    def fingerprint(self) -> str:
        document = {
            "schema": "aegis.library.primary-fence-receipt.v1",
            "logical_library_id": self.logical_library_id,
            "old_primary_host_id": self.old_primary_host_id,
            "old_primary_platform_id": self.old_primary_platform_id,
            "old_primary_epoch": self.old_primary_epoch,
            "old_writer_token_sha256": self.old_writer_token_sha256,
            "fenced_at": self.fenced_at.astimezone(timezone.utc).isoformat(),
            "reason": self.reason,
        }
        return sha256(json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LibraryPrimaryRole:
    logical_library_id: str
    host_identity: str
    primary_platform_id: str
    primary_epoch: int
    catalog_revision: int
    writer_token_sha256: str
    lease_expires_at: datetime
    role: str
    read_only_replica: bool
    fenced_at: datetime | None
    fence_receipt_sha256: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.logical_library_id, "logical Library identity")
        _identifier(self.host_identity, "primary host identity")
        _identifier(self.primary_platform_id, "primary Platform identity")
        _positive(self.primary_epoch, "primary epoch")
        _positive(self.catalog_revision, "catalog revision")
        if type(self.writer_token_sha256) is not str or _SHA.fullmatch(
            self.writer_token_sha256
        ) is None:
            raise LibraryPrimaryDenied("writer token digest required")
        _utc(self.lease_expires_at)
        if type(self.role) is not str or self.role not in _ROLES:
            raise LibraryPrimaryDenied("unknown Library primary role")
        if type(self.read_only_replica) is not bool:
            raise LibraryPrimaryDenied("read-only replica flag required")
        if self.fenced_at is not None:
            _utc(self.fenced_at)
        if self.fence_receipt_sha256 is not None and (
            type(self.fence_receipt_sha256) is not str
            or _SHA.fullmatch(self.fence_receipt_sha256) is None
        ):
            raise LibraryPrimaryDenied("fence receipt digest invalid")
        _utc(self.updated_at)

    @property
    def is_primary(self) -> bool:
        return self.role == "PRIMARY" and not self.read_only_replica

    @property
    def is_fenced(self) -> bool:
        return self.role == "FENCED" or self.fenced_at is not None

    def lease_current(self, now: datetime) -> bool:
        moment = _utc(now)
        return self.is_primary and moment < self.lease_expires_at


class LibraryPrimaryLeaseStore:
    """One durable primary/fence record inside an existing local Platform DB."""

    def __init__(self, storage: PlatformLocalStore, *, logical_library_id: str) -> None:
        if not isinstance(storage, PlatformLocalStore):
            raise LibraryPrimaryDenied("existing Platform-local SQLite state required")
        self.storage = storage
        self.logical_library_id = _identifier(
            logical_library_id, "logical Library identity"
        )

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.execute("""
            CREATE TABLE IF NOT EXISTS platform_library_primary_role (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                logical_library_id TEXT NOT NULL,
                host_identity TEXT NOT NULL,
                primary_platform_id TEXT NOT NULL,
                primary_epoch INTEGER NOT NULL CHECK(primary_epoch>0),
                catalog_revision INTEGER NOT NULL CHECK(catalog_revision>0),
                writer_token_sha256 TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                role TEXT NOT NULL,
                read_only_replica INTEGER NOT NULL CHECK(read_only_replica IN (0,1)),
                fenced_at TEXT,
                fence_receipt_sha256 TEXT,
                updated_at TEXT NOT NULL
            )
        """)

    @staticmethod
    def _table_exists(db: sqlite3.Connection) -> bool:
        return db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='platform_library_primary_role'"
        ).fetchone() is not None

    @staticmethod
    def _decode(row: sqlite3.Row) -> LibraryPrimaryRole:
        try:
            return LibraryPrimaryRole(
                logical_library_id=row["logical_library_id"],
                host_identity=row["host_identity"],
                primary_platform_id=row["primary_platform_id"],
                primary_epoch=row["primary_epoch"],
                catalog_revision=row["catalog_revision"],
                writer_token_sha256=row["writer_token_sha256"],
                lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]),
                role=row["role"],
                read_only_replica=bool(row["read_only_replica"]),
                fenced_at=(
                    None if row["fenced_at"] is None
                    else datetime.fromisoformat(row["fenced_at"])
                ),
                fence_receipt_sha256=row["fence_receipt_sha256"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise LibraryPrimaryDenied("corrupt logical Library primary record") from exc

    def _read(self, db: sqlite3.Connection) -> LibraryPrimaryRole | None:
        if not self._table_exists(db):
            return None
        row = db.execute(
            "SELECT logical_library_id,host_identity,primary_platform_id,"
            "primary_epoch,catalog_revision,writer_token_sha256,lease_expires_at,"
            "role,read_only_replica,fenced_at,fence_receipt_sha256,updated_at "
            "FROM platform_library_primary_role WHERE singleton=1"
        ).fetchone()
        if row is None:
            return None
        record = self._decode(row)
        if record.logical_library_id != self.logical_library_id:
            raise LibraryPrimaryDenied("primary record belongs to another logical Library")
        return record

    def current(self) -> LibraryPrimaryRole | None:
        with closing(self.storage.connect()) as db:
            db.row_factory = sqlite3.Row
            return self._read(db)

    @staticmethod
    def _token_matches(record: LibraryPrimaryRole, writer_token: str) -> bool:
        return hmac.compare_digest(
            record.writer_token_sha256, sha256(writer_token.encode("ascii")).hexdigest()
        )

    @staticmethod
    def _verify_writer(
        record: LibraryPrimaryRole, *, host_identity: str, platform_id: str,
        epoch: int, writer_token: str, now: datetime,
    ) -> None:
        if record.is_fenced or record.role == "FENCED":
            raise LibraryPrimaryDenied("old primary epoch is fenced")
        if record.role != "PRIMARY" or record.read_only_replica:
            raise LibraryPrimaryDenied("logical Library is not a writable primary")
        if (record.host_identity != host_identity
                or record.primary_platform_id != platform_id):
            raise LibraryPrimaryDenied("writer identity differs from current primary")
        if record.primary_epoch != epoch:
            raise LibraryPrimaryDenied("stale, future or fenced primary epoch")
        if not LibraryPrimaryLeaseStore._token_matches(record, writer_token):
            raise LibraryPrimaryDenied("stale or invalid writer token")
        if now >= record.lease_expires_at:
            raise LibraryPrimaryDenied("primary lease expired; no automatic failover")

    def claim_primary(
        self, *, host_identity: str, platform_id: str, now: datetime,
        lease_seconds: int = 60, writer_token: str | None = None,
    ) -> tuple[LibraryPrimaryRole, str]:
        """Claim or renew the one writable primary; never auto-promote a peer."""
        host = _identifier(host_identity, "primary host identity")
        platform = _identifier(platform_id, "primary Platform identity")
        moment = _utc(now)
        ttl = _lease_seconds(lease_seconds)
        supplied = None if writer_token is None else _token_text(writer_token)
        expires = moment + timedelta(seconds=ttl)
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                self._create_schema(db)
                current = self._read(db)
                if current is None:
                    token = secrets.token_hex(32)
                    record = LibraryPrimaryRole(
                        logical_library_id=self.logical_library_id,
                        host_identity=host, primary_platform_id=platform,
                        primary_epoch=1, catalog_revision=1,
                        writer_token_sha256=sha256(token.encode("ascii")).hexdigest(),
                        lease_expires_at=expires, role="PRIMARY",
                        read_only_replica=False, fenced_at=None,
                        fence_receipt_sha256=None, updated_at=moment,
                    )
                    self._insert(db, record)
                    return record, token
                if current.is_fenced or current.role == "FENCED":
                    raise LibraryPrimaryDenied(
                        "fenced primary requires owner-approved promotion"
                    )
                if current.read_only_replica or current.role == "READ_REPLICA":
                    raise LibraryPrimaryDenied(
                        "read-only replica cannot claim primary write authority"
                    )
                same = (
                    current.host_identity == host
                    and current.primary_platform_id == platform
                )
                if not same:
                    if current.lease_current(moment):
                        raise LibraryPrimaryDenied(
                            "current primary epoch and lease deny dual-primary claim"
                        )
                    raise LibraryPrimaryDenied(
                        "expired primary lease requires owner-approved promotion "
                        "with exact old-primary fence evidence"
                    )
                if supplied is not None:
                    if not self._token_matches(current, supplied):
                        raise LibraryPrimaryDenied("stale or invalid writer token")
                    token = supplied
                    epoch = current.primary_epoch
                    revision = current.catalog_revision
                else:
                    if current.lease_current(moment):
                        raise LibraryPrimaryDenied(
                            "current writer token required to renew primary lease"
                        )
                    token = secrets.token_hex(32)
                    epoch = current.primary_epoch + 1
                    revision = current.catalog_revision
                record = LibraryPrimaryRole(
                    logical_library_id=self.logical_library_id,
                    host_identity=host, primary_platform_id=platform,
                    primary_epoch=epoch, catalog_revision=revision,
                    writer_token_sha256=sha256(token.encode("ascii")).hexdigest(),
                    lease_expires_at=expires, role="PRIMARY",
                    read_only_replica=False, fenced_at=None,
                    fence_receipt_sha256=None, updated_at=moment,
                )
                self._update(db, record)
                return record, token

    def mark_read_only_replica(
        self, *, host_identity: str, platform_id: str,
        primary_platform_id: str, primary_epoch: int,
        catalog_revision: int, now: datetime, lease_seconds: int = 60,
    ) -> LibraryPrimaryRole:
        """Record this installed Platform as a read-only replica of one primary.

        A replica record can never claim primary write authority, advance the
        catalog revision or be fenced as a writer. It only tracks the current
        signed primary epoch/revision for stale-epoch refusal. It never
        overwrites a live writer, durable fence evidence or another primary.
        """
        host = _identifier(host_identity, "replica host identity")
        platform = _identifier(platform_id, "replica Platform identity")
        primary = _identifier(primary_platform_id, "primary Platform identity")
        if platform == primary:
            raise LibraryPrimaryDenied("replica must differ from its primary")
        epoch = _positive(primary_epoch, "primary epoch")
        revision = _positive(catalog_revision, "catalog revision")
        moment = _utc(now)
        ttl = _lease_seconds(lease_seconds)
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                self._create_schema(db)
                current = self._read(db)
                if current is not None:
                    if current.role == "PRIMARY" or current.is_primary:
                        raise LibraryPrimaryDenied(
                            "a current writable primary cannot be reclassified as replica"
                        )
                    if current.is_fenced or current.role == "FENCED":
                        raise LibraryPrimaryDenied(
                            "fenced primary evidence cannot be replaced by a replica record"
                        )
                    if (current.role != "READ_REPLICA"
                            or not current.read_only_replica):
                        raise LibraryPrimaryDenied(
                            "unknown local Library role cannot become a replica"
                        )
                    if current.host_identity != host:
                        raise LibraryPrimaryDenied(
                            "local replica host identity changed without owner rotation"
                        )
                    if current.primary_platform_id != primary:
                        raise LibraryPrimaryDenied(
                            "replica primary identity change requires owner rotation"
                        )
                    if epoch < current.primary_epoch:
                        raise LibraryPrimaryDenied("primary epoch rollback denied")
                    if revision < current.catalog_revision:
                        raise LibraryPrimaryDenied("catalog revision rollback denied")
                # The local token never authorizes a write: _verify_writer and
                # claim_primary both deny READ_REPLICA before any token check.
                local_token = secrets.token_hex(32)
                record = LibraryPrimaryRole(
                    logical_library_id=self.logical_library_id,
                    host_identity=host, primary_platform_id=primary,
                    primary_epoch=epoch, catalog_revision=revision,
                    writer_token_sha256=sha256(
                        local_token.encode("ascii")
                    ).hexdigest(),
                    lease_expires_at=moment + timedelta(seconds=ttl),
                    role="READ_REPLICA", read_only_replica=True,
                    fenced_at=None, fence_receipt_sha256=None,
                    updated_at=moment,
                )
                if current is None:
                    self._insert(db, record)
                else:
                    self._update(db, record)
                result = self._read(db)
                if result is None or not result.read_only_replica:
                    raise LibraryPrimaryDenied(
                        "read-only replica role commit was not durable"
                    )
                return result

    def require_writer(
        self, *, host_identity: str, platform_id: str, epoch: int,
        writer_token: str, now: datetime,
    ) -> LibraryPrimaryRole:
        host = _identifier(host_identity, "primary host identity")
        platform = _identifier(platform_id, "primary Platform identity")
        moment = _utc(now)
        selected_epoch = _positive(epoch, "primary epoch")
        token = _token_text(writer_token)
        record = self.current()
        if record is None:
            raise LibraryPrimaryDenied("logical Library primary is not initialized")
        self._verify_writer(
            record, host_identity=host, platform_id=platform,
            epoch=selected_epoch, writer_token=token, now=moment,
        )
        return record

    def advance_catalog_revision(
        self, *, host_identity: str, platform_id: str, epoch: int,
        writer_token: str, expected_revision: int, now: datetime,
    ) -> int:
        """Monotonic signed-index mutation by the current unfenced writer only."""
        host = _identifier(host_identity, "primary host identity")
        platform = _identifier(platform_id, "primary Platform identity")
        moment = _utc(now)
        selected_epoch = _positive(epoch, "primary epoch")
        expected = _positive(expected_revision, "catalog revision")
        token = _token_text(writer_token)
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                current = self._read(db)
                if current is None:
                    raise LibraryPrimaryDenied("logical Library primary is not initialized")
                self._verify_writer(
                    current, host_identity=host, platform_id=platform,
                    epoch=selected_epoch, writer_token=token, now=moment,
                )
                if current.catalog_revision != expected:
                    raise LibraryPrimaryDenied("catalog revision changed or is stale")
                revision = current.catalog_revision + 1
                db.execute(
                    "UPDATE platform_library_primary_role SET catalog_revision=?,"
                    "updated_at=? WHERE singleton=1 AND primary_epoch=? "
                    "AND writer_token_sha256=? AND catalog_revision=? "
                    "AND role='PRIMARY' AND fenced_at IS NULL",
                    (
                        revision, moment.isoformat(), current.primary_epoch,
                        current.writer_token_sha256, expected,
                    ),
                )
                if db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise LibraryPrimaryDenied("primary writer changed during revision advance")
                return revision

    def fence_primary(
        self, *, host_identity: str, platform_id: str, epoch: int,
        writer_token: str, now: datetime,
        reason: str = "OWNER_VERIFIED_OLD_PRIMARY_FENCED",
    ) -> PrimaryFenceReceipt:
        """Fence the exact old primary epoch and return durable evidence."""
        host = _identifier(host_identity, "old primary host identity")
        platform = _identifier(platform_id, "old primary Platform identity")
        moment = _utc(now)
        selected_epoch = _positive(epoch, "old primary epoch")
        token = _token_text(writer_token)
        if type(reason) is not str or _REASON.fullmatch(reason) is None:
            raise LibraryPrimaryDenied("bounded fence reason required")
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                current = self._read(db)
                if current is None:
                    raise LibraryPrimaryDenied("logical Library primary is not initialized")
                if current.role != "PRIMARY" or current.read_only_replica:
                    raise LibraryPrimaryDenied("only the current writable primary can be fenced")
                if (current.host_identity != host
                        or current.primary_platform_id != platform):
                    raise LibraryPrimaryDenied("fence identity differs from current primary")
                if current.primary_epoch != selected_epoch:
                    raise LibraryPrimaryDenied("fence epoch differs from current primary")
                if not self._token_matches(current, token):
                    raise LibraryPrimaryDenied("fence requires the exact current writer token")
                receipt = PrimaryFenceReceipt(
                    logical_library_id=self.logical_library_id,
                    old_primary_host_id=current.host_identity,
                    old_primary_platform_id=current.primary_platform_id,
                    old_primary_epoch=current.primary_epoch,
                    old_writer_token_sha256=current.writer_token_sha256,
                    fenced_at=moment, reason=reason,
                )
                db.execute(
                    "UPDATE platform_library_primary_role SET role='FENCED',"
                    "fenced_at=?,fence_receipt_sha256=?,updated_at=? "
                    "WHERE singleton=1 AND primary_epoch=? "
                    "AND writer_token_sha256=? AND role='PRIMARY' "
                    "AND read_only_replica=0",
                    (
                        moment.isoformat(), receipt.fingerprint,
                        moment.isoformat(), current.primary_epoch,
                        current.writer_token_sha256,
                    ),
                )
                if db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise LibraryPrimaryDenied("primary changed during fencing")
                return receipt

    def promote_read_only_replica(
        self, *, new_primary_host_id: str, new_primary_platform_id: str,
        expected_old_epoch: int, old_primary_fence_receipt: PrimaryFenceReceipt,
        safe_authorization: Callable[[], bool], now: datetime,
        lease_seconds: int = 60,
    ) -> tuple[LibraryPrimaryRole, str]:
        """Owner-approved manual promotion only after exact old-primary fencing."""
        host = _identifier(new_primary_host_id, "promoted primary host identity")
        platform = _identifier(new_primary_platform_id, "promoted primary Platform identity")
        old_epoch = _positive(expected_old_epoch, "old primary epoch")
        moment = _utc(now)
        ttl = _lease_seconds(lease_seconds)
        if not callable(safe_authorization) or safe_authorization() is not True:
            raise LibraryPrimaryDenied(
                "current authenticated owner SAFE authorization required for promotion"
            )
        if not isinstance(old_primary_fence_receipt, PrimaryFenceReceipt):
            raise LibraryPrimaryDenied("exact old-primary fence receipt required")
        receipt = old_primary_fence_receipt
        if receipt.logical_library_id != self.logical_library_id:
            raise LibraryPrimaryDenied("fence receipt belongs to another logical Library")
        if receipt.old_primary_epoch != old_epoch:
            raise LibraryPrimaryDenied("fence receipt epoch differs from expected old epoch")
        with closing(self.storage.connect()) as db:
            with db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                current = self._read(db)
                if current is None:
                    raise LibraryPrimaryDenied("logical Library primary is not initialized")
                if (current.role != "FENCED" or current.fenced_at is None
                        or current.fence_receipt_sha256 is None
                        or not current.is_fenced):
                    raise LibraryPrimaryDenied(
                        "old primary has no durable fence evidence"
                    )
                if current.primary_epoch != old_epoch:
                    raise LibraryPrimaryDenied("old primary epoch changed before promotion")
                if (receipt.old_primary_host_id != current.host_identity
                        or receipt.old_primary_platform_id
                        != current.primary_platform_id
                        or receipt.old_writer_token_sha256
                        != current.writer_token_sha256
                        or receipt.fenced_at.astimezone(timezone.utc)
                        != current.fenced_at.astimezone(timezone.utc)
                        or receipt.fingerprint != current.fence_receipt_sha256):
                    raise LibraryPrimaryDenied(
                        "old-primary fence receipt differs from durable fence evidence"
                    )
                if (host == current.host_identity
                        and platform == current.primary_platform_id):
                    raise LibraryPrimaryDenied(
                        "promotion requires a distinct read-only replica host"
                    )
                if safe_authorization() is not True:
                    raise LibraryPrimaryDenied(
                        "owner SAFE authorization revoked during promotion"
                    )
                token = secrets.token_hex(32)
                record = LibraryPrimaryRole(
                    logical_library_id=self.logical_library_id,
                    host_identity=host, primary_platform_id=platform,
                    primary_epoch=current.primary_epoch + 1,
                    catalog_revision=current.catalog_revision + 1,
                    writer_token_sha256=sha256(token.encode("ascii")).hexdigest(),
                    lease_expires_at=moment + timedelta(seconds=ttl),
                    role="PRIMARY", read_only_replica=False,
                    fenced_at=None, fence_receipt_sha256=None,
                    updated_at=moment,
                )
                self._update(db, record)
                return record, token

    def status(self, *, now: datetime) -> dict[str, object]:
        """Redacted read-only status; never includes the writer token."""
        moment = _utc(now)
        record = self.current()
        base = {
            "schema": "aegis.library.primary-status.v1",
            "logical_library_id": self.logical_library_id,
            "owner_mode": "SINGLE_OWNER_PRIVATE",
            "read_only": False,
            "install_executed": False,
            "core_activated": False,
        }
        if record is None:
            return {**base, "state": "UNINITIALIZED", "role": None,
                    "primary_host_id": None, "primary_platform_id": None,
                    "primary_epoch": None, "catalog_revision": None,
                    "lease_expires_at": None, "lease_current": False,
                    "fenced": False}
        if record.is_fenced or record.role == "FENCED":
            state = "FENCED"
        elif record.read_only_replica or record.role == "READ_REPLICA":
            state = "READ_REPLICA"
        elif record.lease_current(moment):
            state = "PRIMARY"
        else:
            state = "STALE"
        return {
            **base,
            "state": state,
            "role": record.role,
            "read_only": record.read_only_replica,
            "primary_host_id": record.host_identity,
            "primary_platform_id": record.primary_platform_id,
            "primary_epoch": record.primary_epoch,
            "catalog_revision": record.catalog_revision,
            "lease_expires_at": record.lease_expires_at.isoformat(),
            "lease_current": record.lease_current(moment),
            "fenced": record.is_fenced,
        }

    @staticmethod
    def _insert(db: sqlite3.Connection, record: LibraryPrimaryRole) -> None:
        db.execute("""
            INSERT INTO platform_library_primary_role (
                singleton,logical_library_id,host_identity,primary_platform_id,
                primary_epoch,catalog_revision,writer_token_sha256,
                lease_expires_at,role,read_only_replica,fenced_at,
                fence_receipt_sha256,updated_at
            ) VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record.logical_library_id, record.host_identity,
            record.primary_platform_id, record.primary_epoch,
            record.catalog_revision, record.writer_token_sha256,
            record.lease_expires_at.isoformat(), record.role,
            int(record.read_only_replica),
            None if record.fenced_at is None else record.fenced_at.isoformat(),
            record.fence_receipt_sha256, record.updated_at.isoformat(),
        ))

    @staticmethod
    def _update(db: sqlite3.Connection, record: LibraryPrimaryRole) -> None:
        db.execute("""
            UPDATE platform_library_primary_role SET
                logical_library_id=?,host_identity=?,primary_platform_id=?,
                primary_epoch=?,catalog_revision=?,writer_token_sha256=?,
                lease_expires_at=?,role=?,read_only_replica=?,fenced_at=?,
                fence_receipt_sha256=?,updated_at=?
            WHERE singleton=1
        """, (
            record.logical_library_id, record.host_identity,
            record.primary_platform_id, record.primary_epoch,
            record.catalog_revision, record.writer_token_sha256,
            record.lease_expires_at.isoformat(), record.role,
            int(record.read_only_replica),
            None if record.fenced_at is None else record.fenced_at.isoformat(),
            record.fence_receipt_sha256, record.updated_at.isoformat(),
        ))
