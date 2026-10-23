"""Shared cross-platform lifetime lock for one named process per state database."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile
from threading import RLock


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
    ) -> None:
        if not resource or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in resource):
            raise ValueError("resource must be a lowercase lock name")
        self.resource = resource
        self._duplicate_error = duplicate_error
        self._duplicate_message = f"another live Sofía {owner_label or resource} already owns this state"
        resolved = os.path.normcase(str(Path(state_path).resolve())).encode("utf-8")
        digest = sha256(resolved).hexdigest()[:24]
        self.path = Path(tempfile.gettempdir()) / f"sofia-{resource}-{digest}.lock"
        self._key = os.path.normcase(str(self.path.resolve()))
        self._file = None

    def acquire(self) -> None:
        if self._file is not None:
            raise RuntimeError(f"{self.resource} process lock is already acquired")

        with _PROCESS_GUARD:
            if self._key in _PROCESS_OWNED:
                raise self._duplicate_error(self._duplicate_message)

            handle = self.path.open("a+b")
            try:
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
