"""SQLite backend for the backend-neutral State Plane contract."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from sofia.state_plane.model import (
    StateClass,
    StateKey,
    StateRecord,
    StateScope,
)
from sofia.state_plane.store import (
    StateConflictError,
    StatePlane,
    StatePlaneError,
)


class SQLiteStatePlane(StatePlane):
    """Compare-and-set state backend for the current single-database phase."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS state_plane_records (
                        namespace TEXT NOT NULL,
                        record_name TEXT NOT NULL,
                        state_class TEXT NOT NULL,
                        owner_package TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK(revision>=1),
                        schema_revision INTEGER NOT NULL CHECK(schema_revision>=1),
                        payload BLOB NOT NULL,
                        content_type TEXT NOT NULL,
                        principal_id TEXT,
                        audience_id TEXT,
                        host_id TEXT,
                        payload_digest TEXT NOT NULL,
                        PRIMARY KEY(namespace, record_name)
                    );
                    CREATE INDEX IF NOT EXISTS state_plane_owner_idx
                        ON state_plane_records(owner_package, namespace);
                    CREATE INDEX IF NOT EXISTS state_plane_principal_idx
                        ON state_plane_records(principal_id)
                        WHERE principal_id IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS state_plane_audience_idx
                        ON state_plane_records(audience_id)
                        WHERE audience_id IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS state_plane_host_idx
                        ON state_plane_records(host_id)
                        WHERE host_id IS NOT NULL;
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _from_row(row: tuple) -> StateRecord:
        return StateRecord(
            key=StateKey(namespace=row[0], name=row[1]),
            state_class=StateClass(row[2]),
            owner_package=row[3],
            scope=StateScope(row[4]),
            revision=int(row[5]),
            schema_revision=int(row[6]),
            payload=bytes(row[7]),
            content_type=row[8],
            principal_id=row[9],
            audience_id=row[10],
            host_id=row[11],
        )

    def get(self, key: StateKey) -> StateRecord | None:
        if not isinstance(key, StateKey):
            raise TypeError("StateKey required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT namespace, record_name, state_class, owner_package, "
                "scope, revision, schema_revision, payload, content_type, "
                "principal_id, audience_id, host_id "
                "FROM state_plane_records WHERE namespace=? AND record_name=?",
                (key.namespace, key.name),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def compare_and_set(
        self,
        record: StateRecord,
        *,
        expected_revision: int | None,
    ) -> StateRecord:
        if not isinstance(record, StateRecord):
            raise TypeError("StateRecord required")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise ValueError("expected_revision must be positive or None")

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    "SELECT revision FROM state_plane_records "
                    "WHERE namespace=? AND record_name=?",
                    (record.key.namespace, record.key.name),
                ).fetchone()
                if expected_revision is None:
                    if current is not None:
                        raise StateConflictError(
                            "State Plane record already exists"
                        )
                    if record.revision != 1:
                        raise StateConflictError(
                            "new State Plane record must begin at revision 1"
                        )
                    db.execute(
                        "INSERT INTO state_plane_records "
                        "(namespace, record_name, state_class, owner_package, "
                        "scope, revision, schema_revision, payload, content_type, "
                        "principal_id, audience_id, host_id, payload_digest) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            record.key.namespace,
                            record.key.name,
                            record.state_class.value,
                            record.owner_package,
                            record.scope.value,
                            record.revision,
                            record.schema_revision,
                            record.payload,
                            record.content_type,
                            record.principal_id,
                            record.audience_id,
                            record.host_id,
                            record.payload_digest,
                        ),
                    )
                else:
                    if current is None or int(current[0]) != expected_revision:
                        raise StateConflictError(
                            "State Plane expected revision no longer matches"
                        )
                    if record.revision != expected_revision + 1:
                        raise StateConflictError(
                            "State Plane revisions must advance exactly once"
                        )
                    changed = db.execute(
                        "UPDATE state_plane_records SET "
                        "state_class=?, owner_package=?, scope=?, revision=?, "
                        "schema_revision=?, payload=?, content_type=?, "
                        "principal_id=?, audience_id=?, host_id=?, payload_digest=? "
                        "WHERE namespace=? AND record_name=? AND revision=?",
                        (
                            record.state_class.value,
                            record.owner_package,
                            record.scope.value,
                            record.revision,
                            record.schema_revision,
                            record.payload,
                            record.content_type,
                            record.principal_id,
                            record.audience_id,
                            record.host_id,
                            record.payload_digest,
                            record.key.namespace,
                            record.key.name,
                            expected_revision,
                        ),
                    )
                    if changed.rowcount != 1:
                        raise StateConflictError(
                            "State Plane record changed concurrently"
                        )

        stored = self.get(record.key)
        if stored is None:
            raise StatePlaneError("stored State Plane record could not be reloaded")
        return stored

    def list_namespace(
        self,
        namespace: str,
    ) -> tuple[StateRecord, ...]:
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT namespace, record_name, state_class, owner_package, "
                "scope, revision, schema_revision, payload, content_type, "
                "principal_id, audience_id, host_id "
                "FROM state_plane_records WHERE namespace=? "
                "ORDER BY record_name",
                (namespace,),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)
