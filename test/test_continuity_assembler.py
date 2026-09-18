from datetime import datetime, timezone
from uuid import uuid4

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)


def test_assembler_exposes_aggregate_continuity_event():
    started_at = datetime.now(timezone.utc)

    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=uuid4(),
        current_started_at=started_at,
        previous_runtime_id=uuid4(),
        previous_started_at=started_at,
        previous_stopped_at=started_at,
        previous_lifecycle_state="stopped",
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What changed?",
                ),
            ),
        ),
        runtime_continuity=continuity,
    )

    request = CognitiveContextAssembler().assemble(
        context
    )

    system_message = request.messages[0]

    assert system_message.role is CognitiveRole.SYSTEM
    assert "CONTINUITY EVENT" in system_message.content
    assert "Event kind: runtime_resumed" in system_message.content
    assert (
        "Do not produce a separate response for each individual "
        "filesystem change."
        in system_message.content
    )


def test_assembler_does_not_require_continuity_announcement():
    started_at = datetime.now(timezone.utc)

    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.UNKNOWN,
        current_runtime_id=uuid4(),
        current_started_at=started_at,
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What is 2 + 2?",
                ),
            ),
        ),
        runtime_continuity=continuity,
    )

    request = CognitiveContextAssembler().assemble(
        context
    )

    system_message = request.messages[0]

    assert (
        "it does not need to be announced merely because it exists"
        in system_message.content
    )