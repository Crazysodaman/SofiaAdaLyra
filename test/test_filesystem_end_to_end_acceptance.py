from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import CognitiveRole
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResultKind,
)
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
            model="test",
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


def test_filesystem_request_is_unauthorized_before_explicit_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_requests = []
    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_requests.append(request)
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Filesystem request processed."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    response = application.conversation.respond(
        "check your files"
    )

    assert response.content == "Filesystem request processed."

    assert len(captured_requests) == 1
    assert len(captured_filesystem_results) == 1

    results = captured_filesystem_results[0]

    assert len(results) == 1

    result = results[0]

    assert result.operation is FilesystemOperation.LIST_DIRECTORY
    assert result.kind is FilesystemResultKind.UNAUTHORIZED

    application.shutdown()


def test_explicit_own_files_authorization_does_not_execute_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_requests = []
    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_requests.append(request)
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Authorization recorded."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    response = application.conversation.respond(
        "you are allowed to check your own files"
    )

    assert response.content == "Authorization recorded."

    assert application.runtime.filesystem_authorization is not None
    assert application.runtime.filesystem_inspector.authorized is True

    assert captured_filesystem_results == [()]

    application.shutdown()


def test_authorization_enables_actual_own_files_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Inspection completed."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    application.conversation.respond(
        "check your files"
    )

    assert len(captured_filesystem_results) == 2

    results = captured_filesystem_results[1]

    assert len(results) == 1

    result = results[0]

    assert result.operation is FilesystemOperation.LIST_DIRECTORY
    assert result.kind in {
        FilesystemResultKind.SUCCESS,
        FilesystemResultKind.LIMIT_REACHED,
    }

    assert result.entries

    application.shutdown()


def test_authorized_file_read_returns_real_repository_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "File inspection completed."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    application.conversation.respond(
        "read src/sofia/filesystem/model.py"
    )

    results = captured_filesystem_results[1]

    assert len(results) == 1

    result = results[0]

    assert result.operation is FilesystemOperation.READ_FILE
    assert result.kind is FilesystemResultKind.SUCCESS
    assert result.content is not None
    assert "class FilesystemResult" in result.content

    application.shutdown()


def test_authorization_does_not_expand_filesystem_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Scope checked."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    application.conversation.respond(
        "read ../outside-secret.txt"
    )

    results = captured_filesystem_results[1]

    assert len(results) == 1

    result = results[0]

    assert result.kind is FilesystemResultKind.UNAUTHORIZED

    application.shutdown()


def test_filesystem_evidence_reaches_cognitive_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    captured_requests = []
    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_requests.append(request)
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Evidence received."
            },
        )()

    monkeypatch.setattr(
        application.runtime,
        "respond",
        capture_request,
    )

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    application.conversation.respond(
        "read src/sofia/filesystem/model.py"
    )

    assert len(captured_requests) == 2

    request = captured_requests[1]

    assert request.messages[-1].role is CognitiveRole.USER
    assert (
        request.messages[-1].content
        == "read src/sofia/filesystem/model.py"
    )

    results = captured_filesystem_results[1]

    assert len(results) == 1
    assert results[0].content is not None

    application.shutdown()


def test_filesystem_authorization_is_revoked_by_shutdown(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    assert application.runtime.filesystem_authorization is not None
    assert application.runtime.filesystem_inspector.authorized is True

    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED
    assert application.runtime.filesystem_authorization is None
    assert application.runtime.filesystem_inspector.authorized is False


def test_restart_requires_authorization_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    assert application.runtime.filesystem_inspector.authorized is True

    application.shutdown()

    resumed = create_application(tmp_path)
    resumed.start()

    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results=(),
    ):
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Restart authorization checked."
            },
        )()

    monkeypatch.setattr(
        resumed.runtime,
        "respond",
        capture_request,
    )

    resumed.conversation.respond(
        "check your files"
    )

    results = captured_filesystem_results[0]

    assert len(results) == 1
    assert results[0].kind is FilesystemResultKind.UNAUTHORIZED
    assert resumed.runtime.filesystem_inspector.authorized is False

    resumed.shutdown()


def test_filesystem_capability_remains_read_only_after_authorization(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    inspector = application.runtime.filesystem_inspector

    assert inspector.authorized is True

    assert not hasattr(
        inspector,
        "write_file",
    )

    assert not hasattr(
        inspector,
        "delete_file",
    )

    assert not hasattr(
        inspector,
        "move_file",
    )

    assert not hasattr(
        inspector,
        "copy_file",
    )

    assert not hasattr(
        inspector,
        "execute",
    )

    application.shutdown()