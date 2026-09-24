"""Cross-platform lifetime lock for one live Discord process per state DB."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile


class DiscordProcessLock:
    """OS-backed non-blocking lock released automatically on process death."""

    def __init__(self, state_path: str | Path) -> None:
        resolved = os.path.normcase(str(Path(state_path).resolve())).encode("utf-8")
        digest = sha256(resolved).hexdigest()[:24]
        self.path = Path(tempfile.gettempdir()) / f"sofia-discord-{digest}.lock"
        self._file = None

    def acquire(self) -> None:
        if self._file is not None:
            raise RuntimeError("Discord process lock is already acquired")
        handle = self.path.open("a+b")
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise RuntimeError(
                        "another live Sofía Discord process already owns this state"
                    ) from exc
            else:
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise RuntimeError(
                        "another live Sofía Discord process already owns this state"
                    ) from exc
        except Exception:
            handle.close()
            raise
        self._file = handle

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

    def __enter__(self) -> "DiscordProcessLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
