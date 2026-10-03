from pathlib import Path

from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
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

    _TRUSTED_LOCAL_CHANNELS = frozenset({
        "desktop",
        "terminal",
    })

    _READ_ONLY_OPERATIONS = (
        FilesystemAuthorizationOperation.LIST_DIRECTORY,
        FilesystemAuthorizationOperation.INSPECT_PATH,
        FilesystemAuthorizationOperation.READ_FILE,
        FilesystemAuthorizationOperation.SEARCH_FILES,
    )

    _ACTOR = "Sparks"
    _ROLE = "creator"

    def __init__(
        self,
        scope: Path,
    ) -> None:
        if not isinstance(scope, Path):
            raise TypeError(
                "FilesystemAuthorizationEvaluator scope must be a Path."
            )

        self._scope = scope.resolve()

    @property
    def scope(self) -> Path:
        return self._scope

    @property
    def actor(self) -> str:
        return self._ACTOR

    @property
    def role(self) -> str:
        return self._ROLE

    def evaluate(
        self,
        content: str,
        *,
        principal: PrincipalContext | None,
        channel: str,
    ) -> FilesystemAuthorization | None:
        """Evaluate one explicit authorization statement.

        Authorization is fail-closed. Text alone is never identity evidence:
        the caller must supply the authenticated private local Sparks principal
        and an explicitly trusted local interactive channel.
        """

        if not isinstance(content, str):
            raise TypeError(
                "Filesystem authorization content must be a string."
            )
        if principal is not None and not isinstance(
            principal,
            PrincipalContext,
        ):
            raise TypeError(
                "Filesystem authorization principal must be "
                "a PrincipalContext or None."
            )
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError(
                "Filesystem authorization channel must be a non-empty string."
            )

        normalized_channel = channel.strip().casefold()
        if (
            principal is None
            or principal.principal_id != SPARKS_PRINCIPAL_ID
            or principal.audience_kind is not AudienceKind.PRIVATE
            or not principal.audience_id.startswith("local:")
            or normalized_channel not in self._TRUSTED_LOCAL_CHANNELS
        ):
            return None

        normalized = " ".join(
            content.strip().casefold().split()
        ).rstrip(".!?")

        if not normalized:
            return None

        if normalized not in self._AUTHORIZATION_PHRASES:
            return None

        return FilesystemAuthorization(
            actor=self._ACTOR,
            role=self._ROLE,
            domain=AuthorizationDomain.FILESYSTEM,
            scope=self._scope,
            operations=self._READ_ONLY_OPERATIONS,
            target=None,
            decision=AuthorizationDecision.ALLOW,
            reason=(
                "Explicit filesystem authorization from authenticated "
                f"{self._ACTOR} through a trusted local application channel."
            ),
        )