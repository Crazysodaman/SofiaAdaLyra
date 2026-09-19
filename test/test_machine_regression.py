from datetime import datetime, timezone

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
from sofia.machine.observation import (
    ObservationState,
)
from sofia.machine.persistence import (
    MachineInventoryPersistence,
    deserialize_inventory,
    serialize_inventory,
)
from sofia.machine.refresh import MachineInventoryRefresher


class StubMachineDiscovery:
    def __init__(self, result):
        self._result = result

    def discover(self):
        return self._result


class StubHardwareDiscovery:
    def __init__(self, result):
        self._result = result

    def discover(self):
        return self._result


def _machine_result(
    *,
    machine_id: str = "regression-machine",
) -> MachineDiscoveryResult:
    timestamp = datetime(
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
            hostname="regression-host",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
            name="Windows 11",
            version="10",
            architecture="AMD64",
            kernel="test-kernel",
        ),
        observed_at=timestamp,
        source="regression-machine-discovery",
    )


def _hardware_result(
    *,
    cpu: str | None = "Regression CPU",
    gpu: tuple[str, ...] = (),
    memory_bytes: int | None = None,
) -> HardwareDiscoveryResult:
    return HardwareDiscoveryResult(
        hardware=HardwareProfile(
            cpu=cpu,
            gpu=gpu,
            memory_bytes=memory_bytes,
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        source="regression-hardware-discovery",
    )


def _refresh(
    inventory: MachineInventory,
    *,
    cpu: str | None = "Regression CPU",
    gpu: tuple[str, ...] = (),
    memory_bytes: int | None = None,
) -> None:
    MachineInventoryRefresher(
        StubMachineDiscovery(_machine_result()),
        StubHardwareDiscovery(
            _hardware_result(
                cpu=cpu,
                gpu=gpu,
                memory_bytes=memory_bytes,
            )
        ),
    ).refresh(inventory)


def test_real_discovery_shaped_profile_round_trips_through_inventory() -> None:
    inventory = MachineInventory()

    _refresh(
        inventory,
        cpu="AMD Ryzen Regression CPU",
        gpu=("NVIDIA Regression GPU",),
        memory_bytes=32 * 1024**3,
    )

    payload = serialize_inventory(inventory)
    restored = deserialize_inventory(payload)

    observation = restored.get("regression-machine")

    assert observation is not None
    assert observation.state is ObservationState.VERIFIED
    assert observation.profile.hardware.cpu == (
        "AMD Ryzen Regression CPU"
    )
    assert observation.profile.hardware.gpu == (
        "NVIDIA Regression GPU",
    )
    assert observation.profile.hardware.memory_bytes == (
        32 * 1024**3
    )


def test_unknown_hardware_survives_persistence() -> None:
    inventory = MachineInventory()

    _refresh(
        inventory,
        cpu=None,
        gpu=(),
        memory_bytes=None,
    )

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    observation = restored.get("regression-machine")

    assert observation is not None
    assert observation.profile.hardware.cpu is None
    assert observation.profile.hardware.gpu == ()
    assert observation.profile.hardware.memory_bytes is None


def test_hardware_change_becomes_historical_evidence() -> None:
    inventory = MachineInventory()

    _refresh(
        inventory,
        cpu="CPU A",
    )
    _refresh(
        inventory,
        cpu="CPU B",
    )

    current = inventory.get("regression-machine")
    history = inventory.history("regression-machine")

    assert current is not None
    assert current.profile.hardware.cpu == "CPU B"
    assert len(history) == 2
    assert history[0].profile.hardware.cpu == "CPU A"
    assert history[1].profile.hardware.cpu == "CPU B"


def test_stale_and_unknown_states_survive_round_trip() -> None:
    inventory = MachineInventory()

    _refresh(inventory)

    inventory.mark_stale("regression-machine")
    inventory.invalidate("regression-machine")

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    current = restored.get("regression-machine")
    history = restored.history("regression-machine")

    assert current is not None
    assert current.state is ObservationState.UNKNOWN

    assert [
        observation.state
        for observation in history
    ] == [
        ObservationState.VERIFIED,
        ObservationState.STALE,
        ObservationState.UNKNOWN,
    ]


def test_contradiction_does_not_replace_current_truth() -> None:
    inventory = MachineInventory()

    _refresh(
        inventory,
        cpu="Known CPU",
    )

    contradiction = _refresh_contradiction(
        inventory,
        cpu="Contradictory CPU",
    )

    assert contradiction is not None

    current = inventory.get("regression-machine")

    assert current is not None
    assert current.profile.hardware.cpu == "Known CPU"
    assert current.state is ObservationState.VERIFIED

    history = inventory.history("regression-machine")

    assert history[-1].state is ObservationState.CONTRADICTED
    assert history[-1].profile.hardware.cpu == (
        "Contradictory CPU"
    )


def _refresh_contradiction(
    inventory: MachineInventory,
    *,
    cpu: str,
):
    from sofia.machine.observation import (
        MachineObservation,
        ObservationProvenance,
        ObservationSource,
    )
    from sofia.machine.model import MachineProfile, MachineVerification

    machine = _machine_result()

    hardware = _hardware_result(cpu=cpu)

    profile = MachineProfile(
        identity=machine.identity,
        operating_system=machine.operating_system,
        virtualization=hardware.virtualization,
        hardware=hardware.hardware,
        verification=MachineVerification(
            first_observed_at=machine.observed_at,
            last_verified_at=machine.observed_at,
            source=hardware.source,
        ),
    )

    observation = MachineObservation(
        profile=profile,
        observed_at=machine.observed_at,
        verified_at=machine.observed_at,
        provenance=ObservationProvenance(
            source_type=ObservationSource.MACHINE_DISCOVERY,
            source_name="regression-contradiction",
        ),
        state=ObservationState.VERIFIED,
    )

    return inventory.record_contradiction(
        observation
    )


def test_save_load_save_is_semantically_stable(tmp_path) -> None:
    inventory = MachineInventory()

    _refresh(
        inventory,
        cpu="Stable CPU",
        gpu=("Stable GPU",),
        memory_bytes=16 * 1024**3,
    )

    path_a = tmp_path / "inventory-a.json"
    path_b = tmp_path / "inventory-b.json"

    persistence_a = MachineInventoryPersistence(path_a)
    persistence_a.save(inventory)

    restored = persistence_a.load()

    persistence_b = MachineInventoryPersistence(path_b)
    persistence_b.save(restored)

    assert persistence_a.load() == persistence_b.load()