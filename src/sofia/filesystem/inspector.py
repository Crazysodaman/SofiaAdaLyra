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

    Safety limits are enforced inside the capability and cannot be
    increased by the cognitive system.
    """

    MAX_FILE_BYTES = 5 * 1024 * 1024
    MAX_DIRECTORY_ENTRIES = 500
    MAX_SEARCH_RESULTS = 100
    MAX_SEARCH_ENTRIES_INSPECTED = 10_000
    MAX_SEARCH_DEPTH = 32
    MAX_SEARCH_PATTERN_LENGTH = 256

    def __init__(
        self,
        root: Path,
        authorized: bool = False,
    ) -> None:
        if not isinstance(root, Path):
            raise TypeError(
                "FilesystemInspector root must be a Path."
            )

        if not isinstance(authorized, bool):
            raise TypeError(
                "FilesystemInspector authorized must be a bool."
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

        Enumeration is bounded by MAX_DIRECTORY_ENTRIES.
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

        entries: list[Path] = []
        limit_reached = False

        try:
            iterator = authorized_path.iterdir()

            for entry in iterator:
                if self._is_link_like(entry):
                    continue

                if len(entries) >= self.MAX_DIRECTORY_ENTRIES:
                    limit_reached = True
                    break

                entries.append(entry)

        except PermissionError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )
        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        entries.sort(
            key=lambda entry: entry.name.casefold()
        )

        if limit_reached:
            return FilesystemResult(
                operation=FilesystemOperation.LIST_DIRECTORY,
                kind=FilesystemResultKind.LIMIT_REACHED,
                path=requested_path,
                message=(
                    "Directory inspection reached the maximum "
                    f"entry limit of {self.MAX_DIRECTORY_ENTRIES}. "
                    "The returned entries are incomplete."
                ),
                entries=tuple(entries),
            )

        return FilesystemResult(
            operation=FilesystemOperation.LIST_DIRECTORY,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message="Directory inspection completed.",
            entries=tuple(entries),
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
            if not authorized_path.exists():
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

        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.INSPECT_PATH,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

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
        Read a UTF-8 text file inside the authorized filesystem scope.

        The file size is checked before reading.

        The actual read is additionally bounded so a file that grows
        between the size check and the read cannot cause an unbounded
        read.
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

        try:
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

            size = authorized_path.stat().st_size

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

        if size > self.MAX_FILE_BYTES:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.LIMIT_REACHED,
                path=requested_path,
                message=(
                    "The requested file is "
                    f"{size} bytes, which exceeds the maximum "
                    f"read limit of {self.MAX_FILE_BYTES} bytes. "
                    "The file was not read."
                ),
            )

        try:
            with authorized_path.open(
                "rb"
            ) as file_handle:
                data = file_handle.read(
                    self.MAX_FILE_BYTES + 1
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

        if len(data) > self.MAX_FILE_BYTES:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.LIMIT_REACHED,
                path=requested_path,
                message=(
                    "The file exceeded the maximum read limit "
                    "while being read. The complete file was not "
                    "returned."
                ),
            )

        try:
            content = data.decode("utf-8")
        except UnicodeError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.READ_FILE,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=(
                    "The file could not be decoded as UTF-8: "
                    f"{exc}"
                ),
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
        Search for filesystem entries matching a pathlib pattern.

        Search is bounded by:
        - MAX_SEARCH_RESULTS
        - MAX_SEARCH_ENTRIES_INSPECTED
        - MAX_SEARCH_DEPTH
        - MAX_SEARCH_PATTERN_LENGTH

        Links are not followed during recursive traversal.
        """

        if not isinstance(pattern, str):
            raise TypeError(
                "FilesystemInspector search pattern must be a str."
            )

        pattern = pattern.strip()

        if not pattern:
            raise ValueError(
                "FilesystemInspector search pattern must not be empty."
            )

        if len(pattern) > self.MAX_SEARCH_PATTERN_LENGTH:
            raise ValueError(
                "FilesystemInspector search pattern exceeds the "
                f"maximum length of "
                f"{self.MAX_SEARCH_PATTERN_LENGTH} characters."
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

        try:
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

        except OSError as exc:
            return FilesystemResult(
                operation=FilesystemOperation.SEARCH_FILES,
                kind=FilesystemResultKind.INACCESSIBLE,
                path=requested_path,
                message=str(exc),
            )

        matches: list[Path] = []
        inspected = 0
        limit_reason: str | None = None

        stack: list[tuple[Path, int]] = [
            (authorized_path, 0)
        ]

        while stack:
            current_path, depth = stack.pop()

            try:
                children = list(
                    current_path.iterdir()
                )
            except PermissionError as exc:
                return FilesystemResult(
                    operation=FilesystemOperation.SEARCH_FILES,
                    kind=FilesystemResultKind.INACCESSIBLE,
                    path=requested_path,
                    message=(
                        "Filesystem search encountered an "
                        f"inaccessible directory: {exc}"
                    ),
                    entries=tuple(matches),
                )
            except OSError as exc:
                return FilesystemResult(
                    operation=FilesystemOperation.SEARCH_FILES,
                    kind=FilesystemResultKind.INACCESSIBLE,
                    path=requested_path,
                    message=str(exc),
                    entries=tuple(matches),
                )

            children.sort(
                key=lambda entry: entry.name.casefold(),
                reverse=True,
            )

            for candidate in children:
                if self._is_link_like(candidate):
                    continue

                inspected += 1

                if inspected > self.MAX_SEARCH_ENTRIES_INSPECTED:
                    limit_reason = (
                        "maximum search inspection limit reached"
                    )
                    break

                if candidate.match(pattern):
                    matches.append(candidate)

                    if len(matches) >= self.MAX_SEARCH_RESULTS:
                        limit_reason = (
                            "maximum search result limit reached"
                        )
                        break

                try:
                    is_directory = candidate.is_dir()
                except OSError:
                    is_directory = False

                if (
                    is_directory
                    and depth < self.MAX_SEARCH_DEPTH
                ):
                    stack.append(
                        (
                            candidate,
                            depth + 1,
                        )
                    )

            if limit_reason is not None:
                break

        matches.sort(
            key=lambda entry: str(entry).casefold()
        )

        if limit_reason is not None:
            return FilesystemResult(
                operation=FilesystemOperation.SEARCH_FILES,
                kind=FilesystemResultKind.LIMIT_REACHED,
                path=requested_path,
                message=(
                    "Filesystem search stopped because the "
                    f"{limit_reason}. "
                    f"Results returned: {len(matches)}. "
                    f"Entries inspected: {inspected}. "
                    f"Maximum depth: {self.MAX_SEARCH_DEPTH}. "
                    "The results are incomplete."
                ),
                entries=tuple(matches),
            )

        return FilesystemResult(
            operation=FilesystemOperation.SEARCH_FILES,
            kind=FilesystemResultKind.SUCCESS,
            path=requested_path,
            message=(
                "Filesystem search completed. "
                f"Entries inspected: {inspected}."
            ),
            entries=tuple(matches),
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
            return path

        return self._root / path

    def _authorize_path(
        self,
        path: Path,
    ) -> Path | None:
        try:
            if path.exists() and self._is_link_like(path):
                return None

            resolved = path.resolve(
                strict=False
            )

        except (
            OSError,
            RuntimeError,
        ):
            return None

        if not self._is_within_root(resolved):
            return None

        return resolved

    def _is_within_root(
        self,
        path: Path,
    ) -> bool:
        try:
            path.resolve(
                strict=False
            ).relative_to(
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
    def _is_link_like(
        path: Path,
    ) -> bool:
        try:
            if path.is_symlink():
                return True

            is_junction = getattr(
                path,
                "is_junction",
                None,
            )

            if callable(is_junction):
                return bool(is_junction())

        except OSError:
            return True

        return False

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