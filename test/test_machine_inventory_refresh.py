from datetime import datetime, timezone

import pytest

from sofia.machine.discovery import MachineDiscoveryResult
from sofia.machine.hardware import HardwareDiscoveryResult
from sofia.machine.inventory import MachineInventory
from sofia.machine.model import (
    HardwareProfile,
    MachineIdentity,
    OperatingSystemInfo,
    PlatformFamily,
    VirtualizationInfo,
)
from sofia.machine.observation import ObservationState
from sofia.machine.refresh import MachineInventoryRefresher


class StubMachineDiscovery:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error

    def discover(self):
        if self.error is not None:
            raise self.error

        return self.result


class StubHardwareDiscovery:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error

    def discover(self):
        if self.error is not None:
            raise self.error

        return self.result


def _machine_result(
    *,
    machine_id: str = "machine-1",
    hostname: str = "test-host",
) -> MachineDiscoveryResult:
    observed_at = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

    return MachineDiscoveryResult(
        identity=MachineIdentity(
            machine_id=machine_id,
            hostname=hostname,
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
            name="Windows 11",
            version="10",
            architecture="AMD64",
            kernel="test-kernel",
        ),
        observed_at=observed_at,
        source="test-machine-discovery",
    )


def _hardware_result(
    *,
    cpu: str | None = "Test CPU",
) -> HardwareDiscoveryResult:
    return HardwareDiscoveryResult(
        hardware=HardwareProfile(
            cpu=cpu,
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        source="test-hardware-discovery",
    )


def test_refresh_creates_verified_inventory_observation() -> None:
    machine = _machine_result()
    hardware = _hardware_result()

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(hardware),
    )
    inventory = MachineInventory()

    result = refresher.refresh(inventory)

    assert result.succeeded is True
    assert result.error is None
    assert result.observation is not None
    assert result.observation.state is ObservationState.VERIFIED
    assert result.observation.machine_id == "machine-1"
    assert result.observation.profile.hardware.cpu == "Test CPU"

    current = inventory.get("machine-1")

    assert current is not None
    assert current == result.observation
    assert inventory.history("machine-1") == (
        result.observation,
    )


def test_refresh_preserves_unknown_hardware_values() -> None:
    machine = _machine_result()
    hardware = _hardware_result(cpu=None)

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(hardware),
    )
    inventory = MachineInventory()

    result = refresher.refresh(inventory)

    assert result.succeeded is True
    assert result.observation is not None
    assert result.observation.profile.hardware.cpu is None


def test_hardware_failure_invalidates_known_machine() -> None:
    machine = _machine_result()

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(
            error=RuntimeError("hardware unavailable")
        ),
    )
    inventory = MachineInventory()

    initial = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(_hardware_result()),
    ).refresh(inventory)

    assert initial.succeeded is True

    result = refresher.refresh(inventory)

    assert result.succeeded is False
    assert result.machine_discovery_succeeded is True
    assert result.hardware_discovery_succeeded is False
    assert result.observation is None
    assert result.error is not None

    current = inventory.get("machine-1")

    assert current is not None
    assert current.state is ObservationState.UNKNOWN

    history = inventory.history("machine-1")

    assert len(history) == 2
    assert history[0].state is ObservationState.VERIFIED
    assert history[1].state is ObservationState.UNKNOWN


def test_machine_discovery_failure_does_not_fabricate_identity() -> None:
    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(
            error=RuntimeError("machine discovery unavailable")
        ),
        StubHardwareDiscovery(_hardware_result()),
    )
    inventory = MachineInventory()

    result = refresher.refresh(inventory)

    assert result.succeeded is False
    assert result.machine_discovery_succeeded is False
    assert result.hardware_discovery_succeeded is False
    assert result.observation is None
    assert result.error is not None
    assert len(inventory) == 0


def test_machine_discovery_failure_can_invalidate_known_machine() -> None:
    machine = _machine_result()

    inventory = MachineInventory()

    MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(_hardware_result()),
    ).refresh(inventory)

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(
            error=RuntimeError("machine discovery unavailable")
        ),
        StubHardwareDiscovery(_hardware_result()),
    )

    result = refresher.refresh(
        inventory,
        known_machine_id="machine-1",
    )

    assert result.succeeded is False
    assert result.observation is None

    current = inventory.get("machine-1")

    assert current is not None
    assert current.state is ObservationState.UNKNOWN


def test_machine_discovery_failure_without_known_id_does_not_mutate_inventory() -> None:
    machine = _machine_result()

    inventory = MachineInventory()

    initial = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(_hardware_result()),
    ).refresh(inventory)

    assert initial.succeeded is True

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(
            error=RuntimeError("machine discovery unavailable")
        ),
        StubHardwareDiscovery(_hardware_result()),
    )

    result = refresher.refresh(inventory)

    assert result.succeeded is False

    current = inventory.get("machine-1")

    assert current is not None
    assert current.state is ObservationState.VERIFIED


def test_refresh_detects_hardware_change() -> None:
    machine = _machine_result()

    inventory = MachineInventory()

    first = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(
            _hardware_result(cpu="CPU A")
        ),
    ).refresh(inventory)

    second = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(
            _hardware_result(cpu="CPU B")
        ),
    ).refresh(inventory)

    assert first.succeeded is True
    assert second.succeeded is True
    assert second.inventory_change is not None
    assert (
        second.inventory_change.hardware_changed
        is True
    )

    assert inventory.get(
        "machine-1"
    ).profile.hardware.cpu == "CPU B"

    history = inventory.history("machine-1")

    assert len(history) == 2
    assert history[0].profile.hardware.cpu == "CPU A"
    assert history[1].profile.hardware.cpu == "CPU B"


def test_refresh_reverification_does_not_duplicate_unchanged_history() -> None:
    machine = _machine_result()
    hardware = _hardware_result()

    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(machine),
        StubHardwareDiscovery(hardware),
    )
    inventory = MachineInventory()

    first = refresher.refresh(inventory)
    second = refresher.refresh(inventory)

    assert first.succeeded is True
    assert second.succeeded is True

    assert len(inventory.history("machine-1")) == 1
    assert inventory.get("machine-1").state is (
        ObservationState.VERIFIED
    )


def test_refresh_rejects_invalid_inventory() -> None:
    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(_machine_result()),
        StubHardwareDiscovery(_hardware_result()),
    )

    with pytest.raises(TypeError):
        refresher.refresh(object())


def test_refresh_rejects_empty_known_machine_id() -> None:
    refresher = MachineInventoryRefresher(
        StubMachineDiscovery(_machine_result()),
        StubHardwareDiscovery(_hardware_result()),
    )

    with pytest.raises(ValueError):
        refresher.refresh(
            MachineInventory(),
            known_machine_id=" ",
        )