"""Fenced synchronous replication for the logical Sofía State Plane.

This module deliberately does not claim to replicate every legacy/direct SQLite
table. It protects StatePlane records. The witness is control-plane state and
must live in an independent failure domain for real cross-host fencing.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping
from uuid import uuid4

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane, StatePlaneConflictError

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


@dataclass(frozen=True, slots=True)
class WriterLease:
    owner_id: str
    epoch: int
    acquired_at: datetime
    renewed_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ReplicationTargetHealth:
    target_id: str
    last_acked_sequence: int
    pending_operations: int
    is_primary: bool


@dataclass(frozen=True, slots=True)
class ReplicationHealth:
    writer: WriterLease | None
    primary_target_id: str
    latest_sequence: int
    committed_sequence: int
    pending_operations: int
    targets: tuple[ReplicationTargetHealth, ...]


class ReplicationError(RuntimeError):
    pass


class WriterLeaseHeldError(ReplicationError):
    pass


class StaleWriterError(ReplicationError):
    pass


class ReplicationPartialCommitError(ReplicationError):
    pass


class ReplicaDivergenceError(ReplicationError):
    pass


class SQLiteReplicationWitness:
    """Independent durable writer fence and replication operation journal."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS replication_writer (
                    scope TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL CHECK(epoch > 0),
                    acquired_at TEXT NOT NULL,
                    renewed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS replication_control (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS replication_target (
                    target_id TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS replication_operation (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL UNIQUE,
                    writer_id TEXT NOT NULL,
                    writer_epoch INTEGER NOT NULL,
                    operation_kind TEXT NOT NULL CHECK(operation_kind IN ('write','delete')),
                    namespace TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    expected_revision INTEGER,
                    record_payload TEXT,
                    created_at TEXT NOT NULL,
                    committed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS replication_ack (
                    sequence INTEGER NOT NULL,
                    target_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ok','failed')),
                    acked_at TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    PRIMARY KEY(sequence, target_id),
                    FOREIGN KEY(sequence) REFERENCES replication_operation(sequence)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _ttl(ttl_seconds: int) -> int:
        if type(ttl_seconds) is not int or not 5 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be an integer in 5..300")
        return ttl_seconds

    @staticmethod
    def _lease(row: sqlite3.Row) -> WriterLease:
        return WriterLease(
            owner_id=row["owner_id"],
            epoch=int(row["epoch"]),
            acquired_at=datetime.fromisoformat(row["acquired_at"]),
            renewed_at=datetime.fromisoformat(row["renewed_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
        )

    def acquire_writer(
        self,
        owner_id: str,
        *,
        now: datetime,
        ttl_seconds: int = 30,
    ) -> WriterLease:
        owner = _identifier(owner_id, "owner_id")
        moment = _utc(now)
        expires = moment + timedelta(seconds=self._ttl(ttl_seconds))
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            if row is None:
                lease = WriterLease(owner, 1, moment, moment, expires)
                db.execute(
                    "INSERT INTO replication_writer VALUES ('state-plane',?,?,?,?,?)",
                    (
                        lease.owner_id,
                        lease.epoch,
                        lease.acquired_at.isoformat(),
                        lease.renewed_at.isoformat(),
                        lease.expires_at.isoformat(),
                    ),
                )
                return lease

            current = self._lease(row)
            if moment < current.expires_at:
                raise WriterLeaseHeldError(
                    f"writer lease held by {current.owner_id} epoch {current.epoch}"
                )

            epoch = current.epoch + 1
            lease = WriterLease(owner, epoch, moment, moment, expires)
            db.execute(
                "UPDATE replication_writer SET owner_id=?, epoch=?, acquired_at=?, "
                "renewed_at=?, expires_at=? WHERE scope='state-plane'",
                (
                    lease.owner_id,
                    lease.epoch,
                    lease.acquired_at.isoformat(),
                    lease.renewed_at.isoformat(),
                    lease.expires_at.isoformat(),
                ),
            )
            return lease

    def renew_writer(
        self,
        lease: WriterLease,
        *,
        now: datetime,
        ttl_seconds: int = 30,
    ) -> WriterLease:
        if not isinstance(lease, WriterLease):
            raise TypeError("lease must be WriterLease")
        moment = _utc(now)
        expires = moment + timedelta(seconds=self._ttl(ttl_seconds))
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            if row is None:
                raise StaleWriterError("writer lease no longer exists")
            current = self._lease(row)
            if current.owner_id != lease.owner_id or current.epoch != lease.epoch:
                raise StaleWriterError(
                    f"writer fenced by {current.owner_id} epoch {current.epoch}"
                )
            if moment >= current.expires_at:
                raise StaleWriterError(
                    "writer lease expired; reacquire a new writer epoch"
                )
            renewed = WriterLease(
                current.owner_id,
                current.epoch,
                current.acquired_at,
                moment,
                expires,
            )
            db.execute(
                "UPDATE replication_writer SET renewed_at=?, expires_at=? "
                "WHERE scope='state-plane' AND owner_id=? AND epoch=?",
                (
                    renewed.renewed_at.isoformat(),
                    renewed.expires_at.isoformat(),
                    renewed.owner_id,
                    renewed.epoch,
                ),
            )
            return renewed

    def current_writer(self) -> WriterLease | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
        return None if row is None else self._lease(row)

    @classmethod
    def _assert_writer_row(
        cls,
        row: sqlite3.Row | None,
        lease: WriterLease,
        *,
        now: datetime,
        action: str,
    ) -> WriterLease:
        if not isinstance(lease, WriterLease):
            raise TypeError("lease must be WriterLease")
        moment = _utc(now)
        if row is None:
            raise StaleWriterError(f"writer lease missing before {action}")
        current = cls._lease(row)
        if current.owner_id != lease.owner_id or current.epoch != lease.epoch:
            raise StaleWriterError(
                f"writer fenced by {current.owner_id} epoch {current.epoch} "
                f"before {action}"
            )
        if moment >= current.expires_at:
            raise StaleWriterError(
                f"writer lease expired before {action}; reacquire a new epoch"
            )
        return current

    def assert_writer_active(
        self,
        lease: WriterLease,
        *,
        now: datetime,
        action: str = "operation",
    ) -> WriterLease:
        moment = _utc(now)
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
        return self._assert_writer_row(
            row,
            lease,
            now=moment,
            action=action,
        )

    def register_targets(
        self,
        target_ids: tuple[str, ...],
        *,
        primary_target_id: str,
        now: datetime,
    ) -> None:
        if not target_ids or len(set(target_ids)) != len(target_ids):
            raise ValueError("target_ids must be unique and nonempty")
        primary = _identifier(primary_target_id, "primary_target_id")
        if primary not in target_ids:
            raise ValueError("primary target must be registered")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = {
                row["target_id"]
                for row in db.execute("SELECT target_id FROM replication_target")
            }
            desired = set(target_ids)
            if existing and existing != desired:
                raise ReplicationError(
                    "replication target membership change requires explicit migration"
                )
            for target_id in target_ids:
                _identifier(target_id, "target_id")
                db.execute(
                    "INSERT OR IGNORE INTO replication_target(target_id, registered_at) "
                    "VALUES (?,?)",
                    (target_id, moment.isoformat()),
                )
            row = db.execute(
                "SELECT value FROM replication_control WHERE key='primary_target_id'"
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO replication_control(key,value) VALUES ('primary_target_id',?)",
                    (primary,),
                )
            elif row["value"] not in desired:
                raise ReplicationError("witness primary target is not registered")

    def primary_target_id(self) -> str:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT value FROM replication_control WHERE key='primary_target_id'"
            ).fetchone()
        if row is None:
            raise ReplicationError("primary target is not configured")
        return str(row["value"])

    @staticmethod
    def _key_fields(key: StateKey) -> tuple[str, str, str, str]:
        return (key.namespace, key.key, key.principal_id or "", key.audience or "")

    @staticmethod
    def _encode_record(record: StateRecord) -> str:
        return json.dumps(
            {
                "state_class": record.state_class.value,
                "revision": record.revision,
                "value_hex": record.value.hex(),
                "updated_at": record.updated_at.isoformat(),
                "source": record.source,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _decode_record(row: sqlite3.Row) -> StateRecord | None:
        raw = row["record_payload"]
        if raw is None:
            return None
        payload = json.loads(raw)
        return StateRecord(
            key=StateKey(
                namespace=row["namespace"],
                key=row["record_key"],
                principal_id=row["principal_id"] or None,
                audience=row["audience"] or None,
            ),
            state_class=StateClass(payload["state_class"]),
            revision=int(payload["revision"]),
            value=bytes.fromhex(payload["value_hex"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            source=payload["source"],
        )

    def pending_sequences(self) -> tuple[int, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT sequence FROM replication_operation "
                "WHERE committed_at IS NULL ORDER BY sequence"
            ).fetchall()
        return tuple(int(row["sequence"]) for row in rows)

    def prepare(
        self,
        *,
        lease: WriterLease,
        operation_kind: str,
        key: StateKey,
        expected_revision: int | None,
        record: StateRecord | None,
        now: datetime,
    ) -> int:
        if operation_kind not in {"write", "delete"}:
            raise ValueError("unsupported replication operation")
        if not isinstance(key, StateKey):
            raise TypeError("key must be StateKey")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            writer_row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            self._assert_writer_row(
                writer_row,
                lease,
                now=moment,
                action="prepare",
            )
            pending = db.execute(
                "SELECT sequence FROM replication_operation "
                "WHERE committed_at IS NULL ORDER BY sequence LIMIT 1"
            ).fetchone()
            if pending is not None:
                raise ReplicationPartialCommitError(
                    f"pending replication operation {pending['sequence']} requires repair"
                )
            fields = self._key_fields(key)
            cursor = db.execute(
                """
                INSERT INTO replication_operation(
                    operation_id, writer_id, writer_epoch, operation_kind,
                    namespace, record_key, principal_id, audience,
                    expected_revision, record_payload, created_at, committed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)
                """,
                (
                    str(uuid4()),
                    lease.owner_id,
                    lease.epoch,
                    operation_kind,
                    *fields,
                    expected_revision,
                    None if record is None else self._encode_record(record),
                    moment.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def operation(self, sequence: int) -> tuple[str, StateKey, int | None, StateRecord | None]:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM replication_operation WHERE sequence=?",
                (sequence,),
            ).fetchone()
        if row is None:
            raise KeyError(sequence)
        return (
            row["operation_kind"],
            StateKey(
                row["namespace"],
                row["record_key"],
                row["principal_id"] or None,
                row["audience"] or None,
            ),
            None if row["expected_revision"] is None else int(row["expected_revision"]),
            self._decode_record(row),
        )

    def ack(
        self,
        sequence: int,
        target_id: str,
        *,
        lease: WriterLease,
        ok: bool,
        now: datetime,
        detail: str = "",
    ) -> None:
        target = _identifier(target_id, "target_id")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            writer_row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            self._assert_writer_row(
                writer_row,
                lease,
                now=moment,
                action=f"ack sequence {sequence}",
            )
            db.execute(
                """
                INSERT INTO replication_ack(sequence,target_id,status,acked_at,detail)
                VALUES (?,?,?,?,?)
                ON CONFLICT(sequence,target_id) DO UPDATE SET
                    status=excluded.status,
                    acked_at=excluded.acked_at,
                    detail=excluded.detail
                """,
                (
                    sequence,
                    target,
                    "ok" if ok else "failed",
                    moment.isoformat(),
                    detail[:500],
                ),
            )

    def successful_targets(self, sequence: int) -> frozenset[str]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT target_id FROM replication_ack "
                "WHERE sequence=? AND status='ok'",
                (sequence,),
            ).fetchall()
        return frozenset(str(row["target_id"]) for row in rows)

    def commit_if_complete(
        self,
        sequence: int,
        *,
        lease: WriterLease,
        target_ids: tuple[str, ...],
        now: datetime,
    ) -> bool:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            writer_row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            self._assert_writer_row(
                writer_row,
                lease,
                now=moment,
                action=f"commit sequence {sequence}",
            )
            rows = db.execute(
                "SELECT target_id FROM replication_ack "
                "WHERE sequence=? AND status='ok'",
                (sequence,),
            ).fetchall()
            if {str(row["target_id"]) for row in rows} != set(target_ids):
                return False
            db.execute(
                "UPDATE replication_operation SET committed_at=? "
                "WHERE sequence=? AND committed_at IS NULL",
                (moment.isoformat(), sequence),
            )
        return True

    def promote(
        self,
        target_id: str,
        *,
        lease: WriterLease,
        now: datetime,
    ) -> None:
        target = _identifier(target_id, "target_id")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            writer_row = db.execute(
                "SELECT owner_id, epoch, acquired_at, renewed_at, expires_at "
                "FROM replication_writer WHERE scope='state-plane'"
            ).fetchone()
            self._assert_writer_row(
                writer_row,
                lease,
                now=moment,
                action="promotion",
            )
            pending = db.execute(
                "SELECT 1 FROM replication_operation WHERE committed_at IS NULL LIMIT 1"
            ).fetchone()
            if pending is not None:
                raise ReplicationPartialCommitError(
                    "cannot promote while replication is incomplete"
                )
            known = db.execute(
                "SELECT 1 FROM replication_target WHERE target_id=?",
                (target,),
            ).fetchone()
            if known is None:
                raise KeyError(target)
            latest = db.execute(
                "SELECT COALESCE(MAX(sequence),0) AS n FROM replication_operation "
                "WHERE committed_at IS NOT NULL"
            ).fetchone()["n"]
            if latest:
                ack = db.execute(
                    "SELECT status FROM replication_ack WHERE sequence=? AND target_id=?",
                    (latest, target),
                ).fetchone()
                if ack is None or ack["status"] != "ok":
                    raise ReplicationError("promotion target is not caught up")
            db.execute(
                "UPDATE replication_control SET value=? WHERE key='primary_target_id'",
                (target,),
            )
            db.execute(
                "INSERT INTO replication_control(key,value) VALUES ('last_promotion_at',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (moment.isoformat(),),
            )

    def health(self) -> ReplicationHealth:
        with closing(self._connect()) as db:
            latest = int(
                db.execute(
                    "SELECT COALESCE(MAX(sequence),0) AS n FROM replication_operation"
                ).fetchone()["n"]
            )
            committed = int(
                db.execute(
                    "SELECT COALESCE(MAX(sequence),0) AS n FROM replication_operation "
                    "WHERE committed_at IS NOT NULL"
                ).fetchone()["n"]
            )
            pending = int(
                db.execute(
                    "SELECT COUNT(*) AS n FROM replication_operation "
                    "WHERE committed_at IS NULL"
                ).fetchone()["n"]
            )
            target_rows = db.execute(
                "SELECT target_id FROM replication_target ORDER BY target_id"
            ).fetchall()
            primary = self.primary_target_id()
            targets = []
            for row in target_rows:
                target_id = str(row["target_id"])
                last_ack = int(
                    db.execute(
                        "SELECT COALESCE(MAX(sequence),0) AS n FROM replication_ack "
                        "WHERE target_id=? AND status='ok'",
                        (target_id,),
                    ).fetchone()["n"]
                )
                target_pending = int(
                    db.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM replication_operation o
                        LEFT JOIN replication_ack a
                          ON a.sequence=o.sequence AND a.target_id=?
                        WHERE o.committed_at IS NULL
                          AND (a.status IS NULL OR a.status!='ok')
                        """,
                        (target_id,),
                    ).fetchone()["n"]
                )
                targets.append(
                    ReplicationTargetHealth(
                        target_id,
                        last_ack,
                        target_pending,
                        target_id == primary,
                    )
                )
        return ReplicationHealth(
            writer=self.current_writer(),
            primary_target_id=primary,
            latest_sequence=latest,
            committed_sequence=committed,
            pending_operations=pending,
            targets=tuple(targets),
        )


class ReplicatedStatePlane(StatePlane):
    """One-writer synchronous StatePlane mirror with durable repair journal."""

    def __init__(
        self,
        targets: Mapping[str, StatePlane],
        *,
        witness: SQLiteReplicationWitness,
        writer_id: str,
        primary_target_id: str,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> None:
        if not isinstance(witness, SQLiteReplicationWitness):
            raise TypeError("witness must be SQLiteReplicationWitness")
        if len(targets) < 2:
            raise ValueError("replicated State Plane requires at least two data targets")
        self._targets = dict(targets)
        if any(not isinstance(value, StatePlane) for value in self._targets.values()):
            raise TypeError("all replication targets must implement StatePlane")
        self._target_ids = tuple(sorted(self._targets))
        self._witness = witness
        self._ttl_seconds = ttl_seconds
        moment = _utc(now or datetime.now(timezone.utc))
        self._witness.register_targets(
            self._target_ids,
            primary_target_id=primary_target_id,
            now=moment,
        )
        self._lease = witness.acquire_writer(
            _identifier(writer_id, "writer_id"),
            now=moment,
            ttl_seconds=ttl_seconds,
        )

    @property
    def schema_revision(self) -> int:
        revisions = {
            getattr(target, "schema_revision", None)
            for target in self._targets.values()
        }
        if len(revisions) != 1 or None in revisions:
            raise ReplicationError("replication targets do not share one schema revision")
        return int(next(iter(revisions)))

    @property
    def writer_lease(self) -> WriterLease:
        return self._lease

    def _renew(self) -> None:
        self._lease = self._witness.renew_writer(
            self._lease,
            now=datetime.now(timezone.utc),
            ttl_seconds=self._ttl_seconds,
        )

    def _primary(self) -> StatePlane:
        target_id = self._witness.primary_target_id()
        try:
            return self._targets[target_id]
        except KeyError as exc:
            raise ReplicationError("witness primary target is unavailable") from exc

    @staticmethod
    def _same_record(left: StateRecord | None, right: StateRecord | None) -> bool:
        return left == right

    def _apply(
        self,
        target: StatePlane,
        *,
        kind: str,
        key: StateKey,
        expected_revision: int | None,
        record: StateRecord | None,
    ) -> None:
        current = target.read(key)
        if kind == "write":
            if record is None:
                raise ReplicationError("write operation lacks record payload")
            if self._same_record(current, record):
                return
            if expected_revision is None:
                if current is not None:
                    raise ReplicaDivergenceError(
                        "replica contains unexpected existing state"
                    )
            elif current is None or current.revision != expected_revision:
                raise ReplicaDivergenceError(
                    "replica revision differs from expected revision"
                )
            target.write(record, expected_revision=expected_revision)
            return

        if current is None:
            return
        if expected_revision is None or current.revision != expected_revision:
            raise ReplicaDivergenceError(
                "replica delete revision differs from expected revision"
            )
        target.delete(key, expected_revision=expected_revision)

    def _replicate_sequence(self, sequence: int) -> None:
        kind, key, expected, record = self._witness.operation(sequence)
        successful = set(self._witness.successful_targets(sequence))
        failures: list[str] = []
        for target_id in self._target_ids:
            if target_id in successful:
                continue
            self._witness.assert_writer_active(
                self._lease,
                now=datetime.now(timezone.utc),
                action=f"replicate to {target_id}",
            )
            try:
                self._apply(
                    self._targets[target_id],
                    kind=kind,
                    key=key,
                    expected_revision=expected,
                    record=record,
                )
            except Exception as exc:
                self._witness.ack(
                    sequence,
                    target_id,
                    lease=self._lease,
                    ok=False,
                    now=datetime.now(timezone.utc),
                    detail=f"{type(exc).__name__}: {exc}",
                )
                failures.append(f"{target_id}: {type(exc).__name__}: {exc}")
            else:
                self._witness.ack(
                    sequence,
                    target_id,
                    lease=self._lease,
                    ok=True,
                    now=datetime.now(timezone.utc),
                )
        if not self._witness.commit_if_complete(
            sequence,
            lease=self._lease,
            target_ids=self._target_ids,
            now=datetime.now(timezone.utc),
        ):
            raise ReplicationPartialCommitError(
                "replication incomplete: " + "; ".join(failures or ["unknown target failure"])
            )

    def repair_pending(self) -> int:
        self._renew()
        repaired = 0
        for sequence in self._witness.pending_sequences():
            self._replicate_sequence(sequence)
            repaired += 1
        return repaired

    def promote(self, target_id: str) -> None:
        self._renew()
        self.repair_pending()
        self._witness.promote(
            target_id,
            lease=self._lease,
            now=datetime.now(timezone.utc),
        )

    def health(self) -> ReplicationHealth:
        return self._witness.health()

    def read(self, key: StateKey) -> StateRecord | None:
        return self._primary().read(key)

    def write(
        self,
        record: StateRecord,
        *,
        expected_revision: int | None,
    ) -> StateRecord:
        if not isinstance(record, StateRecord):
            raise TypeError("record must be StateRecord")
        self._renew()
        if self._witness.pending_sequences():
            raise ReplicationPartialCommitError(
                "pending replication must be repaired before new writes"
            )
        sequence = self._witness.prepare(
            lease=self._lease,
            operation_kind="write",
            key=record.key,
            expected_revision=expected_revision,
            record=record,
            now=datetime.now(timezone.utc),
        )
        self._replicate_sequence(sequence)
        persisted = self.read(record.key)
        if persisted != record:
            raise ReplicationError("primary readback differs after replicated write")
        return persisted

    def delete(
        self,
        key: StateKey,
        *,
        expected_revision: int,
    ) -> None:
        self._renew()
        if self._witness.pending_sequences():
            raise ReplicationPartialCommitError(
                "pending replication must be repaired before new deletes"
            )
        sequence = self._witness.prepare(
            lease=self._lease,
            operation_kind="delete",
            key=key,
            expected_revision=expected_revision,
            record=None,
            now=datetime.now(timezone.utc),
        )
        self._replicate_sequence(sequence)

    def list_namespace(
        self,
        namespace: str,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[StateRecord, ...]:
        return self._primary().list_namespace(
            namespace,
            principal_id=principal_id,
            audience=audience,
        )
