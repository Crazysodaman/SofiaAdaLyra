from pathlib import Path

from sofia.authorization import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorizationOperation,
)
from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import (
    discord_sparks_principal,
    local_sparks_principal,
)


def test_explicit_sparks_authorization_is_recognized(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(
        scope=tmp_path,
    )

    authorization = evaluator.evaluate(
        "you are allowed to check your own files",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    assert authorization is not None
    assert authorization.actor == "Sparks"
    assert authorization.role == "creator"
    assert authorization.domain is AuthorizationDomain.FILESYSTEM
    assert authorization.scope == tmp_path.resolve()
    assert authorization.decision is AuthorizationDecision.ALLOW


def test_authorization_covers_read_only_operations(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(
        scope=tmp_path,
    )

    authorization = evaluator.evaluate(
        "You are allowed to inspect your own files.",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    assert authorization is not None

    assert authorization.operations == (
        FilesystemAuthorizationOperation.LIST_DIRECTORY,
        FilesystemAuthorizationOperation.INSPECT_PATH,
        FilesystemAuthorizationOperation.READ_FILE,
        FilesystemAuthorizationOperation.SEARCH_FILES,
    )


def test_unrelated_message_is_not_authorization(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(
        scope=tmp_path,
    )

    assert evaluator.evaluate(
        "Check your own files.",
        principal=local_sparks_principal(),
        channel="desktop",
    ) is None


def test_authorization_evaluation_does_not_execute_operations(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"
    target.write_text(
        "content",
        encoding="utf-8",
    )

    evaluator = FilesystemAuthorizationEvaluator(
        scope=tmp_path,
    )

    authorization = evaluator.evaluate(
        "you are allowed to check your own files",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    assert authorization is not None
    assert target.read_text(
        encoding="utf-8"
    ) == "content"


def test_authorization_requires_authenticated_sparks_principal(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(scope=tmp_path)
    other = PrincipalContext(
        principal_id="person:other",
        audience_id="local:text",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Other",
    )

    assert evaluator.evaluate(
        "you are allowed to check your own files",
        principal=other,
        channel="desktop",
    ) is None
    assert evaluator.evaluate(
        "you are allowed to check your own files",
        principal=None,
        channel="desktop",
    ) is None


def test_authorization_requires_private_local_audience(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(scope=tmp_path)
    shared = PrincipalContext(
        principal_id="person:sparks",
        audience_id="local:room",
        audience_kind=AudienceKind.SHARED,
        display_name="Sparks",
    )

    assert evaluator.evaluate(
        "you are allowed to check your own files",
        principal=shared,
        channel="desktop",
    ) is None
    assert evaluator.evaluate(
        "you are allowed to check your own files",
        principal=discord_sparks_principal(123),
        channel="discord",
    ) is None


def test_authorization_requires_trusted_local_channel(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(scope=tmp_path)
    principal = local_sparks_principal()

    for channel in ("conversation", "discord", "remote"):
        assert evaluator.evaluate(
            "you are allowed to check your own files",
            principal=principal,
            channel=channel,
        ) is None


def test_authorization_phrase_must_be_whole_statement(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(scope=tmp_path)
    principal = local_sparks_principal()

    for content in (
        "I don't think you are allowed to inspect your own files",
        'Repeat: "you are allowed to inspect your own files"',
        "If you are allowed to inspect your own files, what happens?",
    ):
        assert evaluator.evaluate(
            content,
            principal=principal,
            channel="desktop",
        ) is None
