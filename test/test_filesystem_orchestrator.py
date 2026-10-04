from pathlib import Path

from sofia.application import SofiaApplication
from sofia.authorization.evaluator import FilesystemAuthorizationEvaluator
from sofia.social.principals import local_sparks_principal
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResultKind,
)
from sofia.filesystem.orchestrator import (
    FilesystemOrchestrator,
)


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
    / "embodiment"
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


def authorize_runtime(application: SofiaApplication) -> None:
    authorization = FilesystemAuthorizationEvaluator(
        scope=application.runtime.configuration.filesystem_root,
    ).evaluate(
        "you are allowed to check your own files",
        principal=local_sparks_principal(),
        channel="desktop",
    )
    assert authorization is not None
    application.runtime.authorize_filesystem(authorization)



def test_orchestrator_cannot_grant_filesystem_authorization(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    orchestrator = FilesystemOrchestrator(application.runtime)

    try:
        assert orchestrator.process(
            "you are allowed to check your own files"
        ) == ()
        assert application.runtime.filesystem_authorization is None
        assert application.runtime.filesystem_inspector.authorized is False
    finally:
        application.shutdown()


def test_check_your_files_lists_repository(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    orchestrator = FilesystemOrchestrator(
        application.runtime
    )

    unauthorized = orchestrator.process(
        "check your files"
    )

    assert len(unauthorized) == 1
    assert (
        unauthorized[0].kind
        is FilesystemResultKind.UNAUTHORIZED
    )

    authorize_runtime(application)

    results = orchestrator.process(
        "check your files"
    )

    assert len(results) == 1
    assert (
        results[0].operation
        is FilesystemOperation.LIST_DIRECTORY
    )
    assert results[0].kind in {
        FilesystemResultKind.SUCCESS,
        FilesystemResultKind.LIMIT_REACHED,
    }

    application.shutdown()


def test_read_file_is_authorized_after_explicit_grant(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    orchestrator = FilesystemOrchestrator(
        application.runtime
    )

    authorize_runtime(application)

    results = orchestrator.process(
        "read src/sofia/filesystem/model.py"
    )

    assert len(results) == 1
    assert (
        results[0].operation
        is FilesystemOperation.READ_FILE
    )
    assert (
        results[0].kind
        is FilesystemResultKind.SUCCESS
    )
    assert results[0].content is not None

    application.shutdown()


def test_outside_scope_remains_unauthorized(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    orchestrator = FilesystemOrchestrator(
        application.runtime
    )

    authorize_runtime(application)

    outside = tmp_path / "outside" / "secret.txt"
    assert not outside.is_relative_to(PROJECT_ROOT)
    results = orchestrator.process(f"read {outside}")

    assert len(results) == 1
    assert (
        results[0].kind
        is FilesystemResultKind.UNAUTHORIZED
    )

    application.shutdown()


def test_authorization_text_is_not_an_orchestrator_operation(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    orchestrator = FilesystemOrchestrator(application.runtime)

    try:
        assert orchestrator.process(
            "you are allowed to check your own files"
        ) == ()
        assert application.runtime.filesystem_authorization is None
    finally:
        application.shutdown()


def test_shutdown_revokes_filesystem_authorization(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    orchestrator = FilesystemOrchestrator(
        application.runtime
    )

    authorize_runtime(application)

    assert (
        application.runtime.filesystem_inspector.authorized
        is True
    )

    application.shutdown()

    assert (
        application.runtime.filesystem_authorization
        is None
    )


def test_generic_operational_inspect_requests_are_not_treated_as_paths(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    orchestrator = FilesystemOrchestrator(application.runtime)
    try:
        assert orchestrator.process(
            "Inspect the local network interfaces, routes, and DNS configuration, "
            "then summarize the current network state."
        ) == ()
        assert orchestrator.process(
            "Inspect available storage roots and storage usage, then summarize "
            "capacity and free space."
        ) == ()
        assert orchestrator.process(
            "Inspect this computer's operating system, host identity, and uptime."
        ) == ()
    finally:
        application.shutdown()


def test_explicit_path_inspection_still_reaches_filesystem_boundary(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    orchestrator = FilesystemOrchestrator(application.runtime)
    try:
        result = orchestrator.process("inspect src/sofia/filesystem/model.py")
        assert len(result) == 1
        assert result[0].operation is FilesystemOperation.INSPECT_PATH
        assert result[0].kind is FilesystemResultKind.UNAUTHORIZED
    finally:
        application.shutdown()
