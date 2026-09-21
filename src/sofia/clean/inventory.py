"""Read-only, fail-closed cleanup candidate inventory.

No deletion, filesystem mutation, dead-code inference or approval is provided.
Only explicitly named files inside an ordinary, non-symlink repository qualify.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
import stat


class Disposition(str, Enum):
    REVIEW = "review"
    PROTECTED = "protected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class InventoryRecord:
    requested_path: str
    disposition: Disposition
    reason: str
    size_bytes: int | None = None


_PROTECTED_COMPONENTS = frozenset({
    ".git", ".env", "secrets", "secret", "credentials", "state", "backup", "backups",
})
_PROTECTED_PREFIXES = (
    ("src", "sofia", "constitution"),
    ("src", "sofia", "identity"),
    ("src", "sofia", "data"),
)
_PROTECTED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".key", ".pem")


def _parts(path: str) -> tuple[str, ...] | None:
    """Accept only unambiguous repository-relative POSIX paths."""
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path or ":" in path:
        return None
    if path.startswith("/") or "//" in path or path.endswith("/"):
        return None
    parts = tuple(path.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        return None
    if PurePosixPath(path).is_absolute():
        return None
    return parts


def _protected(parts: tuple[str, ...]) -> bool:
    lowered = tuple(part.casefold() for part in parts)
    return (
        any(part in _PROTECTED_COMPONENTS or part.startswith(".env.") for part in lowered)
        or any(lowered[:len(prefix)] == prefix for prefix in _PROTECTED_PREFIXES)
        or lowered[-1].endswith(_PROTECTED_SUFFIXES)
    )


def inspect_candidates(root: Path, candidates: tuple[str, ...]) -> tuple[InventoryRecord, ...]:
    """Inspect metadata only. A REVIEW result is never permission to remove a file.

    Symlinks in any path component are rejected rather than followed. Failures
    stay visible as UNKNOWN. Nothing is opened for writing or deleted.
    """
    if not isinstance(root, Path):
        raise TypeError("root must be pathlib.Path")
    if not isinstance(candidates, tuple):
        raise TypeError("candidates must be a tuple")
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise ValueError("repository root is unavailable") from exc
    if not stat.S_ISDIR(root_mode) or stat.S_ISLNK(root_mode):
        raise ValueError("repository root must be a real directory")
    records: list[InventoryRecord] = []
    for request in candidates:
        parts = _parts(request)
        if parts is None:
            records.append(InventoryRecord(str(request), Disposition.UNKNOWN, "invalid relative path"))
            continue
        if _protected(parts):
            records.append(InventoryRecord(request, Disposition.PROTECTED, "protected path or data"))
            continue
        current = root
        result: InventoryRecord | None = None
        for index, part in enumerate(parts):
            current = current / part
            try:
                mode = current.lstat().st_mode
            except OSError:
                result = InventoryRecord(request, Disposition.UNKNOWN, "missing or unreadable path")
                break
            if stat.S_ISLNK(mode):
                result = InventoryRecord(request, Disposition.UNKNOWN, "symlink is not inspected")
                break
            if index < len(parts) - 1 and not stat.S_ISDIR(mode):
                result = InventoryRecord(request, Disposition.UNKNOWN, "parent is not a directory")
                break
            if index == len(parts) - 1:
                if not stat.S_ISREG(mode):
                    result = InventoryRecord(request, Disposition.UNKNOWN, "not a regular file")
                else:
                    try:
                        size = current.lstat().st_size
                    except OSError:
                        result = InventoryRecord(request, Disposition.UNKNOWN, "metadata unavailable")
                    else:
                        result = InventoryRecord(request, Disposition.REVIEW,
                                                 "metadata only; usage and deletion not established", size)
        assert result is not None
        records.append(result)
    return tuple(records)
