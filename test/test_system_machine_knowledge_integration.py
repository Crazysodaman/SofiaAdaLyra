from datetime import datetime, timezone

import pytest

from sofia.machine import (
    HardwareProfile,
    MachineIdentity,
    MachineInventory,
    MachineObservation,
    MachineProfile,
    MachineVerification,
    ObservationProvenance,
    ObservationSource,
    OperatingSystemInfo,
    PlatformFamily,
    VirtualizationInfo,
)
from sofia.system import (
    SystemCapability,
    SystemCapabilityKnowledge,
    SystemCapabilityMachineKnowledge,
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def _machine(
    machine_id: str = "venus",
) -> MachineObservation:
    observed_at = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

    profile = MachineProfile(
        identity=MachineIdentity(
            machine_id=machine_id,
            hostname="venus",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
            name="Windows 11",
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        hardware=HardwareProfile(),
        verification=MachineVerification(
            first_observed_at=observed_at,
            last_verified_at=observed_at,
            source="test",
        ),
    )

    return MachineObservation(
        profile=profile,
        observed_at=observed_at,
        verified_at=observed_at,
        provenance=ObservationProvenance(
            source_type=ObservationSource.MACHINE_DISCOVERY,
            source_name="test",
        ),
    )


def _result(
    capability: SystemCapabilityName,
    evidence: dict,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=SystemCapabilityResultKind.SUCCESS,
        evidence=evidence,
        observed_at=datetime(
            2026,
            9,
            19,
            12,
            1,
            tzinfo=timezone.utc,
        ),
        backend_name="test-backend",
    )


def _service_capability() -> SystemCapability:
    return SystemCapability(
        name=SystemCapabilityName.SERVICE_INSPECT,
        description="Inspect service state.",
    )


def test_association_requires_known_machine() -> None:
    inventory = MachineInventory()
    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    with pytest.raises(KeyError):
        integration.associate("venus")


def test_association_accepts_known_machine() -> None:
    inventory = MachineInventory()
    observation = _machine()

    inventory.record(observation)

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    association = integration.associate("venus")

    assert association.machine is observation
    assert (
        association.system_capability_knowledge
        is knowledge
    )


def test_record_requires_known_machine() -> None:
    inventory = MachineInventory()
    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    result = _result(
        SystemCapabilityName.SYSTEM_INSPECT,
        {"hostname": "venus"},
    )

    with pytest.raises(KeyError):
        integration.record(
            "venus",
            result,
        )

    assert knowledge.machine_ids() == ()


def test_record_adds_dynamic_knowledge_without_mutating_machine() -> None:
    inventory = MachineInventory()
    observation = _machine()

    inventory.record(observation)

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    result = _result(
        SystemCapabilityName.SYSTEM_INSPECT,
        {"hostname": "venus"},
    )

    integration.record(
        "venus",
        result,
    )

    current_machine = inventory.get("venus")

    assert current_machine is observation
    assert current_machine.profile is observation.profile

    record = knowledge.get(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert record.machine_id == "venus"
    assert record.evidence["hostname"] == "venus"


def test_dynamic_failure_does_not_invalidate_machine() -> None:
    inventory = MachineInventory()
    observation = _machine()

    inventory.record(observation)

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    failure = SystemCapabilityResult(
        capability=SystemCapabilityName.NETWORK_INSPECT,
        kind=SystemCapabilityResultKind.FAILED,
        error="inspection failed",
    )

    integration.record(
        "venus",
        failure,
    )

    current_machine = inventory.get("venus")

    assert current_machine is not None
    assert current_machine.state.value == "verified"

    record = knowledge.get(
        "venus",
        SystemCapabilityName.NETWORK_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.FAILED
    assert record.error == "inspection failed"


def test_machine_state_does_not_change_dynamic_capability_state() -> None:
    inventory = MachineInventory()
    observation = _machine()

    inventory.record(observation)

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    inventory.mark_stale("venus")

    current = integration.current("venus")

    assert len(current) == 1
    assert (
        current[0].kind
        is SystemCapabilityResultKind.SUCCESS
    )


def test_current_returns_canonical_capability_order() -> None:
    inventory = MachineInventory()
    inventory.record(_machine())

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.SERVICE_INSPECT,
            {"services": []},
        ),
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    records = integration.current("venus")

    assert tuple(
        record.capability
        for record in records
    ) == (
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.SYSTEM_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    )


def test_current_capability_returns_only_requested_capability() -> None:
    inventory = MachineInventory()
    inventory.record(_machine())

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
    )

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert (
        record.capability
        is SystemCapabilityName.SYSTEM_INSPECT
    )


def test_machine_inventory_is_not_modified_by_record() -> None:
    inventory = MachineInventory()
    observation = _machine()

    inventory.record(observation)

    before = inventory.history("venus")

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        SystemCapabilityKnowledge(),
    )

    integration.record(
        "venus",
        _result(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    after = inventory.history("venus")

    assert after == before
    assert inventory.get("venus") is observation


def test_invalid_machine_id_is_rejected() -> None:
    inventory = MachineInventory()
    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    with pytest.raises(TypeError):
        integration.associate(123)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        integration.associate("   ")


def test_invalid_dependencies_are_rejected() -> None:
    with pytest.raises(TypeError):
        SystemCapabilityMachineKnowledge(
            object(),  # type: ignore[arg-type]
            SystemCapabilityKnowledge(),
        )

    with pytest.raises(TypeError):
        SystemCapabilityMachineKnowledge(
            MachineInventory(),
            object(),  # type: ignore[arg-type]
        )


def test_record_all_requires_tuple() -> None:
    inventory = MachineInventory()
    inventory.record(_machine())

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        SystemCapabilityKnowledge(),
    )

    with pytest.raises(TypeError):
        integration.record_all(
            "venus",
            [],  # type: ignore[arg-type]
        )


def test_record_rejects_invalid_result_before_mutation() -> None:
    inventory = MachineInventory()
    inventory.record(_machine())

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    with pytest.raises(TypeError):
        integration.record(
            "venus",
            object(),  # type: ignore[arg-type]
        )

    assert knowledge.machine_ids() == ()


def test_record_all_preserves_machine_scope() -> None:
    inventory = MachineInventory()
    inventory.record(_machine())

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    results = (
        _result(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
        _result(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    updates = integration.record_all(
        "venus",
        results,
    )

    assert len(updates) == 2
    assert knowledge.machine_ids() == ("venus",)

    records = integration.current("venus")

    assert len(records) == 2


def test_service_capability_definition_remains_canonical() -> None:
    capability = _service_capability()

    assert capability.name is SystemCapabilityName.SERVICE_INSPECT
    assert capability.description == "Inspect service state."