from __future__ import annotations

from contextlib import closing
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import sqlite3

from sofia.platform.state.model import StateClass, StateKey, StateRecord
from sofia.platform.state.plane import StatePlane, StatePlaneConflictError, StateWrite
from sofia.platform.state.sqlite_access import shared_sqlite_access


class SQLiteStatePlane(StatePlane):
    """SQLite production baseline for backend-neutral Sofía state."""

    SCHEMA_REVISION = 1

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite = shared_sqlite_access(self.path)
        # State Plane compare-and-swap writes share the database-wide writer
        # boundary with other migrated stores.
        self._lock = self._sqlite.write_lock
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return self._sqlite.connect(row_factory=sqlite3.Row)

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

                CREATE TABLE IF NOT EXISTS state_plane_lineage (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    operation TEXT NOT NULL CHECK(operation IN ('write','delete')),
                    revision INTEGER NOT NULL,
                    value_sha256 TEXT NOT NULL,
                    source TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
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
        persisted, = self.write_transaction(
            (StateWrite(record, expected_revision),)
        )
        return persisted

    @staticmethod
    def _write_one(
        db: sqlite3.Connection,
        record: StateRecord,
        expected_revision: int | None,
    ) -> None:
        scope = SQLiteStatePlane._scope(record.key)
        current = db.execute(
            """SELECT revision FROM state_plane_record
            WHERE namespace=? AND record_key=? AND principal_id=? AND audience=?""",
            scope,
        ).fetchone()
        if expected_revision is None:
            if current is not None:
                raise StatePlaneConflictError("state record already exists")
            if record.revision != 1:
                raise StatePlaneConflictError(
                    "new state record must begin at revision 1"
                )
            db.execute(
                """INSERT INTO state_plane_record(
                namespace,record_key,principal_id,audience,state_class,revision,
                value,updated_at,source) VALUES(?,?,?,?,?,?,?,?,?)""",
                (*scope, record.state_class.value, record.revision, record.value,
                 record.updated_at.isoformat(), record.source),
            )
        else:
            if current is None or int(current["revision"]) != expected_revision:
                raise StatePlaneConflictError(
                    "state record revision changed before write"
                )
            if record.revision != expected_revision + 1:
                raise StatePlaneConflictError(
                    "updated state record must increment revision exactly once"
                )
            changed = db.execute(
                """UPDATE state_plane_record
                SET state_class=?,revision=?,value=?,updated_at=?,source=?
                WHERE namespace=? AND record_key=? AND principal_id=? AND audience=?
                  AND revision=?""",
                (record.state_class.value, record.revision, record.value,
                 record.updated_at.isoformat(), record.source, *scope,
                 expected_revision),
            )
            if changed.rowcount != 1:
                raise StatePlaneConflictError(
                    "state record compare-and-swap failed"
                )
        db.execute(
            """INSERT INTO state_plane_lineage(
            namespace,record_key,principal_id,audience,operation,revision,
            value_sha256,source,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (*scope, "write", record.revision,
             sha256(record.value).hexdigest(), record.source,
             record.updated_at.isoformat()),
        )

    def write_transaction(
        self, writes: tuple[StateWrite, ...],
    ) -> tuple[StateRecord, ...]:
        if type(writes) is not tuple or not writes:
            raise ValueError("writes must be a nonempty tuple")
        if any(not isinstance(item, StateWrite) for item in writes):
            raise TypeError("writes must contain StateWrite values")
        scopes = [self._scope(item.record.key) for item in writes]
        if len(scopes) != len(set(scopes)):
            raise ValueError(
                "an atomic transaction cannot write the same key twice"
            )
        with self._lock, closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for item in writes:
                self._write_one(
                    db, item.record, item.expected_revision,
                )
        persisted = tuple(self.read(item.record.key) for item in writes)
        if any(item is None for item in persisted):
            raise RuntimeError("State Plane transaction vanished after commit")
        return persisted  # type: ignore[return-value]

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
            scope = self._scope(key)
            current = db.execute(
                """SELECT value,source,updated_at FROM state_plane_record
                WHERE namespace=? AND record_key=? AND principal_id=?
                  AND audience=? AND revision=?""",
                (*scope, expected_revision),
            ).fetchone()
            if current is None:
                raise StatePlaneConflictError(
                    "state record compare-and-swap delete failed"
                )
            changed = db.execute(
                """
                DELETE FROM state_plane_record
                WHERE namespace=? AND record_key=?
                  AND principal_id=? AND audience=?
                  AND revision=?
                """,
                (*scope, expected_revision),
            )
            if changed.rowcount != 1:
                db.rollback()
                raise StatePlaneConflictError(
                    "state record compare-and-swap delete failed"
                )
            db.execute(
                """INSERT INTO state_plane_lineage(
                namespace,record_key,principal_id,audience,operation,revision,
                value_sha256,source,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (*scope, "delete", expected_revision,
                 sha256(bytes(current["value"])).hexdigest(), current["source"],
                 current["updated_at"]),
            )

    def audit_lineage(
        self, *, namespace: str | None = None, limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        if namespace is not None and (
            not isinstance(namespace, str) or not namespace.strip()
        ):
            raise ValueError("namespace must be nonempty or None")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be in 1..1000")
        query = "SELECT * FROM state_plane_lineage"
        parameters: list[object] = []
        if namespace is not None:
            query += " WHERE namespace=?"
            parameters.append(namespace)
        query += " ORDER BY event_id DESC LIMIT ?"
        parameters.append(limit)
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(query, parameters).fetchall()
        return tuple(dict(row) for row in rows)

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

    def list_scopes(self, namespace: str) -> tuple[tuple[str | None, str | None], ...]:
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace must be nonempty")
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT DISTINCT principal_id,audience FROM state_plane_record "
                "WHERE namespace=? ORDER BY principal_id,audience",
                (namespace,),
            ).fetchall()
        return tuple((row[0] or None, row[1] or None) for row in rows)
