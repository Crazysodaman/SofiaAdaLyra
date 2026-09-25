"""The real virtual lab database is internal state, not arbitrary workspace news."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sofia.continuity.model import ContinuityEventKind, create_continuity_event
from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.filesystem.observation import FilesystemEntry
from sofia.interaction.world_setup import lab_state_path
from sofia.operational.model import ContinuityEvidenceStatus, RuntimeContinuity
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.runtime.runtime import SofiaRuntime

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def _modified(path: Path) -> FilesystemChange:
    return FilesystemChange(
        kind=FilesystemChangeKind.MODIFIED, path=path,
        previous=FilesystemEntry(path=path, size_bytes=1, modified_at=NOW, content_hash="0" * 64),
        current=FilesystemEntry(path=path, size_bytes=2, modified_at=NOW, content_hash="1" * 64),
    )


def test_only_configured_conversation_and_lab_sqlite_noise_is_filtered(tmp_path: Path):
    state = tmp_path / "state" / "sofia.db"
    lab = lab_state_path(state)
    other = state.with_name("other-lab.db")
    true_change = _modified(tmp_path / "src" / "world.py")
    raw = FilesystemChangeEvent(
        previous_observed_at=NOW, current_observed_at=NOW,
        new=(),
        modified=(_modified(state), _modified(lab),
                  _modified(Path(str(lab) + "-wal")),
                  _modified(Path(str(lab) + "-shm")),
                  _modified(Path(str(lab) + "-journal")),
                  _modified(other), true_change),
        removed=(), baseline_available=True,
    )
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=uuid4(), current_started_at=NOW,
        previous_runtime_id=uuid4(), previous_started_at=NOW,
    )
    runtime = object.__new__(SofiaRuntime)
    runtime._configuration = SimpleNamespace(state_path=str(state))
    runtime._workspace_changes = raw
    runtime._runtime_continuity = continuity
    runtime._pending_continuity_event = create_continuity_event(continuity, raw)
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.modified == (_modified(other), true_change)
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
    assert runtime.pending_continuity_event.workspace_change_count == 2
    assert raw.total_changes == 7
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.modified == (_modified(other), true_change)


def test_just_lab_database_does_not_generate_workspace_news(tmp_path: Path):
    lab = lab_state_path(tmp_path / "sofia.db")
    raw = FilesystemChangeEvent(
        previous_observed_at=NOW, current_observed_at=NOW,
        new=(), modified=(_modified(lab),), removed=(), baseline_available=True,
    )
    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.OBSERVED,
        current_runtime_id=uuid4(), current_started_at=NOW,
        previous_runtime_id=uuid4(), previous_started_at=NOW,
    )
    runtime = object.__new__(SofiaRuntime)
    runtime._configuration = SimpleNamespace(state_path=tmp_path / "sofia.db")
    runtime._workspace_changes = raw
    runtime._runtime_continuity = continuity
    runtime._pending_continuity_event = create_continuity_event(continuity, raw)
    normalize_runtime_workspace_awareness(runtime)
    assert runtime.workspace_changes.baseline_available
    assert not runtime.workspace_changes.has_changes
    assert runtime.pending_continuity_event.kind is ContinuityEventKind.RUNTIME_RESUMED
