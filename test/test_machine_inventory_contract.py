from datetime import datetime, timedelta, timezone

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


def _profile(
    *,
    machine_id: str = "machine-1",
    hostname: str = "test-host",
    os_family: PlatformFamily = PlatformFamily.WINDOWS,
    cpu: str | None = "Test CPU",
) -> MachineProfile:
    timestamp = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

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
            first_observed_at=timestamp,
            last_verified_at=timestamp,
            source="machine-discovery",
        ),
    )


def _observation(
    *,
    profile: MachineProfile | None = None,
    observed_at: datetime | None = None,
    verified_at: datetime | None = None,
    state: ObservationState = ObservationState.VERIFIED,
) -> MachineObservation:
    timestamp = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

    return MachineObservation(
        profile=profile or _profile(),
        observed_at=observed_at or timestamp,
        verified_at=verified_at or timestamp,
        provenance=ObservationProvenance(
            source_type=ObservationSource.MACHINE_DISCOVERY,
            source_name="windows",
        ),
        state=state,
    )


def test_observation_records_provenance_and_times() -> None:
    observation = _observation()

    assert observation.provenance.source_type is (
        ObservationSource.MACHINE_DISCOVERY
    )
    assert observation.provenance.source_name == "windows"
    assert observation.observed_at == observation.verified_at
    assert observation.state is ObservationState.VERIFIED


def test_observation_rejects_verification_before_observation() -> None:
    observed_at = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )
    verified_at = observed_at - timedelta(seconds=1)

    try:
        _observation(
            observed_at=observed_at,
            verified_at=verified_at,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected verification-before-observation to fail."
        )


def test_observation_can_become_stale_or_unknown() -> None:
    observation = _observation()

    stale = observation.with_state(
        ObservationState.STALE
    )
    unknown = observation.with_state(
        ObservationState.UNKNOWN
    )

    assert stale.state is ObservationState.STALE
    assert unknown.state is ObservationState.UNKNOWN
    assert observation.profile == stale.profile
    assert observation.profile == unknown.profile


def test_observation_reverification_updates_verification_time() -> None:
    observation = _observation()

    later = observation.verified_at + timedelta(hours=1)
    reverified = observation.reverified(later)

    assert reverified.observed_at == observation.observed_at
    assert reverified.verified_at == later
    assert reverified.state is ObservationState.VERIFIED
    assert reverified.profile == observation.profile


def test_comparison_detects_no_change() -> None:
    first = _observation()
    second = _observation(
        verified_at=first.verified_at + timedelta(minutes=5)
    )

    comparison = compare_machine_observations(
        first,
        second,
    )

    assert comparison.change is ObservationChange.NO_CHANGE
    assert comparison.identity_changed is False
    assert comparison.operating_system_changed is False
    assert comparison.virtualization_changed is False
    assert comparison.hardware_changed is False


def test_comparison_detects_hardware_change() -> None:
    first = _observation()

    second = _observation(
        profile=_profile(cpu="Different CPU")
    )

    comparison = compare_machine_observations(
        first,
        second,
    )

    assert comparison.change is ObservationChange.CHANGED
    assert comparison.hardware_changed is True


def test_comparison_detects_operating_system_change() -> None:
    first = _observation()

    second = _observation(
        profile=_profile(
            os_family=PlatformFamily.LINUX
        )
    )

    comparison = compare_machine_observations(
        first,
        second,
    )

    assert comparison.change is ObservationChange.CHANGED
    assert comparison.operating_system_changed is True


def test_inventory_records_first_observation() -> None:
    inventory = MachineInventory()
    observation = _observation()

    result = inventory.record(observation)

    assert result is None
    assert inventory.get("machine-1") == observation
    assert inventory.history("machine-1") == (observation,)
    assert len(inventory) == 1


def test_inventory_does_not_duplicate_unchanged_history() -> None:
    inventory = MachineInventory()
    first = _observation()

    inventory.record(first)

    later = first.verified_at + timedelta(hours=1)
    second = _observation(
        verified_at=later
    )

    result = inventory.record(second)

    assert result is not None
    assert result.change is ObservationChange.NO_CHANGE

    assert len(inventory.history("machine-1")) == 1
    assert inventory.get("machine-1").verified_at == later


def test_inventory_records_changed_state() -> None:
    inventory = MachineInventory()
    first = _observation()

    inventory.record(first)

    second = _observation(
        profile=_profile(cpu="Different CPU")
    )

    result = inventory.record(second)

    assert result is not None
    assert result.change is ObservationChange.CHANGED
    assert inventory.get("machine-1") == second
    assert inventory.history("machine-1") == (
        first,
        second,
    )


def test_inventory_keeps_machines_separate() -> None:
    inventory = MachineInventory()

    first = _observation(
        profile=_profile(machine_id="machine-1")
    )
    second = _observation(
        profile=_profile(machine_id="machine-2")
    )

    inventory.record(first)
    inventory.record(second)

    assert inventory.machine_ids() == (
        "machine-1",
        "machine-2",
    )
    assert len(inventory) == 2


def test_inventory_contains_no_authority_or_capability_state() -> None:
    inventory = MachineInventory()
    observation = _observation()

    inventory.record(observation)

    assert not hasattr(inventory, "authority")
    assert not hasattr(inventory, "capabilities")
    assert not hasattr(inventory, "permissions")