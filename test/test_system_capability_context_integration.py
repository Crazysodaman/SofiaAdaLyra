from datetime import datetime, timezone

from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.system.knowledge import SystemCapabilityKnowledge
from sofia.system.model import (
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def _request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(),
        tools=(),
    )


def _success(
    capability: SystemCapabilityName,
    evidence: dict,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=SystemCapabilityResultKind.SUCCESS,
        evidence=evidence,
        observed_at=datetime.now(timezone.utc),
        backend_name="test-backend",
    )


def _failure(
    capability: SystemCapabilityName,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=SystemCapabilityResultKind.FAILED,
        observed_at=None,
        backend_name="test-backend",
        error="inspection failed",
    )


def test_cognitive_context_accepts_system_capability_knowledge() -> None:
    knowledge = SystemCapabilityKnowledge()

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "hostname": "venus",
                "platform": "windows",
            },
        ),
    )

    context = CognitiveContext(
        request=_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    assert (
        context.system_capability_knowledge
        is knowledge
    )

    assert (
        context.system_capability_machine_id
        == "machine-1"
    )


def test_cognitive_context_rejects_invalid_knowledge_type() -> None:
    try:
        CognitiveContext(
            request=_request(),
            system_capability_knowledge="invalid",  # type: ignore[arg-type]
        )
    except TypeError:
        return

    raise AssertionError(
        "CognitiveContext must reject an invalid "
        "SystemCapabilityKnowledge value."
    )


def test_cognitive_context_rejects_invalid_machine_id_type() -> None:
    knowledge = SystemCapabilityKnowledge()

    try:
        CognitiveContext(
            request=_request(),
            system_capability_knowledge=knowledge,
            system_capability_machine_id=123,  # type: ignore[arg-type]
        )
    except TypeError:
        return

    raise AssertionError(
        "CognitiveContext must reject a non-string "
        "system capability machine ID."
    )


def test_cognitive_context_can_expose_current_machine_knowledge() -> None:
    knowledge = SystemCapabilityKnowledge()

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.PROCESS_INSPECT,
            {
                "processes": [
                    {
                        "pid": 1234,
                        "name": "test-process",
                    }
                ]
            },
        ),
    )

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.SERVICE_INSPECT,
            {
                "services": [
                    {
                        "name": "test-service",
                        "state": "running",
                    }
                ]
            },
        ),
    )

    context = CognitiveContext(
        request=_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    records = context.current_system_capability_knowledge

    assert tuple(
        record.capability
        for record in records
    ) == (
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    )


def test_cognitive_context_exposes_failed_observation_without_stale_success() -> None:
    knowledge = SystemCapabilityKnowledge()

    knowledge.record(
        "machine-1",
        _success(
            SystemCapabilityName.NETWORK_INSPECT,
            {
                "interfaces": [
                    {
                        "name": "Ethernet",
                    }
                ]
            },
        ),
    )

    knowledge.record(
        "machine-1",
        _failure(
            SystemCapabilityName.NETWORK_INSPECT,
        ),
    )

    context = CognitiveContext(
        request=_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    records = context.current_system_capability_knowledge

    assert len(records) == 1
    assert (
        records[0].capability
        is SystemCapabilityName.NETWORK_INSPECT
    )
    assert (
        records[0].kind
        is SystemCapabilityResultKind.FAILED
    )
    assert records[0].evidence is None