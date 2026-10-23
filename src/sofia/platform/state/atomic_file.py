"""Crash-safe file replacement for authoritative local state."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time


def atomic_write_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    attempts: int = 8,
    initial_delay_seconds: float = 0.025,
) -> None:
    """Durably replace one text file without exposing a partial write.

    The temporary file is created in the target directory so the final
    os.replace stays on the same filesystem. File contents are flushed through
    fsync before replacement. Transient Windows/SMB sharing violations are
    retried without deleting the existing target.
    """
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("path must identify a file")
    if not isinstance(content, str):
        raise TypeError("content must be text")
    if not isinstance(encoding, str) or not encoding.strip():
        raise ValueError("encoding must be non-empty text")
    if type(attempts) is not int or attempts < 1:
        raise ValueError("attempts must be a positive integer")
    if (
        not isinstance(initial_delay_seconds, (int, float))
        or initial_delay_seconds < 0
    ):
        raise ValueError("initial_delay_seconds must be non-negative")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        delay = float(initial_delay_seconds)
        last_error: PermissionError | None = None
        for attempt in range(attempts):
            try:
                os.replace(temporary, target)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt == attempts - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 0.25)
        if last_error is not None:
            raise last_error
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def retire_legacy_file(path: Path) -> None:
    """Retain imported evidence without overwriting an earlier backup."""
    destination = path.with_name(path.name + ".migrated")
    index = 1
    while destination.exists():
        destination = path.with_name(path.name + f".migrated.{index}")
        index += 1
    path.replace(destination)
