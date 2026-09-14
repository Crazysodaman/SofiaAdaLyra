from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FilesystemResultKind(str, Enum):
    """
    Classification of a filesystem inspection result.
    """

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    INACCESSIBLE = "inaccessible"
    UNAUTHORIZED = "unauthorized"
    UNAVAILABLE = "unavailable"


class FilesystemOperation(str, Enum):
    """
    Read-only filesystem operations supported by Batch 10.
    """

    LIST_DIRECTORY = "list_directory"
    INSPECT_PATH = "inspect_path"
    READ_FILE = "read_file"
    SEARCH_FILES = "search_files"


class FilesystemInspectionError(Exception):
    """
    Raised when a filesystem inspection operation cannot be completed.
    """


@dataclass(frozen=True)
class FilesystemResult:
    """
    Immutable result of a filesystem inspection operation.

    A result explicitly records whether the requested operation succeeded,
    was unauthorized, encountered a missing path, encountered an
    inaccessible path, or could not be performed.
    """

    operation: FilesystemOperation
    kind: FilesystemResultKind
    path: Path
    message: str
    entries: tuple[Path, ...] = ()
    content: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.operation,
            FilesystemOperation,
        ):
            raise TypeError(
                "FilesystemResult operation must be a "
                "FilesystemOperation."
            )

        if not isinstance(
            self.kind,
            FilesystemResultKind,
        ):
            raise TypeError(
                "FilesystemResult kind must be a "
                "FilesystemResultKind."
            )

        if not isinstance(self.path, Path):
            raise TypeError(
                "FilesystemResult path must be a Path."
            )

        if not isinstance(self.message, str):
            raise TypeError(
                "FilesystemResult message must be a str."
            )

        if not isinstance(self.entries, tuple):
            raise TypeError(
                "FilesystemResult entries must be a tuple."
            )

        for entry in self.entries:
            if not isinstance(entry, Path):
                raise TypeError(
                    "FilesystemResult entries must contain Path "
                    "instances."
                )

        if (
            self.content is not None
            and not isinstance(self.content, str)
        ):
            raise TypeError(
                "FilesystemResult content must be a str or None."
            )