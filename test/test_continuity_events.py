from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sofia.continuity.model import (
    ContinuityEventKind,
    create_continuity_event,
)
from sofia.filesystem.changes import detect_changes
from sofia.filesystem.observation import (
    FilesystemEntry,
    FilesystemObservation,
)
from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)


def observation(
    root: Path,
    entries: tuple[FilesystemEntry, ...],
    observed_at: datetime,
) -> FilesystemObservation:
    return FilesystemObservation(
        root=root,
        observed_at=observed_at,
        entries=tuple(
            sorted(
                entries,
                key=lambda item: str(item.path).casefold(),
            )
        ),
    )


def entry(
    path: Path,
    content_hash: str,
    modified_at: datetime,
) -> FilesystemEntry:
    return FilesystemEntry(
        path=path,
        size_bytes=10,
        modified_at=modified_at,
        content_hash=content_hash,
    )


def runtime_continuity(
    previous: bool,
) -> RuntimeContinuity:
    current_id = uuid4()
    current_started_at = datetime.now(timezone.utc)

    if not previous:
        return RuntimeContinuity(
            evidence_status=ContinuityEvidenceStatus.UNKNOWN,
            current_runtime_id=current_id,
            current_started_at=current_started_at,
        )

    previous_id = uuid4()
    previous_started_at = (
        current_started_at - timedelta(seconds=10)
    )
    previous_stopped_at = (
        current_started_at - timedelta(seconds=5)
    )

    return RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=current_id,
        current_started_at=current_started_at,
        previous_runtime_id=previous_id,
        previous_started_at=previous_started_at,
        previous_stopped_at=previous_stopped_at,
        previous_lifecycle_state="stopped",
    )


def test_initial_runtime_event_is_classified():
    event = create_continuity_event(
        runtime_continuity=runtime_continuity(
            previous=False
        ),
    )

    assert event.kind is ContinuityEventKind.INITIAL_RUNTIME
    assert event.restart_observed is None
    assert event.workspace_change_count == 0


def test_restart_is_classified_as_runtime_resumed():
    event = create_continuity_event(
        runtime_continuity=runtime_continuity(
            previous=True
        ),
    )

    assert event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert event.restart_observed is True


def test_restart_and_workspace_changes_are_one_event(
    tmp_path: Path,
):
    now = datetime.now(timezone.utc)

    changed_path = tmp_path / "changed.py"

    previous = observation(
        root=tmp_path,
        entries=(
            entry(
                changed_path,
                "a" * 64,
                now,
            ),
        ),
        observed_at=now,
    )

    current = observation(
        root=tmp_path,
        entries=(
            entry(
                changed_path,
                "b" * 64,
                now + timedelta(seconds=1),
            ),
        ),
        observed_at=now + timedelta(seconds=1),
    )

    changes = detect_changes(
        previous=previous,
        current=current,
    )

    event = create_continuity_event(
        runtime_continuity=runtime_continuity(
            previous=True
        ),
        workspace_changes=changes,
    )

    assert (
        event.kind
        is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    )
    assert event.workspace_change_count == 1
    assert event.has_workspace_changes is True


def test_workspace_changes_without_restart_are_one_event(
    tmp_path: Path,
):
    now = datetime.now(timezone.utc)

    new_path = tmp_path / "new.py"

    previous = observation(
        root=tmp_path,
        entries=(),
        observed_at=now,
    )

    current = observation(
        root=tmp_path,
        entries=(
            entry(
                new_path,
                "a" * 64,
                now + timedelta(seconds=1),
            ),
        ),
        observed_at=now + timedelta(seconds=1),
    )

    changes = detect_changes(
        previous=previous,
        current=current,
    )

    event = create_continuity_event(
        runtime_continuity=runtime_continuity(
            previous=False
        ),
        workspace_changes=changes,
    )

    assert event.kind is ContinuityEventKind.WORKSPACE_CHANGED
    assert event.workspace_change_count == 1


def test_continuity_event_is_immutable():
    event = create_continuity_event(
        runtime_continuity=runtime_continuity(
            previous=True
        ),
    )

    try:
        event.kind = ContinuityEventKind.UNKNOWN
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "ContinuityEvent must be immutable."
        )