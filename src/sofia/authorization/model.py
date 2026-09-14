from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AuthorizationDecision(str, Enum):
    """
    Result of an authorization evaluation.
    """

    ALLOW = "allow"
    ALLOW_WITH_CONDITIONS = "allow_with_conditions"
    DEFER = "defer"
    ESCALATE = "escalate"
    DENY = "deny"
    EMERGENCY_CONTAINMENT = "emergency_containment"


class AuthorizationDomain(str, Enum):
    """
    Domain in which an authorization applies.
    """

    FILESYSTEM = "filesystem"


class FilesystemAuthorizationOperation(str, Enum):
    """
    Read-only filesystem operations that may be authorized.
    """

    LIST_DIRECTORY = "list_directory"
    INSPECT_PATH = "inspect_path"
    READ_FILE = "read_file"
    SEARCH_FILES = "search_files"


@dataclass(frozen=True)
class FilesystemAuthorization:
    """
    Immutable authorization describing who may authorize filesystem
    inspection, what scope is covered, which operations are allowed,
    and the resulting authorization decision.

    Authorization does not itself perform an operation and does not
    bypass filesystem capability or configured filesystem boundaries.
    """

    actor: str
    role: str
    domain: AuthorizationDomain
    scope: Path
    operations: tuple[FilesystemAuthorizationOperation, ...]
    target: Path | None
    decision: AuthorizationDecision
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.actor, str) or not self.actor.strip():
            raise ValueError(
                "FilesystemAuthorization actor must be a non-empty string."
            )

        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError(
                "FilesystemAuthorization role must be a non-empty string."
            )

        if not isinstance(self.domain, AuthorizationDomain):
            raise TypeError(
                "FilesystemAuthorization domain must be an "
                "AuthorizationDomain."
            )

        if not isinstance(self.scope, Path):
            raise TypeError(
                "FilesystemAuthorization scope must be a Path."
            )

        if not isinstance(self.operations, tuple):
            raise TypeError(
                "FilesystemAuthorization operations must be a tuple."
            )

        for operation in self.operations:
            if not isinstance(
                operation,
                FilesystemAuthorizationOperation,
            ):
                raise TypeError(
                    "FilesystemAuthorization operations must contain "
                    "FilesystemAuthorizationOperation instances."
                )

        if self.target is not None and not isinstance(self.target, Path):
            raise TypeError(
                "FilesystemAuthorization target must be a Path or None."
            )

        if not isinstance(self.decision, AuthorizationDecision):
            raise TypeError(
                "FilesystemAuthorization decision must be an "
                "AuthorizationDecision."
            )

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "FilesystemAuthorization reason must be a non-empty string."
            )