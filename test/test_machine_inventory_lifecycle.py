from datetime import datetime, timedelta, timezone

import pytest

from sofia.machine.comparison import (
    ObservationChange,
    compare_machine_observations,
)
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
    os_family: PlatformFamily = PlatformFamily.WINDOWS,
    cpu: str | None = "Test CPU",
) -> MachineProfile:
    return MachineProfile(
        identity=MachineIdentity(
            machine_id=machine_id,
            hostname=hostname,
        ),
        operating_system=OperatingSystemInfo(
            family=os_family,
            name="Test OS",
            version="1.0",
            architecture="x86_64",
            kernel="test-kernel",
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        hardware=HardwareProfile(
            cpu=cpu,
        ),
        verification=MachineVerification(
            first_observed_at=TIMESTAMP,
            last_verified_at=TIMESTAMP,
            source="machine-discovery",
        ),
    )


def _observation(
    *,
    profile: MachineProfile | None = None,
    state: ObservationState = ObservationState.VERIFIED,
    verified_at: datetime = TIMESTAMP,
) -> MachineObservation:
    return MachineObservation(
        profile=profile or _profile(),
        observed_at=TIMESTAMP,
        verified_at=verified_at,
        provenance=ObservationProvenance(
            source_type=ObservationSource.MACHINE_DISCOVERY,
            source_name="windows",
        ),
        state=state,
    )


def test_state_only_unknown_transition_is_detected() -> None:
    previous = _observation()

    current = _observation(
        state=ObservationState.UNKNOWN,
    )

    comparison = compare_machine_observations(
        previous,
        current,
    )

    assert comparison.change is (
        ObservationChange.BECAME_UNKNOWN
    )


def test_state_only_stale_transition_is_detected() -> None:
    previous = _observation()

    current = _observation(
        state=ObservationState.STALE,
    )

    comparison = compare_machine_observations(
        previous,
        current,
    )

    assert comparison.change is (
        ObservationChange.BECAME_STALE
    )


def test_stale_to_verified_transition_is_detected() -> None:
    previous = _observation(
        state=ObservationState.STALE,
    )

    current = _observation(
        state=ObservationState.VERIFIED,
        verified_at=TIMESTAMP + timedelta(hours=1),
    )

    comparison = compare_machine_observations(
        previous,
        current,
    )

    assert comparison.change is (
        ObservationChange.BECAME_VERIFIED
    )


def test_inventory_mark_stale_records_history() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    comparison = inventory.mark_stale(
        "machine-1"
    )

    assert comparison is not None
    assert comparison.change is (
        ObservationChange.BECAME_STALE
    )

    current = inventory.get("machine-1")

    assert current is not None
    assert current.state is ObservationState.STALE

    history = inventory.history("machine-1")

    assert history == (
        original,
        current,
    )


def test_inventory_invalidate_records_unknown_state() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    comparison = inventory.invalidate(
        "machine-1"
    )

    assert comparison is not None
    assert comparison.change is (
        ObservationChange.BECAME_UNKNOWN
    )

    current = inventory.get("machine-1")

    assert current is not None
    assert current.state is ObservationState.UNKNOWN

    assert len(
        inventory.history("machine-1")
    ) == 2


def test_inventory_missing_machine_can_be_invalidated() -> None:
    inventory = MachineInventory()

    assert inventory.invalidate(
        "missing-machine"
    ) is None

    assert inventory.mark_stale(
        "missing-machine"
    ) is None


def test_unknown_machine_can_become_known_again() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)
    inventory.invalidate("machine-1")

    restored = _observation(
        verified_at=TIMESTAMP + timedelta(hours=1),
    )

    comparison = inventory.record(restored)

    assert comparison is not None
    assert comparison.change is (
        ObservationChange.BECAME_KNOWN
    )

    assert inventory.get("machine-1") == restored


def test_contradiction_is_recorded_without_replacing_current() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    conflicting = _observation(
        profile=_profile(
            cpu="Different CPU",
        )
    )

    comparison = inventory.record_contradiction(
        conflicting
    )

    assert comparison.change is (
        ObservationChange.CONTRADICTED
    )

    assert inventory.get("machine-1") == original

    history = inventory.history("machine-1")

    assert history[0] == original
    assert history[1].state is (
        ObservationState.CONTRADICTED
    )
    assert history[1].profile.hardware.cpu == (
        "Different CPU"
    )


def test_contradiction_requires_existing_machine() -> None:
    inventory = MachineInventory()

    with pytest.raises(
        ValueError,
        match="unknown machine",
    ):
        inventory.record_contradiction(
            _observation()
        )


def test_contradiction_requires_actual_difference() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    with pytest.raises(
        ValueError,
        match="must differ",
    ):
        inventory.record_contradiction(
            _observation()
        )


def test_reverification_updates_current_without_history_duplicate() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    later = TIMESTAMP + timedelta(hours=2)

    reverified = _observation(
        verified_at=later,
    )

    comparison = inventory.record(
        reverified
    )

    assert comparison is not None
    assert comparison.change is (
        ObservationChange.NO_CHANGE
    )

    current = inventory.get("machine-1")

    assert current is not None
    assert current.verified_at == later

    history = inventory.history("machine-1")

    assert len(history) == 1
    assert history[0].verified_at == TIMESTAMP


def test_round_trip_preserves_reverification_without_history_duplicate() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    later = TIMESTAMP + timedelta(hours=2)

    inventory.record(
        _observation(
            verified_at=later,
        )
    )

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    current = restored.get("machine-1")

    assert current is not None
    assert current.verified_at == later

    history = restored.history(
        "machine-1"
    )

    assert len(history) == 1
    assert history[0].verified_at == TIMESTAMP


def test_round_trip_preserves_state_transitions() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)
    inventory.mark_stale("machine-1")
    inventory.invalidate("machine-1")

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    current = restored.get("machine-1")

    assert current is not None
    assert current.state is (
        ObservationState.UNKNOWN
    )

    states = tuple(
        observation.state
        for observation in restored.history(
            "machine-1"
        )
    )

    assert states == (
        ObservationState.VERIFIED,
        ObservationState.STALE,
        ObservationState.UNKNOWN,
    )


def test_round_trip_preserves_contradictory_evidence() -> None:
    inventory = MachineInventory()
    original = _observation()

    inventory.record(original)

    inventory.record_contradiction(
        _observation(
            profile=_profile(
                cpu="Conflicting CPU",
            )
        )
    )

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    assert restored.get(
        "machine-1"
    ) == original

    history = restored.history(
        "machine-1"
    )

    assert len(history) == 2
    assert history[-1].state is (
        ObservationState.CONTRADICTED
    )


def test_save_load_save_is_semantically_stable() -> None:
    inventory = MachineInventory()

    inventory.record(
        _observation()
    )

    inventory.record(
        _observation(
            verified_at=TIMESTAMP + timedelta(
                minutes=30
            ),
        )
    )

    inventory.mark_stale(
        "machine-1"
    )

    inventory.record_contradiction(
        _observation(
            profile=_profile(
                cpu="Conflicting CPU",
            )
        )
    )

    first_payload = serialize_inventory(
        inventory
    )

    restored = deserialize_inventory(
        first_payload
    )

    second_payload = serialize_inventory(
        restored
    )

    assert second_payload == first_payload


def test_round_trip_preserves_multiple_machine_histories() -> None:
    inventory = MachineInventory()

    inventory.record(
        _observation(
            profile=_profile(
                machine_id="machine-1",
                hostname="host-1",
            )
        )
    )

    inventory.record(
        _observation(
            profile=_profile(
                machine_id="machine-2",
                hostname="host-2",
            )
        )
    )

    inventory.mark_stale(
        "machine-1"
    )

    inventory.invalidate(
        "machine-2"
    )

    restored = deserialize_inventory(
        serialize_inventory(inventory)
    )

    assert restored.machine_ids() == (
        "machine-1",
        "machine-2",
    )

    machine_one = restored.get(
        "machine-1"
    )
    machine_two = restored.get(
        "machine-2"
    )

    assert machine_one is not None
    assert machine_two is not None

    assert machine_one.state is (
        ObservationState.STALE
    )
    assert machine_two.state is (
        ObservationState.UNKNOWN
    )


def test_contradiction_does_not_change_current_authority() -> None:
    inventory = MachineInventory()

    original = _observation(
        profile=_profile(
            cpu="Known CPU",
        )
    )

    inventory.record(original)

    conflicting = _observation(
        profile=_profile(
            cpu="Conflicting CPU",
        )
    )

    inventory.record_contradiction(
        conflicting
    )

    current = inventory.get(
        "machine-1"
    )

    assert current is not None
    assert current.profile.hardware.cpu == (
        "Known CPU"
    )

    assert (
        inventory.history("machine-1")[-1]
        .profile.hardware.cpu
        == "Conflicting CPU"
    )


def test_contradicted_evidence_can_later_be_reconciled() -> None:
    inventory = MachineInventory()

    original = _observation(
        profile=_profile(
            cpu="Known CPU",
        )
    )

    inventory.record(original)

    conflicting = _observation(
        profile=_profile(
            cpu="Conflicting CPU",
        )
    )

    inventory.record_contradiction(
        conflicting
    )

    verified = _observation(
        profile=_profile(
            cpu="Conflicting CPU",
        ),
        verified_at=TIMESTAMP + timedelta(
            hours=1
        ),
    )

    comparison = inventory.record(
        verified
    )

    assert comparison is not None
    assert comparison.change is (
        ObservationChange.CHANGED
    )

    current = inventory.get(
        "machine-1"
    )

    assert current == verified
    assert current.state is (
        ObservationState.VERIFIED
    )