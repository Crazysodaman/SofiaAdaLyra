from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.state.component_schema import (
    ComponentSchema,
    StateSchemaCoordinator,
)
from sofia.state.migration_lease import MigrationLeaseBusy
from sofia.state.migration_runner import (
    MigrationOperation,
    StateMigrationRunner,
)
from sofia.state.schema import (
    MigrationPhase,
    MigrationStep,
    SchemaCompatibility,
    SchemaRegistry,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 3, 2, 0, tzinfo=timezone.utc)
REV1 = SchemaCompatibility(1, 1, 1, 1, 1)
REV2 = SchemaCompatibility(2, 1, 2, 2, 2)


@pytest.fixture
def state(tmp_path: Path) -> Path:
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO demo(value) VALUES ('old')")
    StateSchemaCoordinator(path).require(
        ComponentSchema("demo-component", REV1)
    )
    SQLiteStatePlane(path)
    return path


def registry():
    return SchemaRegistry(
        compatibility=REV2,
        steps=(
            MigrationStep(
                "demo-1-2-expand",
                1,
                2,
                MigrationPhase.EXPAND,
                True,
            ),
            MigrationStep(
                "demo-1-2-migrate",
                1,
                2,
                MigrationPhase.MIGRATE,
                True,
            ),
        ),
    )


def operations(*, fail_validation=False):
    def expand(db):
        db.execute("ALTER TABLE demo ADD COLUMN normalized TEXT")

    def validate_expand(db):
        columns = {
            row[1] for row in db.execute("PRAGMA table_info(demo)")
        }
        assert "normalized" in columns

    def migrate(db):
        db.execute(
            "UPDATE demo SET normalized=upper(value)"
        )

    def validate_migrate(db):
        if fail_validation:
            raise RuntimeError("synthetic validation failure")
        assert db.execute(
            "SELECT normalized FROM demo WHERE id=1"
        ).fetchone()[0] == "OLD"

    return (
        MigrationOperation(
            registry().steps[0],
            REV2,
            expand,
            validate_expand,
        ),
        MigrationOperation(
            registry().steps[1],
            REV2,
            migrate,
            validate_migrate,
        ),
    )


def test_runner_applies_all_transition_phases_atomically(state):
    plane = SQLiteStatePlane(state)
    result = StateMigrationRunner(
        state_path=state,
        state_plane=plane,
        owner_id="migration:test",
    ).run(
        component="demo-component",
        registry=registry(),
        operations=operations(),
        target_revision=2,
        evidence_prefix="test-migration",
        now=NOW,
    )

    assert result.from_revision == 1
    assert result.to_revision == 2
    assert result.migration_ids == (
        "demo-1-2-expand",
        "demo-1-2-migrate",
    )
    assert StateSchemaCoordinator(state).current(
        "demo-component"
    ) == REV2
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT normalized FROM demo WHERE id=1"
        ).fetchone()[0] == "OLD"
        rows = db.execute(
            """
            SELECT migration_id FROM state_schema_migration
            WHERE component='demo-component'
            ORDER BY rowid
            """
        ).fetchall()
    assert [row[0] for row in rows] == list(result.migration_ids)


def test_validation_failure_rolls_back_data_and_registry(state):
    plane = SQLiteStatePlane(state)
    runner = StateMigrationRunner(
        state_path=state,
        state_plane=plane,
        owner_id="migration:test",
    )

    with pytest.raises(RuntimeError, match="validation"):
        runner.run(
            component="demo-component",
            registry=registry(),
            operations=operations(fail_validation=True),
            target_revision=2,
            evidence_prefix="test-migration",
            now=NOW,
        )

    assert StateSchemaCoordinator(state).current(
        "demo-component"
    ) == REV1
    with sqlite3.connect(state) as db:
        columns = {
            row[1] for row in db.execute("PRAGMA table_info(demo)")
        }
        count = db.execute(
            "SELECT COUNT(*) FROM state_schema_migration"
        ).fetchone()[0]
    assert "normalized" not in columns
    assert count == 0


def test_missing_executable_operation_fails_before_lease(state):
    plane = SQLiteStatePlane(state)
    runner = StateMigrationRunner(
        state_path=state,
        state_plane=plane,
        owner_id="migration:test",
    )

    with pytest.raises(LookupError, match="missing executable"):
        runner.run(
            component="demo-component",
            registry=registry(),
            operations=(operations()[0],),
            target_revision=2,
            evidence_prefix="test-migration",
            now=NOW,
        )


def test_existing_migration_lease_blocks_second_owner(state):
    plane = SQLiteStatePlane(state)
    blocker = StateMigrationRunner(
        state_path=state,
        state_plane=plane,
        owner_id="migration:blocker",
    )
    blocker.leases.acquire(
        owner_id="migration:blocker",
        now=NOW,
    )

    runner = StateMigrationRunner(
        state_path=state,
        state_plane=plane,
        owner_id="migration:other",
    )
    with pytest.raises(MigrationLeaseBusy):
        runner.run(
            component="demo-component",
            registry=registry(),
            operations=operations(),
            target_revision=2,
            evidence_prefix="test-migration",
            now=NOW,
        )
