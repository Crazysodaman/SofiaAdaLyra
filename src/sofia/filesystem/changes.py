from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sofia.filesystem.observation import (
    FilesystemEntry,
    FilesystemObservation,
)


class FilesystemChangeKind(str, Enum):
    NEW = "new"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass(frozen=True)
class FilesystemChange:
    """
    One deterministic filesystem delta.
    """

    kind: FilesystemChangeKind
    path: Path
    previous: FilesystemEntry | None = None
    current: FilesystemEntry | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.kind,
            FilesystemChangeKind,
        ):
            raise TypeError(
                "FilesystemChange kind must be a FilesystemChangeKind."
            )

        if not isinstance(self.path, Path):
            raise TypeError(
                "FilesystemChange path must be a Path."
            )

        if self.kind is FilesystemChangeKind.NEW:
            if self.current is None:
                raise ValueError(
                    "New filesystem changes require current evidence."
                )

            if self.previous is not None:
                raise ValueError(
                    "New filesystem changes cannot contain previous evidence."
                )

        elif self.kind is FilesystemChangeKind.MODIFIED:
            if self.previous is None or self.current is None:
                raise ValueError(
                    "Modified filesystem changes require both previous "
                    "and current evidence."
                )

        elif self.kind is FilesystemChangeKind.REMOVED:
            if self.previous is None:
                raise ValueError(
                    "Removed filesystem changes require previous evidence."
                )

            if self.current is not None:
                raise ValueError(
                    "Removed filesystem changes cannot contain current evidence."
                )


@dataclass(frozen=True)
class FilesystemChangeEvent:
    """
    Coherent aggregate of one observation transition.

    The event contains facts only. It does not assign intent, cause,
    authorship, or significance to the changes.
    """

    previous_observed_at: object | None
    current_observed_at: object
    new: tuple[FilesystemChange, ...]
    modified: tuple[FilesystemChange, ...]
    removed: tuple[FilesystemChange, ...]
    baseline_available: bool

    def __post_init__(self) -> None:
        if not isinstance(
            self.new,
            tuple,
        ):
            raise TypeError(
                "FilesystemChangeEvent new must be a tuple."
            )

        if not isinstance(
            self.modified,
            tuple,
        ):
            raise TypeError(
                "FilesystemChangeEvent modified must be a tuple."
            )

        if not isinstance(
            self.removed,
            tuple,
        ):
            raise TypeError(
                "FilesystemChangeEvent removed must be a tuple."
            )

        if not isinstance(
            self.baseline_available,
            bool,
        ):
            raise TypeError(
                "FilesystemChangeEvent baseline_available must be a bool."
            )

        if not self.baseline_available:
            if (
                self.new
                or self.modified
                or self.removed
            ):
                raise ValueError(
                    "An event without a baseline cannot contain deltas."
                )

    @property
    def has_changes(self) -> bool:
        return bool(
            self.new
            or self.modified
            or self.removed
        )

    @property
    def total_changes(self) -> int:
        return (
            len(self.new)
            + len(self.modified)
            + len(self.removed)
        )


def detect_changes(
    previous: FilesystemObservation | None,
    current: FilesystemObservation,
) -> FilesystemChangeEvent:
    """
    Compare two observations deterministically.

    A missing previous observation means there is no evidence from
    which changes can be established. That is represented as a
    baseline-unavailable event rather than falsely calling every
    current file "new".
    """

    if previous is not None:
        if previous.root != current.root:
            raise ValueError(
                "Filesystem observations must have the same root."
            )

    if previous is None:
        return FilesystemChangeEvent(
            previous_observed_at=None,
            current_observed_at=current.observed_at,
            new=(),
            modified=(),
            removed=(),
            baseline_available=False,
        )

    previous_by_path = {
        entry.path: entry
        for entry in previous.entries
    }

    current_by_path = {
        entry.path: entry
        for entry in current.entries
    }

    new: list[FilesystemChange] = []
    modified: list[FilesystemChange] = []
    removed: list[FilesystemChange] = []

    for path in sorted(
        current_by_path.keys() - previous_by_path.keys(),
        key=lambda value: str(value).casefold(),
    ):
        new.append(
            FilesystemChange(
                kind=FilesystemChangeKind.NEW,
                path=path,
                current=current_by_path[path],
            )
        )

    for path in sorted(
        current_by_path.keys() & previous_by_path.keys(),
        key=lambda value: str(value).casefold(),
    ):
        old_entry = previous_by_path[path]
        current_entry = current_by_path[path]

        if (
            old_entry.size_bytes != current_entry.size_bytes
            or old_entry.modified_at != current_entry.modified_at
            or old_entry.content_hash != current_entry.content_hash
        ):
            modified.append(
                FilesystemChange(
                    kind=FilesystemChangeKind.MODIFIED,
                    path=path,
                    previous=old_entry,
                    current=current_entry,
                )
            )

    for path in sorted(
        previous_by_path.keys() - current_by_path.keys(),
        key=lambda value: str(value).casefold(),
    ):
        removed.append(
            FilesystemChange(
                kind=FilesystemChangeKind.REMOVED,
                path=path,
                previous=previous_by_path[path],
            )
        )

    return FilesystemChangeEvent(
        previous_observed_at=previous.observed_at,
        current_observed_at=current.observed_at,
        new=tuple(new),
        modified=tuple(modified),
        removed=tuple(removed),
        baseline_available=True,
    )