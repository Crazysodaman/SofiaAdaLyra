from datetime import datetime, timezone
import json

import pytest

from sofia.machine.inventory import MachineInventory
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
    ObservationState,
)
from sofia.machine.persistence import (
    MachineInventoryPersistence,
    deserialize_inventory,
    serialize_inventory,
)


TIMESTAMP = datetime(
    2026,
    9,
    19,
    12,
    0,
    tzinfo=timezone.utc,
)


def _profile(
    *,
    machine_id: str = "machine-1",
    hostname: str = "test-host",
    cpu: str | None = "Test CPU",
) -> MachineProfile:
    return MachineProfile(
        identity=MachineIdentity(
            machine_id=machine_id,
            hostname=hostname,
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
            name="Windows",
            version="11",
            architecture="x86_64",
            kernel="10.0",
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
            hypervisor=None,
            platform=None,
        ),
        hardware=HardwareProfile(
            cpu=cpu,
            gpu=("Test GPU",),
            memory_bytes=16 * 1024**3,
        ),
        verification=MachineVerification(
            first_observed_at=TIMESTAMP,
            last_verified_at=TIMESTAMP,
            source="machine-discovery",
        ),
    )


def _observation(
    *,
    machine_id: str = "machine-1",
    hostname: str = "test-host",
    cpu: str | None = "Test CPU",
    state: ObservationState = ObservationState.VERIFIED,
    verified_at: datetime = TIMESTAMP,
) -> MachineObservation:
    return MachineObservation(
        profile=_profile(
            machine_id=machine_id,
            hostname=hostname,
            cpu=cpu,
        ),
        observed_at=TIMESTAMP,
        verified_at=verified_at,
        provenance=ObservationProvenance(
            source_type=ObservationSource.MACHINE_DISCOVERY,
            source_name="windows",
        ),
        state=state,
    )


def test_serialize_empty_inventory() -> None:
    payload = serialize_inventory(
        MachineInventory()
    )

    assert payload["schema_version"] == 1
    assert payload["current"] == {}
    assert payload["history"] == {}


def test_serialize_inventory_preserves_current_observation() -> None:
    inventory = MachineInventory()
    observation = _observation()

    inventory.record(observation)

    payload = serialize_inventory(inventory)

    assert (
        payload["current"]["machine-1"]["machine_id"]
        == "machine-1"
    )

    assert (
        payload["current"]["machine-1"]["state"]
        == ObservationState.VERIFIED.value
    )

    assert (
        payload["current"]["machine-1"]["observed_at"]
        == TIMESTAMP.isoformat()
    )


def test_serialize_inventory_preserves_history() -> None:
    inventory = MachineInventory()

    inventory.record(_observation())
    inventory.record(
        _observation(cpu="Different CPU")
    )

    payload = serialize_inventory(inventory)

    assert (
        len(payload["history"]["machine-1"])
        == 2
    )

    assert (
        payload["history"]["machine-1"][1]
        ["profile"]["hardware"]["cpu"]
        == "Different CPU"
    )


def test_deserialize_empty_inventory() -> None:
    restored = deserialize_inventory(
        {
            "schema_version": 1,
            "current": {},
            "history": {},
        }
    )

    assert isinstance(
        restored,
        MachineInventory,
    )

    assert len(restored) == 0


def test_round_trip_preserves_inventory_semantics() -> None:
    inventory = MachineInventory()

    first = _observation()
    changed = _observation(
        cpu="Different CPU"
    )

    inventory.record(first)
    inventory.record(changed)

    payload = serialize_inventory(
        inventory
    )

    restored = deserialize_inventory(
        payload
    )

    assert (
        restored.machine_ids()
        == inventory.machine_ids()
    )

    assert (
        restored.get("machine-1")
        == inventory.get("machine-1")
    )

    assert (
        restored.history("machine-1")
        == inventory.history("machine-1")
    )


def test_round_trip_preserves_all_observation_metadata() -> None:
    observation = _observation(
        state=ObservationState.STALE
    )

    inventory = MachineInventory()
    inventory.record(observation)

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    result = restored.get(
        "machine-1"
    )

    assert result is not None
    assert (
        result.observed_at
        == observation.observed_at
    )
    assert (
        result.verified_at
        == observation.verified_at
    )
    assert (
        result.provenance
        == observation.provenance
    )
    assert (
        result.state
        is ObservationState.STALE
    )
    assert (
        result.profile
        == observation.profile
    )


def test_round_trip_preserves_multiple_machines() -> None:
    inventory = MachineInventory()

    first = _observation(
        machine_id="machine-1",
        hostname="host-1",
    )

    second = _observation(
        machine_id="machine-2",
        hostname="host-2",
    )

    inventory.record(first)
    inventory.record(second)

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    assert restored.machine_ids() == (
        "machine-1",
        "machine-2",
    )

    assert (
        restored.get("machine-1")
        == first
    )

    assert (
        restored.get("machine-2")
        == second
    )


def test_file_persistence_round_trip(
    tmp_path,
) -> None:
    inventory = MachineInventory()
    inventory.record(
        _observation()
    )

    path = (
        tmp_path
        / "machine-inventory.json"
    )

    store = MachineInventoryPersistence(
        path
    )

    store.save(inventory)

    restored = store.load()

    assert (
        restored.get("machine-1")
        == inventory.get("machine-1")
    )

    assert (
        restored.history("machine-1")
        == inventory.history("machine-1")
    )


def test_file_persistence_creates_parent_directory(
    tmp_path,
) -> None:
    inventory = MachineInventory()
    inventory.record(
        _observation()
    )

    path = (
        tmp_path
        / "nested"
        / "machine-inventory.json"
    )

    MachineInventoryPersistence(
        path
    ).save(inventory)

    assert path.is_file()


def test_malformed_schema_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        deserialize_inventory(
            {
                "schema_version": 999,
                "current": {},
                "history": {},
            }
        )


def test_malformed_observation_is_rejected() -> None:
    payload = serialize_inventory(
        MachineInventory()
    )

    payload["current"][
        "machine-1"
    ] = {}

    with pytest.raises(ValueError):
        deserialize_inventory(payload)


def test_persistence_does_not_add_authority_or_capability_state(
    tmp_path,
) -> None:
    inventory = MachineInventory()

    inventory.record(
        _observation()
    )

    path = (
        tmp_path
        / "inventory.json"
    )

    MachineInventoryPersistence(
        path
    ).save(inventory)

    raw = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert "authority" not in raw
    assert "capabilities" not in raw
    assert "permissions" not in raw