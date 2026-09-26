from datetime import datetime, timezone
from pathlib import Path

from sofia.machine.capability import MachineToolService
from sofia.machine.location import new_machine_location
from sofia.machine.model import (
    HardwareProfile,
    MachineIdentity,
    MachineProfile,
    MachineVerification,
    OperatingSystemInfo,
    PlatformFamily,
    VirtualizationInfo,
)
from sofia.machine.observation import (
    MachineObservation,
    ObservationProvenance,
    ObservationSource,
)


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def observation():
    profile = MachineProfile(
        identity=MachineIdentity(
            machine_id="machine-1",
            hostname="Artemis",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        hardware=HardwareProfile(),
        verification=MachineVerification(
            first_observed_at=NOW,
            last_verified_at=NOW,
            source="test",
        ),
    )
    return MachineObservation(
        profile=profile,
        observed_at=NOW,
        verified_at=NOW,
        provenance=ObservationProvenance(
            ObservationSource.MANUAL,
            "test",
        ),
    )


def test_machine_inventory_tool_surfaces_location_without_coordinates(
    tmp_path: Path,
):
    service = MachineToolService(tmp_path / "sofia.db")
    service.inventory.record(observation())
    service.location_registry.set(
        new_machine_location(
            machine_id="machine-1",
            hostname="Artemis",
            label="Home Lab",
            timezone_name="America/Chicago",
            latitude=32.6,
            longitude=-97.2,
            updated_at=NOW,
        )
    )

    result = service.get("machine-1")

    assert result is not None
    assert result["configured_location"]["label"] == "Home Lab"
    assert (
        result["configured_location"]["timezone"]
        == "America/Chicago"
    )
    assert "latitude" not in result["configured_location"]
    assert "longitude" not in result["configured_location"]
