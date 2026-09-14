from pathlib import Path

from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorization,
    FilesystemAuthorizationOperation,
)


class FilesystemAuthorizationEvaluator:
    """
    Evaluates explicit local-console authorization statements for
    Sofía's read-only filesystem capability.

    This evaluator does not perform filesystem operations.

    The current application boundary treats explicit authorization
    from Sparks through the local interactive console as legitimate
    authorization. This is an authorization mechanism, not a claim
    that the console has independently authenticated its operator.
    """

    _AUTHORIZATION_PHRASES = (
        "you are allowed to check your own files",
        "you are allowed to inspect your own files",
        "you may check your own files",
        "you may inspect your own files",
        "you have permission to check your own files",
        "you have permission to inspect your own files",
    )

    _READ_ONLY_OPERATIONS = (
        FilesystemAuthorizationOperation.LIST_DIRECTORY,
        FilesystemAuthorizationOperation.INSPECT_PATH,
        FilesystemAuthorizationOperation.READ_FILE,
        FilesystemAuthorizationOperation.SEARCH_FILES,
    )

    def __init__(
        self,
        scope: Path,
        actor: str = "Sparks",
        role: str = "creator",
    ) -> None:
        if not isinstance(scope, Path):
            raise TypeError(
                "FilesystemAuthorizationEvaluator scope must be a Path."
            )

        if not isinstance(actor, str) or not actor.strip():
            raise ValueError(
                "FilesystemAuthorizationEvaluator actor must be "
                "a non-empty string."
            )

        if not isinstance(role, str) or not role.strip():
            raise ValueError(
                "FilesystemAuthorizationEvaluator role must be "
                "a non-empty string."
            )

        self._scope = scope.resolve()
        self._actor = actor.strip()
        self._role = role.strip()

    @property
    def scope(self) -> Path:
        return self._scope

    @property
    def actor(self) -> str:
        return self._actor

    @property
    def role(self) -> str:
        return self._role

    def evaluate(
        self,
        content: str,
    ) -> FilesystemAuthorization | None:
        """
        Return an authorization record when content contains an
        explicit supported authorization statement.

        Return None when no authorization statement is present.
        """

        if not isinstance(content, str):
            raise TypeError(
                "Filesystem authorization content must be a string."
            )

        normalized = " ".join(
            content.strip().lower().split()
        )

        if not normalized:
            return None

        if not any(
            phrase in normalized
            for phrase in self._AUTHORIZATION_PHRASES
        ):
            return None

        return FilesystemAuthorization(
            actor=self._actor,
            role=self._role,
            domain=AuthorizationDomain.FILESYSTEM,
            scope=self._scope,
            operations=self._READ_ONLY_OPERATIONS,
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason=(
                "Explicit filesystem authorization from "
                f"{self._actor} through the local application."
            ),
        )