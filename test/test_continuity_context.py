from datetime import datetime, timezone
from uuid import uuid4

from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.continuity.model import (
    ContinuityEventKind,
)
from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)


def request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )


def test_cognitive_context_derives_one_continuity_event():
    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=runtime_id,
        current_started_at=started_at,
        previous_runtime_id=uuid4(),
        previous_started_at=(
            started_at
        ),
        previous_stopped_at=(
            started_at
        ),
        previous_lifecycle_state="stopped",
    )

    context = CognitiveContext(
        request=request(),
        runtime_continuity=continuity,
    )

    event = context.continuity_event

    assert event is not None
    assert event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert event.runtime_continuity is continuity


def test_cognitive_context_has_no_continuity_event_without_evidence():
    context = CognitiveContext(
        request=request(),
    )

    assert context.continuity_event is None