"""Canonical memory state path validation and single-writer fencing.

The low-level candidate store historically supported disposable fixture
bootstrap. Production and restart paths need a stronger contract: one exact
existing canonical file, owner-private permissions, no redirected components,
and at most one live writer. This module owns that boundary so memory code
does not silently recreate or share a database.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat

from sofia.platform.state.canonical_sqlite import CanonicalStateUnavailable
from sofia.platform.state.private_file import (
    assert_no_redirected_components,
    assert_owner_private_path,
    ensure_owner_private_directory,
)


class MemoryStateUnavailable(CanonicalStateUnavailable):
    """The canonical memory database is missing or cannot be safely opened."""


class MemoryStateCorrupt(MemoryStateUnavailable):
    """The canonical memory database exists but is truncated or malformed."""


class MemoryStateIncompatible(MemoryStateUnavailable):
    """The canonical memory database has an unsupported/legacy schema."""


class LegacyMemoryState(MemoryStateIncompatible):
    """Legacy memory state requires quarantine rather than automatic import."""


class MemoryStateUnsafe(PermissionError):
    """The memory path or its permissions do not satisfy the canonical policy."""


class MemoryWriterConflict(PermissionError):
    """Another live owner already holds the canonical memory writer role."""


_IDENTITY_ASSETS = {
    "identity.json",
    "constitution.md",
    "constitution.sha256",
    "personality.json",
    "avatar.json",
}


def validate_canonical_memory_path(
    path: Path | str,
    *,
    expected_path: Path | str | None = None,
    require_owner_private: bool = True,
) -> Path:
    """Return the exact absolute canonical memory path or refuse it.

    ``expected_path`` binds callers to the configured state location instead
    of accepting any caller-supplied SQLite file. The check intentionally runs
    before opening SQLite so a redirected path can never become a writer.
    """
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise MemoryStateUnsafe("canonical memory state path is required")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = candidate.absolute()
    try:
        assert_no_redirected_components(candidate, include_leaf=True)
    except PermissionError as exc:
        raise MemoryStateUnsafe(
            "canonical memory state path contains filesystem redirection"
        ) from exc
    if expected_path is not None:
        expected = Path(expected_path)
        if not expected.is_absolute():
            expected = expected.absolute()
        if candidate != expected:
            raise MemoryStateUnsafe(
                "memory state path does not match the configured canonical state"
            )
    if candidate.name.casefold() in _IDENTITY_ASSETS:
        raise MemoryStateUnsafe(
            "protected identity assets are not canonical memory state"
        )
    if candidate.name.casefold().startswith("sofia.db-"):
        raise MemoryStateUnsafe(
            "SQLite sidecar files are not canonical memory state"
        )
    if candidate.exists() or candidate.is_symlink():
        try:
            details = candidate.stat(follow_symlinks=False)
        except FileNotFoundError as exc:
            raise MemoryStateUnavailable(
                "canonical memory state is unavailable"
            ) from exc
        if not stat.S_ISREG(details.st_mode):
            raise MemoryStateUnsafe(
                "canonical memory state is not a regular file"
            )
        if require_owner_private:
            try:
                assert_owner_private_path(candidate.parent, directory=True)
            except PermissionError as exc:
                raise MemoryStateUnsafe(
                    "canonical memory directory is not owner-private"
                ) from exc
    return candidate


def ensure_memory_file_private(path: Path | str) -> None:
    """Tighten a newly created SQLite file and verify owner-private access."""
    target = Path(path)
    if os.name == "nt":
        assert_owner_private_path(target, directory=False)
        return
    try:
        target.chmod(0o600)
    except OSError as exc:
        raise MemoryStateUnsafe(
            "canonical memory state permissions cannot be restricted"
        ) from exc
    assert_owner_private_path(target, directory=False)


def _lock_path(state_path: Path) -> Path:
    return Path(str(state_path) + ".memory-writer.lock")


def _open_lock_file(path: Path) -> int:
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise MemoryStateUnsafe("memory writer lock path is redirected")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    if os.name == "nt":
        # The lock file is removed when the last handle closes (including
        # owner-process death), so a stale writer name cannot block recovery.
        flags |= getattr(os, "O_TEMPORARY", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
    else:
        descriptor = os.open(path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        except OSError:
            pass
    return descriptor


def _try_lock(descriptor: int) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(descriptor: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        pass


class MemoryWriterLease:
    """Exclusive process/host writer ownership of one canonical memory file."""

    def __init__(self, state_path: Path | str) -> None:
        self.state_path = Path(state_path).absolute()
        self._lock_path = _lock_path(self.state_path)
        self._descriptor: int | None = None
        try:
            descriptor = _open_lock_file(self._lock_path)
        except OSError as exc:
            raise MemoryWriterConflict(
                "canonical memory writer ownership cannot be acquired"
            ) from exc
        if not _try_lock(descriptor):
            os.close(descriptor)
            raise MemoryWriterConflict(
                "another live canonical memory writer already owns this state"
            )
        self._descriptor = descriptor

    def release(self) -> None:
        descriptor = self._descriptor
        if descriptor is None:
            return
        self._descriptor = None
        _unlock(descriptor)
        os.close(descriptor)

    def __enter__(self) -> "MemoryWriterLease":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.release()
        return False

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


def has_live_writer(state_path: Path | str) -> bool:
    """Observe without creating a persistent lock file whether a writer exists."""
    path = _lock_path(Path(state_path).absolute())
    if not path.exists():
        return False
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise MemoryStateUnsafe("memory writer lock path is redirected")
    try:
        descriptor = _open_lock_file(path)
    except OSError:
        # A lock file that cannot even be opened is itself evidence of
        # another owner or an unsafe lock path.
        return True
    acquired = _try_lock(descriptor)
    try:
        if acquired:
            _unlock(descriptor)
    finally:
        os.close(descriptor)
    return not acquired


def assert_no_live_writer(state_path: Path | str) -> None:
    if has_live_writer(state_path):
        raise MemoryWriterConflict(
            "canonical memory state is owned by a live writer"
        )


@contextmanager
def owner_private_memory_directory(directory: Path | str):
    target = Path(directory)
    ensure_owner_private_directory(target)
    yield target
