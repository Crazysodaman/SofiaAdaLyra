from pathlib import Path

from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResult,
    FilesystemResultKind,
)


class FilesystemInspector:
    """
    Read-only filesystem inspection capability.

    The inspector is permanently scoped to an authorized root.
    It does not modify filesystem state.
    """

    def __init__(
        self,
        root: Path,
        authorized: bool = False,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError(
                "FilesystemInspector root must be a Path."
            )

        self._root = root.resolve()
        self._authorized = authorized

    @property
    def root(self) -> Path:
        return self._root

    @property
    def authorized(self) -> bool:
        return self._authorized

    def list_directory(
        self,
        path: Path | str = ".",
    ) -> FilesystemResult:
        """
        List entries in an authorized directory.
        """

        requested_path = self._normalize_path(path)

        if not self._authorized:
            return self._unauthorized(
                FilesystemOperation.LIST_DIRECTORY,
                requested_path,
            )

        authorized_path = self._authorize_path(
            requested_path
        )

        if authorized_path is None:
            return self._unauthorized(
                FilesystemOperation.LIST_DIRECTORY,
                requested_path,
            )

        if not authorized_path.exists():
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.NOT_FOUND,
                path=requested_path,
                message="The requested path does not exist.",
            )

        if not authorized_path.is_dir():
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message="The requested path is not a directory.",
            )

        try:
            entries = tuple(
                sorted(
                    authorized_path.iterdir(),
                    key=lambda entry: entry.name.lower(),
                )
            )
        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        return FilesystemResult(
            operation=FilesystemOperation.LIST_DIRECTORY,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message="Directory inspection completed.",
            entries=entries,
        )

    def inspect_path(
        self,
        path: Path | str,
    ) -> FilesystemResult:
        """
        Inspect whether an authorized path exists and what kind
        of filesystem object it represents.
        """

        requested_path = self._normalize_path(path)

        if not self._authorized:
            return self._unauthorized(
                FilesystemOperation.INSPECT_PATH,
                requested_path,
            )

        authorized_path = self._authorize_path(
            requested_path
        )

        if authorized_path is None:
            return self._unauthorized(
                FilesystemOperation.INSPECT_PATH,
                requested_path,
            )

        try:
            exists = authorized_path.exists()
        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.INSPECT_PATH,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        if not exists:
            return FilesystemResult(
                operation=FilesystemOperation.INSPECT_PATH,
                kind=FilesystemResultKind.NOT_FOUND,
                path=requested_path,
                message="The requested path does not exist.",
            )

        if authorized_path.is_dir():
            object_type = "directory"
        elif authorized_path.is_file():
            object_type = "file"
        else:
            object_type = "other"

        return FilesystemResult(
            operation=FilesystemOperation.INSPECT_PATH,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message=(
                f"The requested path exists and is a "
                f"{object_type}."
            ),
        )

    def read_file(
        self,
        path: Path | str,
    ) -> FilesystemResult:
        """
        Read a text file inside the authorized filesystem scope.

        This operation never writes to the filesystem.
        """

        requested_path = self._normalize_path(path)

        if not self._authorized:
            return self._unauthorized(
                FilesystemOperation.READ_FILE,
                requested_path,
            )

        authorized_path = self._authorize_path(
            requested_path
        )

        if authorized_path is None:
            return self._unauthorized(
                FilesystemOperation.READ_FILE,
                requested_path,
            )

        if not authorized_path.exists():
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.NOT_FOUND,
                path=requested_path,
                message="The requested file does not exist.",
            )

        if not authorized_path.is_file():
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message="The requested path is not a file.",
            )

        try:
            content = authorized_path.read_text(
                encoding="utf-8"
            )
        except PermissionError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )
        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )
        except UnicodeError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        return FilesystemResult(
            operation=FilesystemOperation.READ_FILE,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message="File read completed.",
            content=content,
        )

    def search_files(
        self,
        pattern: str,
        path: Path | str = ".",
    ) -> FilesystemResult:
        """
        Search for filesystem entries matching a pathlib glob pattern.

        Search is strictly read-only and remains inside the authorized root.
        """

        if not isinstance(pattern, str):
            raise TypeError(
                "FilesystemInspector search pattern must be a str."
            )

        if not pattern:
            raise ValueError(
                "FilesystemInspector search pattern must not be empty."
            )

        requested_path = self._normalize_path(path)

        if not self._authorized:
            return self._unauthorized(
                FilesystemOperation.SEARCH_FILES,
                requested_path,
            )

        authorized_path = self._authorize_path(
            requested_path
        )

        if authorized_path is None:
            return self._unauthorized(
                FilesystemOperation.SEARCH_FILES,
                requested_path,
            )

        if not authorized_path.exists():
            return FilesystemResult(
                operation=FilesystemOperation.SEARCH_FILES,
                kind=FilesystemResultKind.NOT_FOUND,
                path=requested_path,
                message="The search root does not exist.",
            )

        if not authorized_path.is_dir():
            return FilesystemResult(
                operation=FilesystemOperation.SEARCH_FILES,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message="The search root is not a directory.",
            )

        try:
            matches = tuple(
                sorted(
                    (
                        candidate
                        for candidate in authorized_path.rglob(pattern)
                        if self._is_within_root(candidate)
                    ),
                    key=lambda entry: str(entry).lower(),
                )
            )
        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.SEARCH_FILES,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        return FilesystemResult(
            operation=FilesystemOperation.SEARCH_FILES,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message="Filesystem search completed.",
            entries=matches,
        )

    def _normalize_path(
        self,
        path: Path | str,
    ) -> Path:
        if isinstance(path, str):
            path = Path(path)

        if not isinstance(path, Path):
            raise TypeError(
                "Filesystem path must be a Path or str."
            )

        if path.is_absolute():
            return path.resolve(strict=False)

        return (
            self._root / path
        ).resolve(strict=False)

    def _authorize_path(
        self,
        path: Path,
    ) -> Path | None:
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError):
            return None

        if not self._is_within_root(resolved):
            return None

        return resolved

    def _is_within_root(
        self,
        path: Path,
    ) -> bool:
        try:
            path.resolve(strict=False).relative_to(
                self._root
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
        ):
            return False

        return True

    @staticmethod
    def _unauthorized(
        operation: FilesystemOperation,
        path: Path,
    ) -> FilesystemResult:
        return FilesystemResult(
            operation=operation,
            kind=FilesystemResultKind.UNAUTHORIZED,
            path=path,
            message=(
                "Filesystem inspection is not authorized "
                "for this operation."
            ),
        )