from pathlib import Path

import pytest

from sofia.authorization import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorization,
    FilesystemAuthorizationOperation,
)


def make_authorization() -> FilesystemAuthorization:
    return FilesystemAuthorization(
        actor="Sparks",
        role="creator",
        domain=AuthorizationDomain.FILESYSTEM,
        scope=Path("/sofia"),
        operations=(
            FilesystemAuthorizationOperation.LIST_DIRECTORY,
            FilesystemAuthorizationOperation.INSPECT_PATH,
            FilesystemAuthorizationOperation.READ_FILE,
            FilesystemAuthorizationOperation.SEARCH_FILES,
        ),
        target=None,
        decision=AuthorizationDecision.ALLOW,
        reason="Explicit authorization from Sparks.",
    )


def test_filesystem_authorization_is_immutable():
    authorization = make_authorization()

    with pytest.raises(AttributeError):
        authorization.actor = "Someone Else"


def test_filesystem_authorization_preserves_authority_context():
    authorization = make_authorization()

    assert authorization.actor == "Sparks"
    assert authorization.role == "creator"
    assert authorization.domain is AuthorizationDomain.FILESYSTEM
    assert authorization.scope == Path("/sofia")
    assert authorization.decision is AuthorizationDecision.ALLOW
    assert authorization.reason == "Explicit authorization from Sparks."


def test_filesystem_authorization_supports_read_only_operations():
    authorization = make_authorization()

    assert authorization.operations == (
        FilesystemAuthorizationOperation.LIST_DIRECTORY,
        FilesystemAuthorizationOperation.INSPECT_PATH,
        FilesystemAuthorizationOperation.READ_FILE,
        FilesystemAuthorizationOperation.SEARCH_FILES,
    )


def test_filesystem_authorization_can_target_specific_path():
    authorization = FilesystemAuthorization(
        actor="Sparks",
        role="creator",
        domain=AuthorizationDomain.FILESYSTEM,
        scope=Path("/sofia"),
        operations=(
            FilesystemAuthorizationOperation.READ_FILE,
        ),
        target=Path("/sofia/src/sofia/runtime/runtime.py"),
        decision=AuthorizationDecision.ALLOW,
        reason="Explicit authorization from Sparks.",
    )

    assert authorization.target == Path(
        "/sofia/src/sofia/runtime/runtime.py"
    )


@pytest.mark.parametrize(
    "actor",
    ["", "   ", None],
)
def test_filesystem_authorization_rejects_invalid_actor(actor):
    with pytest.raises((TypeError, ValueError)):
        FilesystemAuthorization(
            actor=actor,
            role="creator",
            domain=AuthorizationDomain.FILESYSTEM,
            scope=Path("/sofia"),
            operations=(
                FilesystemAuthorizationOperation.READ_FILE,
            ),
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason="Explicit authorization from Sparks.",
        )


def test_filesystem_authorization_rejects_invalid_scope():
    with pytest.raises(TypeError):
        FilesystemAuthorization(
            actor="Sparks",
            role="creator",
            domain=AuthorizationDomain.FILESYSTEM,
            scope="/sofia",
            operations=(
                FilesystemAuthorizationOperation.READ_FILE,
            ),
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason="Explicit authorization from Sparks.",
        )


def test_filesystem_authorization_rejects_invalid_operation():
    with pytest.raises(TypeError):
        FilesystemAuthorization(
            actor="Sparks",
            role="creator",
            domain=AuthorizationDomain.FILESYSTEM,
            scope=Path("/sofia"),
            operations=("read_file",),
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason="Explicit authorization from Sparks.",
        )


def test_filesystem_authorization_rejects_empty_reason():
    with pytest.raises(ValueError):
        FilesystemAuthorization(
            actor="Sparks",
            role="creator",
            domain=AuthorizationDomain.FILESYSTEM,
            scope=Path("/sofia"),
            operations=(
                FilesystemAuthorizationOperation.READ_FILE,
            ),
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason="",
        )


def test_denial_is_represented_explicitly():
    authorization = FilesystemAuthorization(
        actor="Sparks",
        role="creator",
        domain=AuthorizationDomain.FILESYSTEM,
        scope=Path("/sofia"),
        operations=(
            FilesystemAuthorizationOperation.READ_FILE,
        ),
        target=Path("/outside/secret.txt"),
        decision=AuthorizationDecision.DENY,
        reason="Requested target is outside the authorized filesystem scope.",
    )

    assert authorization.decision is AuthorizationDecision.DENY