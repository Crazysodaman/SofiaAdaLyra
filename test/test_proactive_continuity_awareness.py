from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.continuity.model import ContinuityEventKind
from sofia.cognition.model import CognitiveResponse
from sofia.runtime.model import RuntimeState


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


def create_configuration(
    personality_path: Path,
    state_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def create_personality(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "personality.json"

    path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return path


def create_application(
    tmp_path: Path,
) -> SofiaApplication:
    return SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )


def test_first_boot_has_no_pending_awareness(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    assert application.runtime.state is RuntimeState.READY
    assert application.runtime.pending_continuity_event is None

    application.shutdown()


def test_restart_creates_pending_runtime_awareness(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()
    first_runtime_id = application.runtime.runtime_id

    assert first_runtime_id is not None

    application.shutdown()

    application.start()

    event = application.runtime.pending_continuity_event

    assert event is not None
    assert event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert event.restart_observed is True
    assert event.runtime_continuity.previous_runtime_id == (
        first_runtime_id
    )

    application.shutdown()


def test_start_delivers_pending_awareness_automatically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    captured_requests = []

    def fake_respond(request, filesystem_results=()):
        captured_requests.append(request)
        return CognitiveResponse(
            content="I detected a new runtime after the previous runtime.",
        )

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fake_respond,
    )

    application.start()
    application.shutdown()

    application.start()

    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert len(request.messages) == 1
    assert request.messages[0].role.value == "system"
    assert "pending continuity event" in request.messages[0].content
    assert "subjective memory" in request.messages[0].content
    assert "separate statement for each changed file" in (
        request.messages[0].content
    )

    assert application.runtime.pending_continuity_event is None

    messages = application.conversation.messages()

    assert len(messages) == 1
    assert messages[0].role.value == "assistant"
    assert messages[0].content == (
        "I detected a new runtime after the previous runtime."
    )

    application.shutdown()


def test_failed_awareness_delivery_preserves_pending_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()
    application.shutdown()

    application.start()

    original_event = application.runtime.pending_continuity_event

    assert original_event is not None

    def fail_respond(request, filesystem_results=()):
        raise RuntimeError("simulated cognitive failure")

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fail_respond,
    )

    with pytest.raises(Exception):
        application.conversation.deliver_pending_awareness()

    assert application.runtime.pending_continuity_event is original_event

    application.shutdown()


def test_awareness_consumption_is_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()
    application.shutdown()

    application.start()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        lambda request, filesystem_results=(): CognitiveResponse(
            content="Continuity acknowledged.",
        ),
    )

    first = application.conversation.deliver_pending_awareness()
    second = application.conversation.deliver_pending_awareness()

    assert first is not None
    assert second is None
    assert application.runtime.pending_continuity_event is None

    application.shutdown()