from datetime import datetime, timezone
import sys

from sofia.machine import location_cli
from sofia.machine.discovery import MachineDiscoveryResult
from sofia.machine.location import MachineLocationRegistry
from sofia.machine.model import (
    MachineIdentity,
    OperatingSystemInfo,
    PlatformFamily,
)


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class FakeDiscovery:
    def discover(self):
        return MachineDiscoveryResult(
            identity=MachineIdentity(
                machine_id="machine-local",
                hostname="Venus",
            ),
            operating_system=OperatingSystemInfo(
                family=PlatformFamily.WINDOWS,
            ),
            observed_at=NOW,
            source="test",
        )


def test_location_cli_set_local_persists_machine_identity(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        location_cli,
        "create_machine_discovery",
        lambda: FakeDiscovery(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "location_cli",
            "--state-directory",
            str(tmp_path),
            "set-local",
            "--label",
            "Home Lab",
            "--timezone",
            "America/Chicago",
            "--latitude",
            "32.6",
            "--longitude",
            "-97.2",
        ],
    )

    assert location_cli.main() == 0

    record = MachineLocationRegistry(
        tmp_path / "machine-locations.json"
    ).get("machine-local")
    assert record is not None
    assert record.hostname == "Venus"
    assert record.label == "Home Lab"
    output = capsys.readouterr().out
    assert "Saved Venus (machine-local) location as Home Lab" in output
