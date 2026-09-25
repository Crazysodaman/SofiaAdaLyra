from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3


class FilesystemObservationError(Exception):
    """Raised when filesystem observation cannot be completed."""


@dataclass(frozen=True)
class FilesystemEntry:
    """
    Immutable observation of one filesystem file.

    This records filesystem facts only. It does not interpret why a
    file changed or who changed it.
    """

    path: Path
    size_bytes: int
    modified_at: datetime
    content_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError(
                "FilesystemEntry path must be a Path."
            )

        if not isinstance(self.size_bytes, int):
            raise TypeError(
                "FilesystemEntry size_bytes must be an int."
            )

        if self.size_bytes < 0:
            raise ValueError(
                "FilesystemEntry size_bytes must not be negative."
            )

        if not isinstance(self.modified_at, datetime):
            raise TypeError(
                "FilesystemEntry modified_at must be a datetime."
            )

        if self.modified_at.tzinfo is None:
            raise ValueError(
                "FilesystemEntry modified_at must be timezone-aware."
            )

        if not isinstance(self.content_hash, str):
            raise TypeError(
                "FilesystemEntry content_hash must be a string."
            )

        if len(self.content_hash) != 64:
            raise ValueError(
                "FilesystemEntry content_hash must be a SHA-256 digest."
            )


@dataclass(frozen=True)
class FilesystemObservation:
    """
    Immutable snapshot of the configured filesystem observation scope.
    """

    root: Path
    observed_at: datetime
    entries: tuple[FilesystemEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError(
                "FilesystemObservation root must be a Path."
            )

        if not isinstance(self.observed_at, datetime):
            raise TypeError(
                "FilesystemObservation observed_at must be a datetime."
            )

        if self.observed_at.tzinfo is None:
            raise ValueError(
                "FilesystemObservation observed_at must be timezone-aware."
            )

        if not isinstance(self.entries, tuple):
            raise TypeError(
                "FilesystemObservation entries must be a tuple."
            )

        previous_path: Path | None = None

        for entry in self.entries:
            if not isinstance(entry, FilesystemEntry):
                raise TypeError(
                    "FilesystemObservation entries must contain "
                    "FilesystemEntry instances."
                )

            if previous_path is not None:
                if str(entry.path).casefold() <= str(previous_path).casefold():
                    raise ValueError(
                        "FilesystemObservation entries must be sorted "
                        "by path."
                    )

            previous_path = entry.path


class FilesystemObserver:
    """
    Deterministic, read-only filesystem observation.

    Observation is deliberately separate from filesystem command
    execution. It records metadata and content hashes only. It does
    not modify files, execute files, or infer intent.
    """

    MAX_FILES = 1_000
    MAX_FILE_BYTES = 5 * 1024 * 1024

    _IGNORED_PARTS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "state",
    }

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError(
                "FilesystemObserver root must be a Path."
            )

        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def observe(self) -> FilesystemObservation:
        if not self._root.exists():
            raise FilesystemObservationError(
                f"Filesystem observation root does not exist: {self._root}"
            )

        if not self._root.is_dir():
            raise FilesystemObservationError(
                f"Filesystem observation root is not a directory: {self._root}"
            )

        entries: list[FilesystemEntry] = []

        paths = sorted(
            self._root.rglob("*"),
            key=lambda path: str(path).casefold(),
        )

        for path in paths:
            if len(entries) >= self.MAX_FILES:
                break

            if not path.is_file():
                continue

            if self._is_ignored(path):
                continue

            try:
                stat = path.stat()

                if stat.st_size > self.MAX_FILE_BYTES:
                    continue

                digest = self._hash_file(path)

            except (OSError, UnicodeError):
                continue

            entries.append(
                FilesystemEntry(
                    path=path,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        stat.st_mtime,
                        timezone.utc,
                    ),
                    content_hash=digest,
                )
            )

        return FilesystemObservation(
            root=self._root,
            observed_at=datetime.now(timezone.utc),
            entries=tuple(entries),
        )

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = sha256()

        with path.open("rb") as file_handle:
            while True:
                chunk = file_handle.read(1024 * 1024)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self._root)
        except ValueError:
            return True

        return any(
            part in self._IGNORED_PARTS
            for part in relative.parts
        )


class FilesystemObservationStore:
    """
    Persistent storage for filesystem observations.

    The store records snapshots independently from runtime continuity.
    """

    def __init__(self, state_path: Path | str) -> None:
        if not isinstance(state_path, (Path, str)):
            raise TypeError(
                "FilesystemObservationStore state_path must be a Path or str."
            )

        self._state_path = Path(state_path)

        self._connection = sqlite3.connect(
            self._state_path,
            check_same_thread=False,
        )

        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS filesystem_observation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root TEXT NOT NULL,
                observed_at TEXT NOT NULL
            )
            """
        )

        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS filesystem_observation_entry (
                observation_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (observation_id, path),
                FOREIGN KEY (observation_id)
                    REFERENCES filesystem_observation(id)
                    ON DELETE CASCADE
            )
            """
        )

        self._connection.commit()

    def record(
        self,
        observation: FilesystemObservation,
    ) -> None:
        if not isinstance(
            observation,
            FilesystemObservation,
        ):
            raise TypeError(
                "FilesystemObservationStore observation must be a "
                "FilesystemObservation."
            )

        cursor = self._connection.execute(
            """
            INSERT INTO filesystem_observation (
                root,
                observed_at
            )
            VALUES (?, ?)
            """,
            (
                str(observation.root),
                observation.observed_at.isoformat(),
            ),
        )

        observation_id = cursor.lastrowid

        for entry in observation.entries:
            self._connection.execute(
                """
                INSERT INTO filesystem_observation_entry (
                    observation_id,
                    path,
                    size_bytes,
                    modified_at,
                    content_hash
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    str(entry.path),
                    entry.size_bytes,
                    entry.modified_at.isoformat(),
                    entry.content_hash,
                ),
            )

        self._connection.commit()

    def latest(
        self,
        root: Path,
    ) -> FilesystemObservation | None:
        if not isinstance(root, Path):
            raise TypeError(
                "FilesystemObservationStore root must be a Path."
            )

        resolved_root = root.resolve()

        row = self._connection.execute(
            """
            SELECT id, observed_at
            FROM filesystem_observation
            WHERE root = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(resolved_root),),
        ).fetchone()

        if row is None:
            return None

        observation_id, observed_at = row

        entry_rows = self._connection.execute(
            """
            SELECT
                path,
                size_bytes,
                modified_at,
                content_hash
            FROM filesystem_observation_entry
            WHERE observation_id = ?
            ORDER BY path COLLATE NOCASE
            """,
            (observation_id,),
        ).fetchall()

        entries = tuple(
            FilesystemEntry(
                path=Path(path),
                size_bytes=size_bytes,
                modified_at=datetime.fromisoformat(
                    modified_at
                ),
                content_hash=content_hash,
            )
            for (
                path,
                size_bytes,
                modified_at,
                content_hash,
            ) in entry_rows
        )

        return FilesystemObservation(
            root=resolved_root,
            observed_at=datetime.fromisoformat(
                observed_at
            ),
            entries=entries,
        )

    def close(self) -> None:
        self._connection.close()