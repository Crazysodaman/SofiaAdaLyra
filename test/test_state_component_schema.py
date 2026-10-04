"""Production schema registration must preserve incompatible durable evidence."""
import sqlite3

import pytest

from sofia.state.component_schema import (
    PRODUCTION_COMPONENT_SCHEMAS,
    verify_production_component_schemas,
)


def test_production_registration_is_idempotent(tmp_path):
    state = tmp_path / "sofia.db"
    verify_production_component_schemas(state)
    verify_production_component_schemas(state)
    with sqlite3.connect(state) as db:
        rows = db.execute("SELECT component, current_revision FROM state_schema_component").fetchall()
    assert dict(rows) == {schema.component: schema.compatibility.current_revision for schema in PRODUCTION_COMPONENT_SCHEMAS}


def test_production_registration_fails_closed_without_rewriting_unknown_revision(tmp_path):
    state = tmp_path / "sofia.db"
    verify_production_component_schemas(state)
    with sqlite3.connect(state) as db:
        db.execute("UPDATE state_schema_component SET current_revision=2, readable_min=2, readable_max=2, writable_min=2, writable_max=2 WHERE component='memory-reviewed'")

    with pytest.raises(RuntimeError, match="explicit migration required"):
        verify_production_component_schemas(state)

    with sqlite3.connect(state) as db:
        row = db.execute("SELECT current_revision FROM state_schema_component WHERE component='memory-reviewed'").fetchone()
    assert row == (2,)
