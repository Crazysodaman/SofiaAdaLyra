from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

@dataclass(frozen=True, slots=True)
class SchemaCompatibility:
    current_revision: int
    readable_min: int
    readable_max: int
    writable_min: int
    writable_max: int

    def __post_init__(self) -> None:
        values = (
            self.current_revision,
            self.readable_min,
            self.readable_max,
            self.writable_min,
            self.writable_max,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("schema revisions must be positive integers")
        if self.readable_min > self.readable_max:
            raise ValueError("readable schema window is invalid")
        if self.writable_min > self.writable_max:
            raise ValueError("writable schema window is invalid")
        if not self.can_read(self.current_revision):
            raise ValueError("current revision must be readable")
        if not self.can_write(self.current_revision):
            raise ValueError("current revision must be writable")

    def can_read(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.readable_min <= revision <= self.readable_max
        )

    def can_write(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.writable_min <= revision <= self.writable_max
        )


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
        "ops-dependencies",
        "ops-platform-install",
        "virtual-world",
        "personality-preferences",
        "rel-nicknames",
        "creative-inventory",
    )
)


def verify_production_component_schemas(
    state_path: Path | str,
) -> StateSchemaCoordinator:
    coordinator = StateSchemaCoordinator(state_path)
    for schema in PRODUCTION_COMPONENT_SCHEMAS:
        coordinator.require(schema)
    return coordinator
