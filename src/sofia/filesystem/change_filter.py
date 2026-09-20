"""Remove configured internal SQLite state noise from public workspace deltas.

Only the *projection* of a filesystem observation is filtered. The raw
snapshot remains preserved in the observation store for correct future diffs.
"""
from __future__ import annotations

from pathlib import Path

from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent

_SQLITE_SIDECARS = ("", "-wal", "-shm", "-journal")


def exclude_internal_state_changes(
    event: FilesystemChangeEvent, *, state_path: Path,
) -> FilesystemChangeEvent:
    """Suppress only the configured state database and its SQLite sidecars.

    Preserve baseline metadata, timestamps and ordering. Unrelated files,
    including other databases, remain visible. Case folding handles Windows
    paths even when tests execute on a case-sensitive host.
    """
    if not isinstance(event, FilesystemChangeEvent):
        raise TypeError("A FilesystemChangeEvent is required.")
    if not isinstance(state_path, Path):
        raise TypeError("Configured state_path must be a Path.")
    state = str(state_path.resolve()).casefold()
    ignored = frozenset(state + suffix for suffix in _SQLITE_SIDECARS)

    def relevant(change: FilesystemChange) -> bool:
        return str(change.path.resolve()).casefold() not in ignored

    added = tuple(change for change in event.new if relevant(change))
    modified = tuple(change for change in event.modified if relevant(change))
    removed = tuple(change for change in event.removed if relevant(change))
    if (added, modified, removed) == (event.new, event.modified, event.removed):
        return event
    return FilesystemChangeEvent(
        previous_observed_at=event.previous_observed_at,
        current_observed_at=event.current_observed_at,
        new=added, modified=modified, removed=removed,
        baseline_available=event.baseline_available,
    )
