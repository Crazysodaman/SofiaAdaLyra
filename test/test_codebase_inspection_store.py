from datetime import datetime, timedelta, timezone
from pathlib import Path

from sofia.core.codebase import CodebaseInspectionStore, CodebaseInspector


NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def test_hashed_inspection_detects_change_and_survives_restart(
    canonical_state_path, tmp_path,
):
    root = tmp_path / "source"
    root.mkdir()
    module = root / "module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    store = CodebaseInspectionStore(canonical_state_path)

    first_evidence = CodebaseInspector(root).inspect()
    first = store.record(first_evidence, observed_at=NOW)
    assert first.added_paths == ("module.py",)
    assert first.modified_paths == ()
    assert first.capability_modules_added == ("module",)
    assert first.fresh_until == NOW + timedelta(hours=6)

    module.write_text("VALUE = 2\n", encoding="utf-8")
    second = store.record(
        CodebaseInspector(root).inspect(),
        observed_at=NOW + timedelta(minutes=1),
    )
    assert second.snapshot_digest != first.snapshot_digest
    assert second.modified_paths == ("module.py",)
    assert second.added_paths == second.removed_paths == ()
    assert CodebaseInspectionStore(canonical_state_path).latest() == second


def test_inspection_skips_redirected_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "private.py"
    outside.write_text("SECRET = True\n", encoding="utf-8")
    link = root / "redirected.py"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        return

    evidence = CodebaseInspector(root).inspect()
    assert all(item.path != link for item in evidence.files)


def test_durable_store_rejects_unhashed_or_out_of_scope_evidence(
    canonical_state_path, tmp_path,
):
    from sofia.core.codebase import (
        CodebaseEvidenceKind,
        CodebaseFile,
        CodebaseInspectionEvidence,
        SourceFileKind,
    )
    import pytest

    root = tmp_path / "source"
    root.mkdir()
    external = tmp_path / "outside.py"
    external.write_text("VALUE = 1\n", encoding="utf-8")
    store = CodebaseInspectionStore(canonical_state_path)
    evidence = CodebaseInspectionEvidence(
        root=root, files=(CodebaseFile(external, SourceFileKind.PYTHON, 10),),
        python_modules=(), relationships=(),
        evidence_kind=CodebaseEvidenceKind.OBSERVED,
    )
    with pytest.raises(ValueError, match="content hashes"):
        store.record(evidence, observed_at=NOW)

    escaped = CodebaseInspectionEvidence(
        root=root,
        files=(CodebaseFile(external, SourceFileKind.PYTHON, 10, "a" * 64),),
        python_modules=(), relationships=(),
        evidence_kind=CodebaseEvidenceKind.OBSERVED,
    )
    with pytest.raises(ValueError, match="escaped"):
        store.record(escaped, observed_at=NOW)
