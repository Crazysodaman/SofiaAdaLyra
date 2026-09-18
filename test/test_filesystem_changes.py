from datetime import datetime, timezone
from pathlib import Path

from sofia.filesystem.changes import (
    FilesystemChangeKind,
    detect_changes,
)
from sofia.filesystem.observation import (
    FilesystemEntry,
    FilesystemObservation,
)


def entry(
    path: Path,
    content_hash: str,
    size: int = 10,
) -> FilesystemEntry:
    return FilesystemEntry(
        path=path,
        size_bytes=size,
        modified_at=datetime.now(timezone.utc),
        content_hash=content_hash,
    )


def observation(
    root: Path,
    entries: tuple[FilesystemEntry, ...],
) -> FilesystemObservation:
    return FilesystemObservation(
        root=root,
        observed_at=datetime.now(timezone.utc),
        entries=tuple(
            sorted(
                entries,
                key=lambda item: str(item.path).casefold(),
            )
        ),
    )


def test_first_observation_has_no_false_new_file_events(
    tmp_path: Path,
):
    current = observation(
        tmp_path,
        (
            entry(
                tmp_path / "one.py",
                "a" * 64,
            ),
        ),
    )

    event = detect_changes(
        previous=None,
        current=current,
    )

    assert event.baseline_available is False
    assert event.has_changes is False
    assert event.total_changes == 0


def test_new_file_is_detected(
    tmp_path: Path,
):
    path = tmp_path / "new.py"

    previous = observation(
        tmp_path,
        (),
    )

    current = observation(
        tmp_path,
        (
            entry(
                path,
                "a" * 64,
            ),
        ),
    )

    event = detect_changes(
        previous=previous,
        current=current,
    )

    assert len(event.new) == 1
    assert event.new[0].kind is FilesystemChangeKind.NEW
    assert event.new[0].path == path


def test_modified_file_is_detected_by_hash(
    tmp_path: Path,
):
    path = tmp_path / "changed.py"

    previous = observation(
        tmp_path,
        (
            entry(
                path,
                "a" * 64,
            ),
        ),
    )

    current = observation(
        tmp_path,
        (
            entry(
                path,
                "b" * 64,
            ),
        ),
    )

    event = detect_changes(
        previous=previous,
        current=current,
    )

    assert len(event.modified) == 1
    assert event.modified[0].kind is FilesystemChangeKind.MODIFIED
    assert event.modified[0].path == path


def test_removed_file_is_detected(
    tmp_path: Path,
):
    path = tmp_path / "removed.py"

    previous = observation(
        tmp_path,
        (
            entry(
                path,
                "a" * 64,
            ),
        ),
    )

    current = observation(
        tmp_path,
        (),
    )

    event = detect_changes(
        previous=previous,
        current=current,
    )

    assert len(event.removed) == 1
    assert event.removed[0].kind is FilesystemChangeKind.REMOVED
    assert event.removed[0].path == path


def test_multiple_changes_are_one_event(
    tmp_path: Path,
):
    new_path = tmp_path / "new.py"
    modified_path = tmp_path / "changed.py"
    removed_path = tmp_path / "removed.py"

    previous = observation(
        tmp_path,
        (
            entry(
                modified_path,
                "a" * 64,
            ),
            entry(
                removed_path,
                "b" * 64,
            ),
        ),
    )

    current = observation(
        tmp_path,
        (
            entry(
                new_path,
                "c" * 64,
            ),
            entry(
                modified_path,
                "d" * 64,
            ),
        ),
    )

    event = detect_changes(
        previous=previous,
        current=current,
    )

    assert event.total_changes == 3
    assert len(event.new) == 1
    assert len(event.modified) == 1
    assert len(event.removed) == 1