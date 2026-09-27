"""Central State Plane schema compatibility and migration coordination."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class MigrationPhase(str, Enum):
    EXPAND = "expand"
    MIGRATE = "migrate"
    CONTRACT = "contract"


@dataclass(frozen=True, slots=True)
class SchemaCompatibility:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if type(self.minimum) is not int or self.minimum < 0:
            raise ValueError("minimum schema revision must be >= 0")
        if type(self.maximum) is not int or self.maximum < self.minimum:
            raise ValueError("maximum schema revision must be >= minimum")

    def accepts(self, revision: int) -> bool:
        return type(revision) is int and self.minimum <= revision <= self.maximum


@dataclass(frozen=True, slots=True)
class SchemaMigration:
    migration_id: str
    owner_package: str
    from_revision: int
    to_revision: int
    phase: MigrationPhase

    def __post_init__(self) -> None:
        _id(self.migration_id, "migration_id")
        _id(self.owner_package, "owner_package")
        if type(self.from_revision) is not int or self.from_revision < 0:
            raise ValueError("from_revision must be >= 0")
        if type(self.to_revision) is not int or self.to_revision <= self.from_revision:
            raise ValueError("to_revision must be greater than from_revision")
        if not isinstance(self.phase, MigrationPhase):
            raise TypeError("phase must be a MigrationPhase")


class SchemaMigrationError(RuntimeError):
    pass


class SchemaRegistry:
    """Central revision ledger and exclusive migration lease.

    Package-specific SQL remains package-owned. This registry coordinates when
    a migration may run and records exact phase/revision evidence so releases
    can reject unsupported database revisions before mutation.
    """

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS sofia_schema_state (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        revision INTEGER NOT NULL CHECK(revision>=0)
                    );
                    INSERT OR IGNORE INTO sofia_schema_state(singleton, revision)
                    VALUES (1, 0);

                    CREATE TABLE IF NOT EXISTS sofia_schema_migrations (
                        migration_id TEXT PRIMARY KEY,
                        owner_package TEXT NOT NULL,
                        from_revision INTEGER NOT NULL,
                        to_revision INTEGER NOT NULL,
                        phase TEXT NOT NULL CHECK(
                            phase IN ('expand','migrate','contract')
                        ),
                        applied_at TEXT NOT NULL,
                        actor TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS sofia_schema_migration_lease (
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        owner_id TEXT NOT NULL,
                        acquired_at TEXT NOT NULL
                    );
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def revision(self) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT revision FROM sofia_schema_state WHERE singleton=1"
            ).fetchone()
        if row is None:
            raise SchemaMigrationError("schema revision row is missing")
        return int(row[0])

    def require_compatible(self, compatibility: SchemaCompatibility) -> int:
        if not isinstance(compatibility, SchemaCompatibility):
            raise TypeError("SchemaCompatibility required")
        revision = self.revision()
        if not compatibility.accepts(revision):
            raise SchemaMigrationError(
                f"state schema revision {revision} is outside supported "
                f"window {compatibility.minimum}..{compatibility.maximum}"
            )
        return revision

    def acquire(self, *, owner_id: str, now: datetime) -> None:
        _id(owner_id, "owner_id")
        moment = _utc(now)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute(
                    "SELECT owner_id FROM sofia_schema_migration_lease "
                    "WHERE singleton=1"
                ).fetchone()
                if current is not None:
                    raise SchemaMigrationError(
                        f"schema migration lease is already held by {current[0]}"
                    )
                db.execute(
                    "INSERT INTO sofia_schema_migration_lease "
                    "(singleton, owner_id, acquired_at) VALUES (1, ?, ?)",
                    (owner_id, moment.isoformat()),
                )

    def release(self, *, owner_id: str) -> None:
        _id(owner_id, "owner_id")
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute(
                    "DELETE FROM sofia_schema_migration_lease "
                    "WHERE singleton=1 AND owner_id=?",
                    (owner_id,),
                )
                if changed.rowcount != 1:
                    raise SchemaMigrationError(
                        "schema migration lease is not held by caller"
                    )

    def record_applied(
        self,
        migration: SchemaMigration,
        *,
        owner_id: str,
        actor: str,
        now: datetime,
    ) -> int:
        if not isinstance(migration, SchemaMigration):
            raise TypeError("SchemaMigration required")
        _id(owner_id, "owner_id")
        _id(actor, "actor")
        moment = _utc(now)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                lease = db.execute(
                    "SELECT owner_id FROM sofia_schema_migration_lease "
                    "WHERE singleton=1"
                ).fetchone()
                if lease is None or lease[0] != owner_id:
                    raise SchemaMigrationError(
                        "caller does not hold schema migration lease"
                    )
                revision = int(
                    db.execute(
                        "SELECT revision FROM sofia_schema_state "
                        "WHERE singleton=1"
                    ).fetchone()[0]
                )
                existing = db.execute(
                    "SELECT from_revision, to_revision, phase "
                    "FROM sofia_schema_migrations WHERE migration_id=?",
                    (migration.migration_id,),
                ).fetchone()
                if existing is not None:
                    expected = (
                        migration.from_revision,
                        migration.to_revision,
                        migration.phase.value,
                    )
                    if tuple(existing) != expected:
                        raise SchemaMigrationError(
                            "migration ID already records different semantics"
                        )
                    return revision
                if revision != migration.from_revision:
                    raise SchemaMigrationError(
                        "migration source revision does not match "
                        "authoritative schema revision"
                    )
                db.execute(
                    "INSERT INTO sofia_schema_migrations "
                    "(migration_id, owner_package, from_revision, to_revision, "
                    "phase, applied_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        migration.migration_id,
                        migration.owner_package,
                        migration.from_revision,
                        migration.to_revision,
                        migration.phase.value,
                        moment.isoformat(),
                        actor,
                    ),
                )
                db.execute(
                    "UPDATE sofia_schema_state SET revision=? "
                    "WHERE singleton=1",
                    (migration.to_revision,),
                )
        return migration.to_revision
