from pathlib import Path

from sofia.authorization import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorizationOperation,
)
from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)


def test_explicit_sparks_authorization_is_recognized(
    tmp_path: Path,
):
    evaluator = FilesystemAuthorizationEvaluator(
        scope=tmp_path,
    )

    authorization = evaluator.evaluate(
        "you are allowed to check your own files"
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
        "You are allowed to inspect your own files."
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
        "Check your own files."
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
        "you are allowed to check your own files"
    )

    assert authorization is not None
    assert target.read_text(
        encoding="utf-8"
    ) == "content"