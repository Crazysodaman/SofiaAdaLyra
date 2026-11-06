"""Shared cross-platform lifetime lock for one named process per state database."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile
import stat
from threading import RLock

from sofia.platform.state.private_file import (
    assert_owner_private_path, assert_no_redirected_components,
    restrict_new_owner_private_path,
)


_PROCESS_GUARD = RLock()
_PROCESS_OWNED: set[str] = set()


class StateProcessLock:
    """OS-backed non-blocking lock released automatically on process death.

    The process-local registry closes a Windows-specific hole where byte-range
    locks may be re-acquired by another file handle in the same process.
    """

    def __init__(
        self, state_path: str | Path, *, resource: str,
        duplicate_error: type[RuntimeError] = RuntimeError,
        owner_label: str | None = None,
        lock_directory: Path | None = None,
    ) -> None:
        if not resource or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in resource):
            raise ValueError("resource must be a lowercase lock name")
        self.resource = resource
        self._duplicate_error = duplicate_error
        self._duplicate_message = f"another live Sofía {owner_label or resource} already owns this state"
        resolved = os.path.normcase(str(Path(state_path).resolve())).encode("utf-8")
        digest = sha256(resolved).hexdigest()[:24]
        directory = Path(tempfile.gettempdir()) if lock_directory is None else lock_directory
        if lock_directory is not None:
            assert_owner_private_path(directory, directory=True)
        self.path = directory / f"sofia-{resource}-{digest}.lock"
        self._key = os.path.normcase(str(self.path.resolve()))
        self._file = None

    def acquire(self) -> None:
        if self._file is not None:
            raise RuntimeError(f"{self.resource} process lock is already acquired")

        with _PROCESS_GUARD:
            if self._key in _PROCESS_OWNED:
                raise self._duplicate_error(self._duplicate_message)

            assert_no_redirected_components(self.path, include_leaf=True)
            flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
            try:
                descriptor = os.open(self.path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                descriptor = os.open(self.path, flags)
                created = False
            handle = os.fdopen(descriptor, "r+b")
            try:
                details = os.fstat(handle.fileno())
                if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                    raise PermissionError("process lock must be a private regular file with one link")
                if os.name != "nt" and details.st_uid != os.geteuid():
                    raise PermissionError("process lock belongs to another OS user")
                if created:
                    restrict_new_owner_private_path(self.path, directory=False)
                assert_owner_private_path(self.path, directory=False)
                after = self.path.stat(follow_symlinks=False)
                if (details.st_dev, details.st_ino) != (after.st_dev, after.st_ino):
                    raise PermissionError("process lock changed while opening")
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.seek(0)
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)

                if os.name == "nt":
                    import msvcrt

                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError as exc:
                        raise self._duplicate_error(self._duplicate_message) from exc
                else:
                    import fcntl

                    try:
                        fcntl.flock(
                            handle.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB,
                        )
                    except OSError as exc:
                        raise self._duplicate_error(self._duplicate_message) from exc
            except Exception:
                handle.close()
                raise

            self._file = handle
            _PROCESS_OWNED.add(self._key)

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return

        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._file = None
            with _PROCESS_GUARD:
                _PROCESS_OWNED.discard(self._key)

    def __enter__(self) -> "StateProcessLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
