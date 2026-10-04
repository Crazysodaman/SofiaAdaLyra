from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from sofia.state.sqlite_plane import SQLiteStatePlane

import pytest

from sofia.machine.location import (
    MachineLocationRecord,
    MachineLocationRegistry,
    new_machine_location,
)


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def record(**overrides):
    values = {
        "machine_id": "machine-1",
        "hostname": "Artemis",
        "label": "Home Lab",
        "timezone": "America/Chicago",
        "latitude": 32.6,
        "longitude": -97.2,
        "updated_at": NOW,
        "source": "operator",
    }
    values.update(overrides)
    return MachineLocationRecord(**values)


def test_machine_location_record_validates_timezone_and_coordinates():
    value = record()
    assert value.hostname == "Artemis"
    assert value.timezone == "America/Chicago"

    with pytest.raises(ValueError, match="unknown machine location timezone"):
        record(timezone="Mars/Olympus_Mons")

    with pytest.raises(ValueError, match="latitude"):
        record(latitude=91.0)


def test_machine_location_registry_round_trips_atomically(tmp_path: Path):
    path = tmp_path / "sofia.db"
    registry = MachineLocationRegistry(SQLiteStatePlane(path))
    registry.set(record())

    loaded = MachineLocationRegistry(SQLiteStatePlane(path))
    restored = loaded.get("machine-1")

    assert restored == record()
    assert path.exists()
    assert not (tmp_path / "machine-locations.json").exists()


def test_machine_location_registry_replaces_one_machine_without_touching_others(
    tmp_path: Path,
):
    path = tmp_path / "sofia.db"
    registry = MachineLocationRegistry(SQLiteStatePlane(path))
    registry.set(record())
    registry.set(
        record(
            machine_id="machine-2",
            hostname="Venus",
            label="Office",
        )
    )
    registry.set(
        new_machine_location(
            machine_id="machine-1",
            hostname="Artemis",
            label="Server Room",
            timezone_name="America/Chicago",
            latitude=32.7,
            longitude=-97.3,
            updated_at=NOW,
        )
    )

    loaded = MachineLocationRegistry(SQLiteStatePlane(path))
    assert loaded.get("machine-1").label == "Server Room"
    assert loaded.get("machine-2").label == "Office"


def test_machine_location_registry_hostname_lookup_is_case_insensitive(
    tmp_path: Path,
):
    registry = MachineLocationRegistry(
        SQLiteStatePlane(tmp_path / "sofia.db")
    )
    registry.set(record())

    matches = registry.find_hostname("artemis")
    assert len(matches) == 1
    assert matches[0].machine_id == "machine-1"


def write_legacy(path, records):
    rows = [dict(asdict(value), updated_at=value.updated_at.isoformat()) for value in records]
    path.write_text(json.dumps({"schema_version": 1, "locations": rows}), encoding="utf-8")


def test_location_migration_resumes_partial_import_and_retires_evidence(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    registry = MachineLocationRegistry(plane)
    first = record()
    second = record(machine_id="machine-2", hostname="Venus")
    registry.set(replace(first, source="legacy-json:operator"))
    legacy = tmp_path / "machine-locations.json"
    write_legacy(legacy, [first, second])
    retired = legacy.with_name(legacy.name + ".migrated")
    retired.write_text("older migration", encoding="utf-8")

    migrated = MachineLocationRegistry(plane, legacy_path=legacy)

    assert migrated.get(first.machine_id) == replace(first, source="legacy-json:operator")
    assert migrated.get(second.machine_id) == replace(second, source="legacy-json:operator")
    assert not legacy.exists()
    assert retired.read_text(encoding="utf-8") == "older migration"
    assert legacy.with_name(legacy.name + ".migrated.1").exists()


def test_location_migration_preserves_conflicting_canonical_configuration(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "sofia.db")
    registry = MachineLocationRegistry(plane)
    canonical = record(label="Current Office")
    registry.set(canonical)
    legacy = tmp_path / "machine-locations.json"
    write_legacy(legacy, [record()])

    with pytest.raises(RuntimeError, match="conflicts with canonical"):
        MachineLocationRegistry(plane, legacy_path=legacy)

    assert registry.get(canonical.machine_id) == canonical
    assert legacy.exists()
