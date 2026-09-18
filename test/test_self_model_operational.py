from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sofia.filesystem.changes import detect_changes
from sofia.filesystem.observation import (
    FilesystemEntry,
    FilesystemObservation,
)
from sofia.operational.model import (
    ContinuityEvidenceStatus,
    OperationalState,
    RuntimeContinuity,
)
from sofia.self_model.operational import (
    SofiaOperationalSelfModel,
)


def test_operational_self_model_combines_runtime_and_workspace_evidence(
    tmp_path: Path,
):
    runtime_id = uuid4()
    started_at = datetime.now(timezone.utc)

    operational_state = OperationalState(
        runtime_id=runtime_id,
        started_at=started_at,
        lifecycle_state="READY",
        application_name="sofia-ada-lyra",
        application_version="0.1.0",
        provider="test",
        model="test-model",
    )

    continuity = RuntimeContinuity(
        evidence_status=ContinuityEvidenceStatus.UNKNOWN,
        current_runtime_id=runtime_id,
        current_started_at=started_at,
    )

    previous = FilesystemObservation(
        root=tmp_path,
        observed_at=started_at,
        entries=(),
    )

    current_entry = FilesystemEntry(
        path=tmp_path / "new.py",
        size_bytes=10,
        modified_at=started_at,
        content_hash="a" * 64,
    )

    current = FilesystemObservation(
        root=tmp_path,
        observed_at=datetime.now(timezone.utc),
        entries=(current_entry,),
    )

    changes = detect_changes(
        previous=previous,
        current=current,
    )

    model = SofiaOperationalSelfModel(
        operational_state=operational_state,
        continuity=continuity,
        workspace_changes=changes,
    )

    assert model.operational_state.runtime_id == runtime_id
    assert model.continuity.current_runtime_id == runtime_id
    assert model.workspace_changes is not None
    assert model.workspace_changes.total_changes == 1