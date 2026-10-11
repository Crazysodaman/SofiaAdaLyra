"""Canonical SQLite path validation and explicit first-install bootstrap.

Ordinary state owners must never create ``sofia.db``. Creation is reserved
for configuration bootstrap, which atomically publishes a closed SQLite file.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import os
from pathlib import Path
import sqlite3
import stat
import tempfile


class CanonicalStateUnavailable(FileNotFoundError):
    """The configured canonical SQLite state is missing or unsafe."""


def _absolute(path: Path | str) -> Path:
    return Path(path).absolute()


def _reject_redirected_components(path: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise CanonicalStateUnavailable(
                f"canonical SQLite path is redirected by a symbolic link: {current}"
            )
        parent = current.parent
        if parent == current:
            return
        current = parent


def require_existing_sqlite(path: Path | str) -> tuple[Path, tuple[int, int]]:
    """Return an existing regular SQLite path and stable file identity."""
    value = _absolute(path)
    _reject_redirected_components(value)
    try:
        details = value.stat(follow_symlinks=False)
    except FileNotFoundError as exc:
        raise CanonicalStateUnavailable(
            f"canonical SQLite state is unavailable: {value}"
        ) from exc
    if not stat.S_ISREG(details.st_mode):
        raise CanonicalStateUnavailable(
            f"canonical SQLite state is not a regular file: {value}"
        )
    return value, (int(details.st_dev), int(details.st_ino))


@dataclass(slots=True)
class CanonicalSQLiteGuard:
    """Pin one canonical SQLite file and refuse loss or replacement."""

    path: Path | str
    _absolute_path: Path = field(init=False, repr=False)
    _identity: tuple[int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._absolute_path, self._identity = require_existing_sqlite(self.path)

    @property
    def canonical_path(self) -> Path:
        return self._absolute_path

    def validate(self) -> Path:
        current, identity = require_existing_sqlite(self._absolute_path)
        if identity != self._identity:
            raise CanonicalStateUnavailable(
                "canonical SQLite state was replaced after this owner started"
            )
        return current

    def connect(
        self,
        *,
        timeout: float = 10.0,
        check_same_thread: bool = True,
        factory: type[sqlite3.Connection] = sqlite3.Connection,
    ) -> sqlite3.Connection:
        path = self.validate()
        database = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=timeout,
            check_same_thread=check_same_thread, factory=factory,
        )
        # A canonical file can be swapped between path validation and the
        # actual sqlite3_open call. Do not hand an owner a handle to an
        # unexpected replacement. Revalidation failure must close the
        # just-opened connection, including on Windows where open handles
        # can otherwise obstruct a supervised restore.
        try:
            self.validate()
        except BaseException:
            database.close()
            raise
        return database


def bootstrap_canonical_sqlite(path: Path | str) -> Path:
    """Atomically create empty state for an authorized first installation."""
    target = _absolute(path)
    _reject_redirected_components(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        return require_existing_sqlite(target)[0]

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".bootstrap", dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(str(temporary), timeout=10)) as database:
            database.execute("PRAGMA application_id = 0x534F4649")
            database.commit()
        with temporary.open("rb") as persisted:
            os.fsync(persisted.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            require_existing_sqlite(target)
    finally:
        temporary.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(temporary) + suffix).unlink(missing_ok=True)
    return require_existing_sqlite(target)[0]
