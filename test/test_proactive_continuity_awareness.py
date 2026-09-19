from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.continuity.model import ContinuityEventKind


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
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=state_path,
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


def test_first_runtime_has_no_pending_continuity_awareness(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.runtime.start()

    assert application.runtime.pending_continuity_event is None

    application.runtime.shutdown()


def test_restart_creates_pending_runtime_awareness(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.runtime.start()
    first_runtime_id = application.runtime.runtime_id

    application.runtime.shutdown()

    application.runtime.start()

    assert application.runtime.runtime_id != first_runtime_id

    event = application.runtime.pending_continuity_event

    assert event is not None
    assert event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert event.restart_observed is True
    assert event.runtime_continuity.previous_runtime_id == first_runtime_id

    application.runtime.shutdown()


def test_application_start_delivers_pending_runtime_awareness(
    tmp_path: Path,
):
    configuration = create_configuration(
        create_personality(tmp_path),
        tmp_path / "sofia.db",
    )

    first_application = SofiaApplication(configuration)
    first_application.start()
    first_application.shutdown()

    second_application = SofiaApplication(configuration)
    second_application.start()

    messages = second_application.conversation.messages()

    assert len(messages) == 1
    assert messages[0].role.value == "assistant"
    assert messages[0].content == "Test cognitive response."

    assert second_application.runtime.pending_continuity_event is None

    second_application.shutdown()


def test_failed_awareness_delivery_preserves_pending_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.runtime.start()
    application.runtime.shutdown()
    application.runtime.start()

    pending_event = application.runtime.pending_continuity_event

    assert pending_event is not None
    assert pending_event.kind is ContinuityEventKind.RUNTIME_RESUMED

    def fail_response(*args, **kwargs):
        raise RuntimeError("simulated cognitive delivery failure")

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fail_response,
    )

    with pytest.raises(RuntimeError, match="simulated cognitive delivery failure"):
        application.conversation.deliver_pending_awareness()

    assert application.runtime.pending_continuity_event is pending_event

    application.runtime.shutdown()


def test_awareness_consumption_is_exactly_once(
    tmp_path: Path,
):
    configuration = create_configuration(
        create_personality(tmp_path),
        tmp_path / "sofia.db",
    )

    first_application = SofiaApplication(configuration)
    first_application.start()
    first_application.shutdown()

    second_application = SofiaApplication(configuration)
    second_application.start()

    assert second_application.runtime.pending_continuity_event is None

    messages_after_start = second_application.conversation.messages()

    assert len(messages_after_start) == 1
    assert messages_after_start[0].role.value == "assistant"

    result = second_application.conversation.deliver_pending_awareness()

    assert result is None

    messages_after_second_delivery = (
        second_application.conversation.messages()
    )

    assert len(messages_after_second_delivery) == 1
    assert messages_after_second_delivery == messages_after_start

    second_application.shutdown()