"""Regression: valid string-configured DB paths must not break startup awareness."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sofia.continuity.model import ContinuityEventKind, create_continuity_event
from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.filesystem.observation import FilesystemEntry
from sofia.operational.model import ContinuityEvidenceStatus, RuntimeContinuity
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.runtime.runtime import SofiaRuntime


NOW = datetime(2026, 9, 20, 20, tzinfo=timezone.utc)


def _modified(path: Path) -> FilesystemChange:
    return FilesystemChange(
        kind=FilesystemChangeKind.MODIFIED,
        path=path,
        previous=FilesystemEntry(path=path, size_bytes=1, modified_at=NOW, content_hash="0" * 64),
        current=FilesystemEntry(path=path, size_bytes=2, modified_at=NOW, content_hash="1" * 64),
    )


def test_string_configured_state_path_only_filters_own_sqlite_noise(tmp_path: Path) -> None:
    db = tmp_path / "state" / "sofia.db"
    other_db = tmp_path / "state" / "other.db"
    external = _modified(other_db)
    original = FilesystemChangeEvent(
        previous_observed_at=NOW,
        current_observed_at=NOW,
        new=(),
        modified=(_modified(db), _modified(Path(str(db) + "-wal")), external),
        removed=(),
        baseline_available=True,
    )
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=uuid4(),
        current_started_at=NOW,
        previous_runtime_id=uuid4(),
        previous_started_at=NOW,
    )
    runtime = object.__new__(SofiaRuntime)
    runtime._configuration = SimpleNamespace(state_path=str(db))
    runtime._workspace_changes = original
    runtime._runtime_continuity = continuity
    runtime._pending_continuity_event = create_continuity_event(continuity, original)

    normalize_runtime_workspace_awareness(runtime)

    assert runtime.workspace_changes.modified == (external,)
    assert runtime.workspace_changes.baseline_available
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    assert runtime.pending_continuity_event.workspace_change_count == 1
    assert original.total_changes == 3  # Raw observation is preserved.

    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.modified == (external,)
    assert runtime.pending_continuity_event.workspace_change_count == 1
