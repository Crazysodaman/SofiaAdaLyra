from datetime import datetime, timezone
from pathlib import Path

from sofia.composition import root as composition_root
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.factory import (
    NWS_ENVIRONMENT_CAPABILITY,
    create_environment_service,
)
from sofia.environment.model import LocationSubject
from sofia.environment.nws import NwsEnvironmentProvider
from sofia.machine.location import (
    MachineLocationRegistry,
    new_machine_location,
)
from sofia.machine.model import MachineIdentity, OperatingSystemInfo, PlatformFamily
from sofia.machine.discovery import MachineDiscoveryResult


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class FakeDiscovery:
    def discover(self):
        return MachineDiscoveryResult(
            identity=MachineIdentity(
                machine_id="machine-1",
                hostname="Artemis",
            ),
            operating_system=OperatingSystemInfo(
                family=PlatformFamily.WINDOWS,
            ),
            observed_at=NOW,
            source="test",
        )


def configuration(tmp_path: Path, environment=None):
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "state" / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=tmp_path,
        environment=environment or EnvironmentConfiguration(),
    )


def test_composition_loads_persistent_location_for_current_machine(
    tmp_path,
    monkeypatch,
):
    state = tmp_path / "state"
    registry = MachineLocationRegistry(
        state / "machine-locations.json"
    )
    registry.set(
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
    monkeypatch.setattr(
        composition_root,
        "create_machine_discovery",
        lambda: FakeDiscovery(),
    )

    effective = (
        composition_root
        ._configuration_with_persistent_host_location(
            configuration(tmp_path)
        )
    )

    host = effective.environment.host_location
    assert host is not None
    assert host.label == "Home Lab"
    assert host.subject is LocationSubject.HOST
    assert host.source_id == "machine.location:machine-1"
    assert host.latitude == 32.6
    assert host.longitude == -97.2


def test_explicit_process_host_location_overrides_persistent_registry(
    tmp_path,
    monkeypatch,
):
    state = tmp_path / "state"
    registry = MachineLocationRegistry(
        state / "machine-locations.json"
    )
    registry.set(
        new_machine_location(
            machine_id="machine-1",
            hostname="Artemis",
            label="Inventory Site",
            timezone_name="America/Chicago",
            latitude=32.6,
            longitude=-97.2,
            updated_at=NOW,
        )
    )
    monkeypatch.setattr(
        composition_root,
        "create_machine_discovery",
        lambda: FakeDiscovery(),
    )
    explicit = ConfiguredLocation(
        label="Temporary Test Site",
        timezone="America/Denver",
        subject=LocationSubject.HOST,
        latitude=39.7,
        longitude=-104.9,
        source_id="config.environment.host",
    )

    effective = (
        composition_root
        ._configuration_with_persistent_host_location(
            configuration(
                tmp_path,
                EnvironmentConfiguration(
                    host_location=explicit
                ),
            )
        )
    )

    assert effective.environment.host_location is explicit


def test_missing_persistent_location_leaves_configuration_unchanged(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        composition_root,
        "create_machine_discovery",
        lambda: FakeDiscovery(),
    )
    original = configuration(tmp_path)
    effective = (
        composition_root
        ._configuration_with_persistent_host_location(original)
    )
    assert effective is original

def test_persistent_host_location_completes_nws_host_configuration(
    tmp_path,
    monkeypatch,
):
    state = tmp_path / "state"
    registry = MachineLocationRegistry(
        state / "machine-locations.json"
    )
    registry.set(
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
    monkeypatch.setattr(
        composition_root,
        "create_machine_discovery",
        lambda: FakeDiscovery(),
    )
    original = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=state / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=(
            NWS_ENVIRONMENT_CAPABILITY,
        ),
        environment=EnvironmentConfiguration(
            nws_enabled=True,
            nws_location_subject=LocationSubject.HOST,
        ),
    )

    effective = (
        composition_root
        ._configuration_with_persistent_host_location(original)
    )
    service = create_environment_service(effective)

    assert effective.environment.host_location is not None
    assert len(service.providers) == 1
    assert isinstance(
        service.providers[0],
        NwsEnvironmentProvider,
    )

