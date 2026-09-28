from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from threading import RLock

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane, StatePlaneConflictError


class SQLiteStatePlane(StatePlane):
    """SQLite production baseline for backend-neutral Sofía state."""

    SCHEMA_REVISION = 1

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(
            str(self.path),
            timeout=10.0,
            check_same_thread=False,
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS state_plane_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_plane_record (
                    namespace TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    state_class TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision > 0),
                    value BLOB NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (
                        namespace,
                        record_key,
                        principal_id,
                        audience
                    )
                );
                """
            )
            row = db.execute(
                "SELECT value FROM state_plane_meta WHERE key='schema_revision'"
            ).fetchone()
            if row is None:
                db.execute(
                    """
                    INSERT INTO state_plane_meta(key, value)
                    VALUES ('schema_revision', ?)
                    """,
                    (str(self.SCHEMA_REVISION),),
                )
            elif int(row["value"]) != self.SCHEMA_REVISION:
                raise RuntimeError(
                    "State Plane schema revision requires an explicit migration"
                )
            db.commit()

    @property
    def schema_revision(self) -> int:
        with self._lock, closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT value FROM state_plane_meta WHERE key='schema_revision'"
            ).fetchone()
        if row is None:
            raise RuntimeError("State Plane schema metadata is missing")
        return int(row["value"])

    @staticmethod
    def _scope(key: StateKey) -> tuple[str, str, str, str]:
        return (
            key.namespace,
            key.key,
            key.principal_id or "",
            key.audience or "",
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> StateRecord:
        principal_id = row["principal_id"] or None
        audience = row["audience"] or None
        return StateRecord(
            key=StateKey(
                namespace=row["namespace"],
                key=row["record_key"],
                principal_id=principal_id,
                audience=audience,
            ),
            state_class=StateClass(row["state_class"]),
            revision=int(row["revision"]),
            value=bytes(row["value"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            source=row["source"],
        )

    def read(self, key: StateKey) -> StateRecord | None:
        if not isinstance(key, StateKey):
            raise TypeError("key must be a StateKey")
        with self._lock, closing(self._connect()) as db, db:
            row = db.execute(
                """
                SELECT namespace, record_key, principal_id, audience,
                       state_class, revision, value, updated_at, source
                FROM state_plane_record
                WHERE namespace=? AND record_key=?
                  AND principal_id=? AND audience=?
                """,
                self._scope(key),
            ).fetchone()
        return None if row is None else self._record(row)

    def write(
        self,
        record: StateRecord,
        *,
        expected_revision: int | None,
    ) -> StateRecord:
        if not isinstance(record, StateRecord):
            raise TypeError("record must be a StateRecord")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise ValueError(
                "expected_revision must be None or a positive integer"
            )
        scope = self._scope(record.key)
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                """
                SELECT revision
                FROM state_plane_record
                WHERE namespace=? AND record_key=?
                  AND principal_id=? AND audience=?
                """,
                scope,
            ).fetchone()

            if expected_revision is None:
                if current is not None:
                    db.rollback()
                    raise StatePlaneConflictError(
                        "state record already exists"
                    )
                if record.revision != 1:
                    db.rollback()
                    raise StatePlaneConflictError(
                        "new state record must begin at revision 1"
                    )
                db.execute(
                    """
                    INSERT INTO state_plane_record (
                        namespace, record_key, principal_id, audience,
                        state_class, revision, value, updated_at, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        *scope,
                        record.state_class.value,
                        record.revision,
                        record.value,
                        record.updated_at.isoformat(),
                        record.source,
                    ),
                )
            else:
                if current is None or int(current["revision"]) != expected_revision:
                    db.rollback()
                    raise StatePlaneConflictError(
                        "state record revision changed before write"
                    )
                if record.revision != expected_revision + 1:
                    db.rollback()
                    raise StatePlaneConflictError(
                        "updated state record must increment revision exactly once"
                    )
                changed = db.execute(
                    """
                    UPDATE state_plane_record
                    SET state_class=?, revision=?, value=?, updated_at=?, source=?
                    WHERE namespace=? AND record_key=?
                      AND principal_id=? AND audience=?
                      AND revision=?
                    """,
                    (
                        record.state_class.value,
                        record.revision,
                        record.value,
                        record.updated_at.isoformat(),
                        record.source,
                        *scope,
                        expected_revision,
                    ),
                )
                if changed.rowcount != 1:
                    db.rollback()
                    raise StatePlaneConflictError(
                        "state record compare-and-swap failed"
                    )
            db.commit()
        persisted = self.read(record.key)
        if persisted is None:
            raise RuntimeError("State Plane write vanished after commit")
        return persisted

    def delete(
        self,
        key: StateKey,
        *,
        expected_revision: int,
    ) -> None:
        if not isinstance(key, StateKey):
            raise TypeError("key must be a StateKey")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                """
                DELETE FROM state_plane_record
                WHERE namespace=? AND record_key=?
                  AND principal_id=? AND audience=?
                  AND revision=?
                """,
                (*self._scope(key), expected_revision),
            )
            if changed.rowcount != 1:
                db.rollback()
                raise StatePlaneConflictError(
                    "state record compare-and-swap delete failed"
                )
            db.commit()

    def list_namespace(
        self,
        namespace: str,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[StateRecord, ...]:
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace must be nonempty")
        # None means the unscoped partition, not every principal. Cross-principal
        # administrative enumeration must use a separate privileged interface.
        principal = principal_id or ""
        audience_value = audience or ""
        with self._lock, closing(self._connect()) as db, db:
            rows = db.execute(
                """
                SELECT namespace, record_key, principal_id, audience,
                       state_class, revision, value, updated_at, source
                FROM state_plane_record
                WHERE namespace=? AND principal_id=? AND audience=?
                ORDER BY record_key ASC
                """,
                (namespace, principal, audience_value),
            ).fetchall()
        return tuple(self._record(row) for row in rows)
