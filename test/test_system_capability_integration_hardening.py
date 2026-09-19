from datetime import datetime, timezone

import pytest

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.constitution.model import Constitution
from sofia.embodiment.model import Embodiment
from sofia.identity.model import SofiaIdentity
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
from sofia.memory.model import MemoryRecord
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import SofiaCoreState
from sofia.self_model.operational import SofiaOperationalSelfModel
from sofia.system import (
    SystemCapabilityKnowledge,
    SystemCapabilityMachineKnowledge,
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def _machine(
    machine_id: str,
    hostname: str,
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
            hostname=hostname,
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


def _success(
    capability: SystemCapabilityName,
    evidence: dict,
    minute: int = 1,
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
            minute,
            tzinfo=timezone.utc,
        ),
        backend_name="test-backend",
    )


def _failure(
    capability: SystemCapabilityName,
    error: str,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=SystemCapabilityResultKind.FAILED,
        error=error,
    )


def _integration(
    *machines: MachineObservation,
) -> tuple[
    MachineInventory,
    SystemCapabilityKnowledge,
    SystemCapabilityMachineKnowledge,
]:
    inventory = MachineInventory()

    for machine in machines:
        inventory.record(machine)

    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    return inventory, knowledge, integration


def test_all_canonical_capabilities_are_machine_scoped() -> None:
    machine = _machine("venus", "venus")

    _, knowledge, integration = _integration(machine)

    for index, capability in enumerate(
        SystemCapabilityName,
        start=1,
    ):
        integration.record(
            "venus",
            _success(
                capability,
                {"sequence": index},
                minute=index,
            ),
        )

    records = integration.current("venus")

    assert tuple(
        record.capability
        for record in records
    ) == tuple(SystemCapabilityName)

    assert len(records) == len(SystemCapabilityName)

    assert all(
        record.machine_id == "venus"
        for record in records
    )

    assert knowledge.machine_ids() == ("venus",)


def test_success_is_replaced_by_failure() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.SYSTEM_INSPECT,
            "inspection failed",
        ),
    )

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.FAILED
    assert record.evidence is None
    assert record.error == "inspection failed"


def test_failure_is_replaced_by_success() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.SYSTEM_INSPECT,
            "temporary failure",
        ),
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
            minute=2,
        ),
    )

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.SUCCESS
    assert record.evidence["hostname"] == "venus"
    assert record.error is None


def test_unavailable_is_replaced_by_success() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    unavailable = SystemCapabilityResult(
        capability=SystemCapabilityName.NETWORK_INSPECT,
        kind=SystemCapabilityResultKind.UNAVAILABLE,
        error="backend unavailable",
    )

    integration.record(
        "venus",
        unavailable,
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.NETWORK_INSPECT,
            {"interfaces": ["Ethernet"]},
            minute=2,
        ),
    )

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.NETWORK_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.SUCCESS
    assert record.evidence["interfaces"] == ("Ethernet",)


def test_machines_are_strictly_isolated() -> None:
    venus = _machine("venus", "venus")
    terra = _machine("terra", "terra")

    _, knowledge, integration = _integration(
        venus,
        terra,
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    integration.record(
        "terra",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "terra"},
        ),
    )

    venus_record = integration.current_capability(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    terra_record = integration.current_capability(
        "terra",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert venus_record is not None
    assert terra_record is not None

    assert venus_record.evidence["hostname"] == "venus"
    assert terra_record.evidence["hostname"] == "terra"

    assert knowledge.machine_ids() == (
        "terra",
        "venus",
    )


def test_same_capability_on_two_machines_is_independent() -> None:
    venus = _machine("venus", "venus")
    terra = _machine("terra", "terra")

    _, _, integration = _integration(
        venus,
        terra,
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"process_count": 100},
        ),
    )

    integration.record(
        "terra",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"process_count": 20},
        ),
    )

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.PROCESS_INSPECT,
            "process inspection failed",
        ),
    )

    venus_record = integration.current_capability(
        "venus",
        SystemCapabilityName.PROCESS_INSPECT,
    )

    terra_record = integration.current_capability(
        "terra",
        SystemCapabilityName.PROCESS_INSPECT,
    )

    assert venus_record is not None
    assert terra_record is not None

    assert (
        venus_record.kind
        is SystemCapabilityResultKind.FAILED
    )

    assert (
        terra_record.kind
        is SystemCapabilityResultKind.SUCCESS
    )

    assert terra_record.evidence["process_count"] == 20


def test_machine_invalidation_does_not_delete_capability_knowledge() -> None:
    machine = _machine("venus", "venus")

    inventory, knowledge, integration = _integration(machine)

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    inventory.invalidate("venus")

    assert inventory.get("venus") is not None
    assert inventory.get("venus").state.value == "unknown"

    record = knowledge.get(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.SUCCESS


def test_unknown_machine_cannot_receive_capability_knowledge() -> None:
    inventory = MachineInventory()
    knowledge = SystemCapabilityKnowledge()

    integration = SystemCapabilityMachineKnowledge(
        inventory,
        knowledge,
    )

    with pytest.raises(KeyError):
        integration.record(
            "unknown",
            _success(
                SystemCapabilityName.SYSTEM_INSPECT,
                {"hostname": "unknown"},
            ),
        )

    assert knowledge.machine_ids() == ()


def test_nested_evidence_remains_immutable() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    evidence = {
        "system": {
            "hostname": "venus",
            "nested": {
                "value": 42,
            },
        },
        "items": [
            {"name": "one"},
            {"name": "two"},
        ],
    }

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            evidence,
        ),
    )

    evidence["system"]["hostname"] = "changed"
    evidence["system"]["nested"]["value"] = 99
    evidence["items"][0]["name"] = "changed"

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert record.evidence["system"]["hostname"] == "venus"
    assert record.evidence["system"]["nested"]["value"] == 42
    assert record.evidence["items"][0]["name"] == "one"

    with pytest.raises(TypeError):
        record.evidence["system"]["hostname"] = "blocked"


def test_current_capability_does_not_return_stale_success() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SERVICE_INSPECT,
            {"services": ["Spooler"]},
        ),
    )

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.SERVICE_INSPECT,
            "service backend failed",
        ),
    )

    record = integration.current_capability(
        "venus",
        SystemCapabilityName.SERVICE_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.FAILED
    assert record.evidence is None


def test_record_all_is_atomic_against_unknown_machine() -> None:
    machine = _machine("venus", "venus")

    _, knowledge, integration = _integration(machine)

    results = (
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    with pytest.raises(KeyError):
        integration.record_all(
            "terra",
            results,
        )

    assert knowledge.machine_ids() == ()


def test_record_all_preserves_independent_capability_state() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    results = (
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
        _failure(
            SystemCapabilityName.NETWORK_INSPECT,
            "network unavailable",
        ),
        _success(
            SystemCapabilityName.SERVICE_INSPECT,
            {"services": []},
        ),
    )

    integration.record_all(
        "venus",
        results,
    )

    process = integration.current_capability(
        "venus",
        SystemCapabilityName.PROCESS_INSPECT,
    )
    network = integration.current_capability(
        "venus",
        SystemCapabilityName.NETWORK_INSPECT,
    )
    service = integration.current_capability(
        "venus",
        SystemCapabilityName.SERVICE_INSPECT,
    )

    assert process.kind is SystemCapabilityResultKind.SUCCESS
    assert network.kind is SystemCapabilityResultKind.FAILED
    assert service.kind is SystemCapabilityResultKind.SUCCESS


def test_association_does_not_change_machine_history() -> None:
    machine = _machine("venus", "venus")

    inventory, _, integration = _integration(machine)

    before = inventory.history("venus")

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.HARDWARE_INSPECT,
            {"gpu": {"name": "test-gpu"}},
        ),
    )

    after = inventory.history("venus")

    assert after == before


def test_dynamic_capability_observation_does_not_replace_machine_profile() -> None:
    machine = _machine("venus", "venus")

    inventory, _, integration = _integration(machine)

    original_profile = inventory.get("venus").profile

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.HARDWARE_INSPECT,
            {
                "gpu": {
                    "name": "new-gpu-observation",
                },
            },
        ),
    )

    current_profile = inventory.get("venus").profile

    assert current_profile is original_profile
    assert current_profile.hardware == machine.profile.hardware


def test_capability_order_is_stable_after_replacements() -> None:
    machine = _machine("venus", "venus")

    _, _, integration = _integration(machine)

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SERVICE_INSPECT,
            {"services": []},
        ),
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": []},
        ),
    )

    integration.record(
        "venus",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": "venus"},
        ),
    )

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.PROCESS_INSPECT,
            "temporary failure",
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


def test_failed_capability_is_visible_to_cognitive_projection() -> None:
    machine = _machine("venus", "venus")

    _, knowledge, integration = _integration(machine)

    integration.record(
        "venus",
        _failure(
            SystemCapabilityName.NETWORK_INSPECT,
            "network inspection failed",
        ),
    )

    assert knowledge.get(
        "venus",
        SystemCapabilityName.NETWORK_INSPECT,
    ).kind is SystemCapabilityResultKind.FAILED