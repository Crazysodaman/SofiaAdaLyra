import json
from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config import ProviderConfiguration, SofiaConfiguration
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
    filesystem_root: Path,
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
        filesystem_root=filesystem_root,
    )


def create_application(
    tmp_path: Path,
    filesystem_root: Path | None = None,
) -> SofiaApplication:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
        json.dumps(
            {
                "name": "Sofía",
                "traits": [
                    "rigorous",
                    "analytical",
                    "curious",
                    "direct",
                    "blunt",
                    "playful",
                ],
                "communication_style": (
                    "Sofía communicates clearly, directly, rigorously, "
                    "and does not guess when information is missing."
                ),
                "embodiment_guidance": (
                    "Embodied expression should remain natural and varied."
                ),
            }
        ),
        encoding="utf-8",
    )

    configuration = create_configuration(
        personality_path=personality_path,
        state_path=tmp_path / "state.sqlite3",
        filesystem_root=(
            filesystem_root
            if filesystem_root is not None
            else tmp_path
        ),
    )

    return SofiaApplication(configuration)


def test_first_boot_has_no_pending_continuity_awareness(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    application = create_application(
        tmp_path,
        filesystem_root=workspace_root,
    )

    application.runtime.start()

    assert application.runtime.pending_continuity_event is None

    application.runtime.shutdown()


def test_restart_creates_pending_runtime_resumed_awareness(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    application = create_application(
        tmp_path,
        filesystem_root=workspace_root,
    )

    application.runtime.start()
    application.runtime.shutdown()

    application.runtime.start()

    pending_event = application.runtime.pending_continuity_event

    assert pending_event is not None
    assert pending_event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert pending_event.restart_observed is True
    assert pending_event.runtime_continuity.previous_runtime_id is not None
    assert (
        pending_event.runtime_continuity.previous_started_at
        is not None
    )

    application.runtime.shutdown()


def test_application_start_proactively_delivers_runtime_awareness(
    tmp_path,
    monkeypatch,
):
    application = create_application(tmp_path)

    application.runtime.start()
    application.runtime.shutdown()

    responses = []

    def fake_deliver_pending_awareness():
        response = type(
            "FakeResponse",
            (),
            {
                "content": "A previous runtime was observed.",
            },
        )()
        responses.append(response)
        return response

    monkeypatch.setattr(
        application.conversation,
        "deliver_pending_awareness",
        fake_deliver_pending_awareness,
    )

    response = application.start()

    assert response is not None
    assert response.content == (
        "A previous runtime was observed."
    )
    assert len(responses) == 1


def test_failed_awareness_delivery_preserves_pending_event(
    tmp_path,
    monkeypatch,
):
    application = create_application(tmp_path)

    application.runtime.start()
    application.runtime.shutdown()
    application.runtime.start()

    pending_event = application.runtime.pending_continuity_event

    assert pending_event is not None

    application.conversation.open()
    application.conversation.start()

    def fail_delivery(
        request,
        *,
        filesystem_results=(),
    ):
        raise RuntimeError("synthetic awareness delivery failure")

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fail_delivery,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic awareness delivery failure",
    ):
        application.conversation.deliver_pending_awareness()

    assert (
        application.runtime.pending_continuity_event
        is pending_event
    )


def test_awareness_is_consumed_exactly_once(tmp_path, monkeypatch):
    application = create_application(tmp_path)

    application.runtime.start()
    application.runtime.shutdown()
    application.runtime.start()

    assert application.runtime.pending_continuity_event is not None

    application.conversation.open()
    application.conversation.start()

    def fake_respond(
        request,
        *,
        filesystem_results=(),
    ):
        return type(
            "FakeResponse",
            (),
            {
                "content": "Continuity awareness delivered.",
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fake_respond,
    )

    first_response = (
        application.conversation.deliver_pending_awareness()
    )

    assert first_response is not None
    assert first_response.content == (
        "Continuity awareness delivered."
    )
    assert application.runtime.pending_continuity_event is None

    second_response = (
        application.conversation.deliver_pending_awareness()
    )

    assert second_response is None


def test_workspace_changes_create_one_aggregated_pending_awareness_event(
    tmp_path,
):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    modified_path = workspace_root / "modified.py"
    removed_path = workspace_root / "removed.py"

    modified_path.write_text(
        "print('before')\n",
        encoding="utf-8",
    )
    removed_path.write_text(
        "print('removed')\n",
        encoding="utf-8",
    )

    application = create_application(
        tmp_path,
        filesystem_root=workspace_root,
    )

    application.runtime.start()
    application.runtime.shutdown()

    modified_path.write_text(
        "print('after')\n",
        encoding="utf-8",
    )
    removed_path.unlink()

    added_path = workspace_root / "added.py"
    added_path.write_text(
        "print('added')\n",
        encoding="utf-8",
    )

    application.runtime.start()

    pending_event = application.runtime.pending_continuity_event

    assert pending_event is not None
    assert (
        pending_event.kind
        is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    )
    assert pending_event.restart_observed is True
    assert pending_event.workspace_change_count == 3

    changes = pending_event.workspace_changes

    assert changes is not None
    assert len(changes.modified) == 1
    assert len(changes.removed) == 1
    assert len(changes.new) == 1

    assert changes.modified[0].path == modified_path.resolve()
    assert changes.removed[0].path == removed_path.resolve()
    assert changes.new[0].path == added_path.resolve()

    application.runtime.shutdown()


def test_workspace_changes_are_delivered_as_one_awareness_response(
    tmp_path,
    monkeypatch,
):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    modified_path = workspace_root / "modified.py"
    removed_path = workspace_root / "removed.py"

    modified_path.write_text(
        "print('before')\n",
        encoding="utf-8",
    )
    removed_path.write_text(
        "print('removed')\n",
        encoding="utf-8",
    )

    application = create_application(
        tmp_path,
        filesystem_root=workspace_root,
    )

    application.runtime.start()
    application.runtime.shutdown()

    modified_path.write_text(
        "print('after')\n",
        encoding="utf-8",
    )
    removed_path.unlink()

    added_path = workspace_root / "added.py"
    added_path.write_text(
        "print('added')\n",
        encoding="utf-8",
    )

    application.runtime.start()

    pending_event = application.runtime.pending_continuity_event

    assert pending_event is not None
    assert (
        pending_event.kind
        is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    )
    assert pending_event.workspace_change_count == 3

    application.conversation.open()
    application.conversation.start()

    captured_requests = []

    def fake_respond(
        request,
        *,
        filesystem_results=(),
    ):
        captured_requests.append(request)

        return type(
            "FakeResponse",
            (),
            {
                "content": "Workspace awareness delivered.",
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        fake_respond,
    )

    response = application.conversation.deliver_pending_awareness()

    assert response is not None
    assert response.content == "Workspace awareness delivered."

    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert len(request.messages) == 1
    assert request.messages[0].role.value == "system"

    instruction = request.messages[0].content

    assert pending_event.kind.value in instruction
    assert "workspace changes" in instruction
    assert "3" in instruction

    assert application.runtime.pending_continuity_event is None

    messages = application.conversation.messages()

    assert len(messages) == 1
    assert messages[0].role.value == "assistant"
    assert messages[0].content == (
        "Workspace awareness delivered."
    )

    application.runtime.shutdown()