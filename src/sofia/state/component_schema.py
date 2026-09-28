from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.state.schema import SchemaCompatibility


@dataclass(frozen=True, slots=True)
class ComponentSchema:
    component: str
    compatibility: SchemaCompatibility

    def __post_init__(self) -> None:
        if not isinstance(self.component, str) or not self.component.strip():
            raise ValueError("component must be nonempty")
        if not isinstance(self.compatibility, SchemaCompatibility):
            raise TypeError("compatibility must be SchemaCompatibility")


class StateSchemaCoordinator:
    """
    Central production schema registry for all SQLite-backed state components.

    Existing revision-1 package stores may create their initial tables, but every
    authoritative component must register here at startup. A revision mismatch
    fails closed until an explicit reviewed migration updates the registry.
    """

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS state_schema_component (
                    component TEXT PRIMARY KEY,
                    current_revision INTEGER NOT NULL CHECK(current_revision > 0),
                    readable_min INTEGER NOT NULL CHECK(readable_min > 0),
                    readable_max INTEGER NOT NULL CHECK(readable_max > 0),
                    writable_min INTEGER NOT NULL CHECK(writable_min > 0),
                    writable_max INTEGER NOT NULL CHECK(writable_max > 0),
                    registered_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS state_schema_migration (
                    migration_id TEXT PRIMARY KEY,
                    component TEXT NOT NULL,
                    from_revision INTEGER NOT NULL,
                    to_revision INTEGER NOT NULL,
                    applied_at TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def require(self, schema: ComponentSchema) -> None:
        if not isinstance(schema, ComponentSchema):
            raise TypeError("schema must be ComponentSchema")
        expected = schema.compatibility
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT current_revision, readable_min, readable_max,
                       writable_min, writable_max
                FROM state_schema_component
                WHERE component=?
                """,
                (schema.component,),
            ).fetchone()
            if row is None:
                db.execute(
                    """
                    INSERT INTO state_schema_component (
                        component,current_revision,readable_min,readable_max,
                        writable_min,writable_max,registered_at
                    )
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        schema.component,
                        expected.current_revision,
                        expected.readable_min,
                        expected.readable_max,
                        expected.writable_min,
                        expected.writable_max,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                db.commit()
                return

            stored = SchemaCompatibility(
                current_revision=int(row["current_revision"]),
                readable_min=int(row["readable_min"]),
                readable_max=int(row["readable_max"]),
                writable_min=int(row["writable_min"]),
                writable_max=int(row["writable_max"]),
            )
            if stored != expected:
                db.rollback()
                raise RuntimeError(
                    f"schema component {schema.component!r} differs from "
                    "the reviewed production schema registry; explicit migration required"
                )
            db.rollback()

    def record_migration(
        self,
        *,
        migration_id: str,
        component: str,
        from_revision: int,
        to_revision: int,
        compatibility: SchemaCompatibility,
        evidence_ref: str,
        applied_at: datetime,
    ) -> None:
        if not isinstance(migration_id, str) or not migration_id.strip():
            raise ValueError("migration_id must be nonempty")
        if not isinstance(component, str) or not component.strip():
            raise ValueError("component must be nonempty")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise ValueError("evidence_ref must be nonempty")
        if not isinstance(applied_at, datetime):
            raise TypeError("applied_at must be a datetime")
        if applied_at.tzinfo is None or applied_at.utcoffset() is None:
            raise ValueError("applied_at must be timezone-aware")
        if compatibility.current_revision != to_revision:
            raise ValueError("compatibility current revision must equal to_revision")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT current_revision
                FROM state_schema_component
                WHERE component=?
                """,
                (component,),
            ).fetchone()
            if row is None or int(row["current_revision"]) != from_revision:
                db.rollback()
                raise RuntimeError(
                    "component schema changed before migration record"
                )
            db.execute(
                """
                INSERT INTO state_schema_migration (
                    migration_id,component,from_revision,to_revision,
                    applied_at,evidence_ref
                )
                VALUES (?,?,?,?,?,?)
                """,
                (
                    migration_id,
                    component,
                    from_revision,
                    to_revision,
                    applied_at.astimezone(timezone.utc).isoformat(),
                    evidence_ref,
                ),
            )
            db.execute(
                """
                UPDATE state_schema_component
                SET current_revision=?,readable_min=?,readable_max=?,
                    writable_min=?,writable_max=?,registered_at=?
                WHERE component=? AND current_revision=?
                """,
                (
                    compatibility.current_revision,
                    compatibility.readable_min,
                    compatibility.readable_max,
                    compatibility.writable_min,
                    compatibility.writable_max,
                    applied_at.astimezone(timezone.utc).isoformat(),
                    component,
                    from_revision,
                ),
            )
            db.commit()


REVISION_ONE = SchemaCompatibility(
    current_revision=1,
    readable_min=1,
    readable_max=1,
    writable_min=1,
    writable_max=1,
)

PRODUCTION_COMPONENT_SCHEMAS = tuple(
    ComponentSchema(name, REVISION_ONE)
    for name in (
        "state-plane",
        "conversation",
        "social",
        "memory-reviewed",
        "chatgpt-memory-import",
        "safe-operator-stop",
        "safe-execution-approval",
        "safe-dev-approval",
        "ops-fleet",
        "run-local-lease",
        "act-delivery",
        "act-system-notice",
        "knowledge-access",
        "ui-control",
        "release-state",
        "personality-reflection",
        "habit-continuity",
        "run-heartbeat",
    )
)


def verify_production_component_schemas(
    state_path: Path | str,
) -> StateSchemaCoordinator:
    coordinator = StateSchemaCoordinator(state_path)
    for schema in PRODUCTION_COMPONENT_SCHEMAS:
        coordinator.require(schema)
    return coordinator
