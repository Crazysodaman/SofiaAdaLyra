from datetime import datetime, timezone
from pathlib import Path

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
    path = tmp_path / "machine-locations.json"
    registry = MachineLocationRegistry(path)
    registry.set(record())

    loaded = MachineLocationRegistry(path)
    restored = loaded.get("machine-1")

    assert restored == record()
    assert path.exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_machine_location_registry_replaces_one_machine_without_touching_others(
    tmp_path: Path,
):
    path = tmp_path / "machine-locations.json"
    registry = MachineLocationRegistry(path)
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

    loaded = MachineLocationRegistry(path)
    assert loaded.get("machine-1").label == "Server Room"
    assert loaded.get("machine-2").label == "Office"


def test_machine_location_registry_hostname_lookup_is_case_insensitive(
    tmp_path: Path,
):
    registry = MachineLocationRegistry(
        tmp_path / "machine-locations.json"
    )
    registry.set(record())

    matches = registry.find_hostname("artemis")
    assert len(matches) == 1
    assert matches[0].machine_id == "machine-1"
