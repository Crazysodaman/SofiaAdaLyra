from datetime import datetime, timedelta, timezone

import pytest

from sofia.system import (
    SystemCapabilityKnowledge,
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def _success(
    capability: SystemCapabilityName,
    evidence: dict,
    observed_at: datetime,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=SystemCapabilityResultKind.SUCCESS,
        evidence=evidence,
        observed_at=observed_at,
        backend_name="test-backend",
    )


def _failure(
    capability: SystemCapabilityName,
    kind: SystemCapabilityResultKind,
    error: str,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=kind,
        error=error,
        backend_name="test-backend",
    )


def test_knowledge_records_successful_capability_evidence() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    result = _success(
        SystemCapabilityName.SYSTEM_INSPECT,
        {
            "system": {
                "hostname": "test-host",
                "operating_system": "Test Linux",
            }
        },
        observed_at,
    )

    update = knowledge.record(
        "machine-1",
        result,
    )

    assert update.previous is None
    assert update.changed is True
    assert update.current.machine_id == "machine-1"
    assert (
        update.current.capability
        is SystemCapabilityName.SYSTEM_INSPECT
    )
    assert update.current.kind is SystemCapabilityResultKind.SUCCESS
    assert update.current.observed_at == observed_at
    assert update.current.backend_name == "test-backend"


def test_evidence_is_copied_into_immutable_mapping() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    evidence = {
        "system": {
            "hostname": "test-host",
        }
    }

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            evidence,
            observed_at,
        ),
    )

    evidence["system"]["hostname"] = "changed"

    record = knowledge.get(
        "machine-1",
        SystemCapabilityName.SYSTEM_INSPECT,
    )

    assert record is not None
    assert (
        record.evidence["system"]["hostname"]
        == "test-host"
    )


def test_repeated_identical_result_is_not_changed() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    result = _success(
        SystemCapabilityName.NETWORK_INSPECT,
        {
            "network": {
                "interfaces": (),
                "routes": (),
                "dns_servers": (),
            }
        },
        observed_at,
    )

    first = knowledge.record(
        "machine-1",
        result,
    )
    second = knowledge.record(
        "machine-1",
        result,
    )

    assert first.changed is True
    assert second.changed is False
    assert second.previous == second.current


def test_changed_successful_result_replaces_previous_record() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    first = knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "system": {
                    "hostname": "old-host",
                }
            },
            observed_at,
        ),
    )

    second = knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "system": {
                    "hostname": "new-host",
                }
            },
            observed_at + timedelta(seconds=1),
        ),
    )

    assert first.previous is None
    assert second.previous is not None
    assert second.changed is True
    assert (
        second.previous.evidence["system"]["hostname"]
        == "old-host"
    )
    assert (
        second.current.evidence["system"]["hostname"]
        == "new-host"
    )


@pytest.mark.parametrize(
    "kind",
    (
        SystemCapabilityResultKind.UNAVAILABLE,
        SystemCapabilityResultKind.UNSUPPORTED,
        SystemCapabilityResultKind.FAILED,
    ),
)
def test_non_successful_result_replaces_old_success(
    kind: SystemCapabilityResultKind,
) -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {
                "processes": (),
            },
            observed_at,
        ),
    )

    update = knowledge.record(
        "machine-1",
        _failure(
            SystemCapabilityName.PROCESS_INSPECT,
            kind,
            "inspection unavailable",
        ),
    )

    assert update.changed is True
    assert update.current.kind is kind
    assert update.current.evidence is None
    assert update.current.error == "inspection unavailable"


def test_failed_result_does_not_retain_stale_success_evidence() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SERVICE_INSPECT,
            {
                "services": (
                    {
                        "name": "example.service",
                    },
                ),
            },
            observed_at,
        ),
    )

    knowledge.record(
        "machine-1",
        _failure(
            SystemCapabilityName.SERVICE_INSPECT,
            SystemCapabilityResultKind.UNAVAILABLE,
            "systemctl unavailable",
        ),
    )

    current = knowledge.get(
        "machine-1",
        SystemCapabilityName.SERVICE_INSPECT,
    )

    assert current is not None
    assert (
        current.kind
        is SystemCapabilityResultKind.UNAVAILABLE
    )
    assert current.evidence is None


def test_capabilities_are_isolated_per_machine() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    result = _success(
        SystemCapabilityName.SYSTEM_INSPECT,
        {
            "system": {
                "hostname": "host-a",
            }
        },
        observed_at,
    )

    knowledge.record(
        "machine-a",
        result,
    )

    assert (
        knowledge.get(
            "machine-a",
            SystemCapabilityName.SYSTEM_INSPECT,
        )
        is not None
    )

    assert (
        knowledge.get(
            "machine-b",
            SystemCapabilityName.SYSTEM_INSPECT,
        )
        is None
    )


def test_all_for_machine_returns_canonical_capability_order() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    for capability in (
        SystemCapabilityName.SERVICE_INSPECT,
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
    ):
        knowledge.record(
            "machine-1",
            _success(
                capability,
                {"value": capability.value},
                observed_at,
            ),
        )

    records = knowledge.all_for_machine(
        "machine-1"
    )

    assert tuple(
        record.capability
        for record in records
    ) == (
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    )


def test_record_all_records_every_result() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    results = (
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {"processes": ()},
            observed_at,
        ),
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"system": {}},
            observed_at,
        ),
        _success(
            SystemCapabilityName.NETWORK_INSPECT,
            {"network": {}},
            observed_at,
        ),
    )

    updates = knowledge.record_all(
        "machine-1",
        results,
    )

    assert len(updates) == 3
    assert len(knowledge.all_for_machine("machine-1")) == 3


def test_machine_ids_reports_known_machines() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-a",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {},
            observed_at,
        ),
    )

    knowledge.record(
        "machine-b",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {},
            observed_at,
        ),
    )

    assert knowledge.machine_ids() == (
        "machine-a",
        "machine-b",
    )


def test_capabilities_for_machine_reports_recorded_capabilities() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {},
            observed_at,
        ),
    )

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.HARDWARE_INSPECT,
            {},
            observed_at,
        ),
    )

    assert knowledge.capabilities_for_machine(
        "machine-1"
    ) == (
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.HARDWARE_INSPECT,
    )


def test_clear_machine_removes_all_operational_knowledge() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {},
            observed_at,
        ),
    )

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {},
            observed_at,
        ),
    )

    knowledge.clear_machine("machine-1")

    assert knowledge.get(
        "machine-1",
        SystemCapabilityName.SYSTEM_INSPECT,
    ) is None

    assert knowledge.get(
        "machine-1",
        SystemCapabilityName.PROCESS_INSPECT,
    ) is None

    assert knowledge.machine_ids() == ()


@pytest.mark.parametrize(
    "machine_id",
    ("", "   "),
)
def test_record_rejects_empty_machine_id(
    machine_id: str,
) -> None:
    knowledge = SystemCapabilityKnowledge()

    with pytest.raises(ValueError):
        knowledge.record(
            machine_id,
            _failure(
                SystemCapabilityName.SYSTEM_INSPECT,
                SystemCapabilityResultKind.FAILED,
                "test",
            ),
        )


def test_record_rejects_invalid_machine_id_type() -> None:
    knowledge = SystemCapabilityKnowledge()

    with pytest.raises(TypeError):
        knowledge.record(  # type: ignore[arg-type]
            123,
            _failure(
                SystemCapabilityName.SYSTEM_INSPECT,
                SystemCapabilityResultKind.FAILED,
                "test",
            ),
        )


def test_record_rejects_invalid_result_type() -> None:
    knowledge = SystemCapabilityKnowledge()

    with pytest.raises(TypeError):
        knowledge.record(
            "machine-1",
            object(),  # type: ignore[arg-type]
        )


def test_get_rejects_invalid_capability() -> None:
    knowledge = SystemCapabilityKnowledge()

    with pytest.raises(TypeError):
        knowledge.get(
            "machine-1",
            "system.inspect",  # type: ignore[arg-type]
        )


def test_successful_record_preserves_backend_provenance() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.HARDWARE_INSPECT,
            {
                "hardware": {
                    "cpu": "test-cpu",
                }
            },
            observed_at,
        ),
    )

    record = knowledge.get(
        "machine-1",
        SystemCapabilityName.HARDWARE_INSPECT,
    )

    assert record is not None
    assert record.backend_name == "test-backend"
    assert record.observed_at == observed_at


def test_non_successful_result_preserves_failure_provenance() -> None:
    knowledge = SystemCapabilityKnowledge()

    knowledge.record(
        "machine-1",
        _failure(
            SystemCapabilityName.HARDWARE_INSPECT,
            SystemCapabilityResultKind.FAILED,
            "backend failed",
        ),
    )

    record = knowledge.get(
        "machine-1",
        SystemCapabilityName.HARDWARE_INSPECT,
    )

    assert record is not None
    assert record.kind is SystemCapabilityResultKind.FAILED
    assert record.backend_name == "test-backend"
    assert record.error == "backend failed"