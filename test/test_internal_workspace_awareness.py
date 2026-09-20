"""Internal SQLite writes are not workspace news; real changes remain visible."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from sofia.continuity.model import ContinuityEventKind, create_continuity_event
from sofia.filesystem.change_filter import exclude_internal_state_changes
from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.filesystem.observation import FilesystemEntry
from sofia.operational.model import ContinuityEvidenceStatus, RuntimeContinuity
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.runtime.runtime import SofiaRuntime

NOW = datetime(2026, 9, 20, 19, tzinfo=timezone.utc)


def _change(path, kind=FilesystemChangeKind.MODIFIED):
    previous = FilesystemEntry(path=path, size_bytes=1, modified_at=NOW, content_hash="0" * 64)
    current = FilesystemEntry(path=path, size_bytes=2, modified_at=NOW, content_hash="1" * 64)
    return FilesystemChange(kind=kind, path=path,
                            previous=previous if kind is not FilesystemChangeKind.NEW else None,
                            current=current if kind is not FilesystemChangeKind.REMOVED else None)


def _event(*, modified=(), added=(), removed=(), baseline=True):
    return FilesystemChangeEvent(
        previous_observed_at=NOW, current_observed_at=NOW,
        new=tuple(added), modified=tuple(modified), removed=tuple(removed),
        baseline_available=baseline,
    )


def _runtime(tmp_path, changes, *, restarted=True):
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED if restarted else ContinuityEvidenceStatus.UNKNOWN,
        current_runtime_id=uuid4(), current_started_at=NOW,
        previous_runtime_id=uuid4() if restarted else None,
        previous_started_at=NOW if restarted else None,
    )
    runtime = object.__new__(SofiaRuntime)
    runtime._configuration = SimpleNamespace(state_path=tmp_path / "state" / "sofia.db")
    runtime._workspace_changes = changes
    runtime._runtime_continuity = continuity
    runtime._pending_continuity_event = create_continuity_event(continuity, changes)
    return runtime


def test_all_sqlite_noise_is_removed_from_runtime_awareness_but_restart_remains(tmp_path):
    db = tmp_path / "state" / "sofia.db"
    changes = _event(modified=(_change(db), _change(Path(str(db) + "-wal"))),
                     added=(_change(Path(str(db) + "-shm"), FilesystemChangeKind.NEW),),
                     removed=(_change(Path(str(db) + "-journal"), FilesystemChangeKind.REMOVED),))
    runtime = _runtime(tmp_path, changes)
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.baseline_available
    assert not runtime.workspace_changes.has_changes
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.RUNTIME_RESUMED
    assert runtime.pending_continuity_event.workspace_change_count == 0
    assert runtime.operational_self_model is None if False else not runtime.workspace_changes.has_changes
    assert changes.total_changes == 4  # The original observation is not mutated.
    normalize_runtime_workspace_awareness(runtime)  # Idempotent.
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.RUNTIME_RESUMED


def test_mixed_changes_preserve_real_paths_and_correct_aggregate(tmp_path):
    db = tmp_path / "state" / "sofia.db"
    code = tmp_path / "src" / "sofia" / "engine.py"
    changes = _event(modified=(_change(db), _change(code)))
    runtime = _runtime(tmp_path, changes)
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.modified == (_change(code),)
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    assert runtime.pending_continuity_event.workspace_change_count == 1


def test_state_only_without_previous_runtime_creates_no_startup_alert(tmp_path):
    db = tmp_path / "state" / "sofia.db"
    runtime = _runtime(tmp_path, _event(modified=(_change(db),)), restarted=False)
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.pending_continuity_event is None


def test_unrelated_database_is_not_suppressed(tmp_path):
    own = tmp_path / "state" / "sofia.db"
    other = tmp_path / "state" / "other.db"
    changes = _event(modified=(_change(other),))
    assert exclude_internal_state_changes(changes, state_path=own) is changes


def test_invalid_path_rejected_and_unavailable_baseline_preserved(tmp_path):
    changes = _event(baseline=False)
    with pytest.raises(TypeError):
        exclude_internal_state_changes(changes, state_path="state/sofia.db")
    assert exclude_internal_state_changes(changes, state_path=tmp_path / "sofia.db") is changes
