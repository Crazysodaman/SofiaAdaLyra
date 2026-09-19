from datetime import datetime, timezone

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.system import (
    SystemCapabilityKnowledge,
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="What is the current system state?",
            ),
        ),
    )


def make_success(
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


def make_failure(
    capability: SystemCapabilityName,
    kind: SystemCapabilityResultKind,
    error: str,
) -> SystemCapabilityResult:
    return SystemCapabilityResult(
        capability=capability,
        kind=kind,
        backend_name=None,
        error=error,
    )


def test_assembler_injects_current_system_capability_knowledge() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        make_success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "system": {
                    "hostname": "venus",
                    "operating_system": "Windows 11",
                }
            },
            observed_at,
        ),
    )

    context = CognitiveContext(
        request=make_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    assembled = CognitiveContextAssembler().assemble(context)
    content = assembled.messages[0].content

    assert "SYSTEM CAPABILITY KNOWLEDGE" in content
    assert "Machine ID: machine-1" in content
    assert "CAPABILITY: system.inspect" in content
    assert "Result: success" in content
    assert "Backend: test-backend" in content
    assert "hostname: venus" in content
    assert "operating_system: Windows 11" in content


def test_assembler_preserves_non_successful_observation_state() -> None:
    knowledge = SystemCapabilityKnowledge()

    knowledge.record(
        "machine-1",
        make_failure(
            SystemCapabilityName.NETWORK_INSPECT,
            SystemCapabilityResultKind.UNAVAILABLE,
            "inspection backend unavailable",
        ),
    )

    context = CognitiveContext(
        request=make_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    assembled = CognitiveContextAssembler().assemble(context)
    content = assembled.messages[0].content

    assert "CAPABILITY: network.inspect" in content
    assert "Result: unavailable" in content
    assert "Error: inspection backend unavailable" in content
    assert "Evidence: none" in content


def test_assembler_projects_only_the_selected_machine() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-a",
        make_success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "system": {
                    "hostname": "machine-a-host",
                }
            },
            observed_at,
        ),
    )

    knowledge.record(
        "machine-b",
        make_success(
            SystemCapabilityName.SYSTEM_INSPECT,
            {
                "system": {
                    "hostname": "machine-b-host",
                }
            },
            observed_at,
        ),
    )

    context = CognitiveContext(
        request=make_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-a",
    )

    assembled = CognitiveContextAssembler().assemble(context)
    content = assembled.messages[0].content

    assert "machine-a-host" in content
    assert "machine-b-host" not in content


def test_assembler_uses_canonical_capability_order() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    for capability in (
        SystemCapabilityName.SERVICE_INSPECT,
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
    ):
        knowledge.record(
            "machine-1",
            make_success(
                capability,
                {"capability": capability.value},
                observed_at,
            ),
        )

    context = CognitiveContext(
        request=make_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    assembled = CognitiveContextAssembler().assemble(context)
    content = assembled.messages[0].content

    process_position = content.index(
        "CAPABILITY: process.inspect"
    )
    network_position = content.index(
        "CAPABILITY: network.inspect"
    )
    service_position = content.index(
        "CAPABILITY: service.inspect"
    )

    assert process_position < network_position
    assert network_position < service_position


def test_assembler_does_not_execute_or_authorize_capabilities() -> None:
    knowledge = SystemCapabilityKnowledge()
    observed_at = datetime.now(timezone.utc)

    knowledge.record(
        "machine-1",
        make_success(
            SystemCapabilityName.PROCESS_INSPECT,
            {
                "processes": (
                    {
                        "pid": 1234,
                        "name": "example",
                    },
                ),
            },
            observed_at,
        ),
    )

    context = CognitiveContext(
        request=make_request(),
        system_capability_knowledge=knowledge,
        system_capability_machine_id="machine-1",
    )

    assembled = CognitiveContextAssembler().assemble(context)
    content = assembled.messages[0].content

    assert (
        "These observations do not grant authority, "
        "execute capabilities"
        in content
    )

    assert assembled.messages[1] == context.request.messages[0]