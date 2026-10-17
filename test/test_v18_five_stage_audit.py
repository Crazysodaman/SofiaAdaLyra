"""Contract regressions for the conservative five-stage V18 inventory."""
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v18_five_stage_audit.py"
spec = importlib.util.spec_from_file_location("v18_five_stage_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40


def fixture_repo(tmp_path):
    doc = tmp_path / "docs" / "development" / "v18-full-780-task-design-code-gate-status-2026-10-17.md"
    doc.parent.mkdir(parents=True)
    ids = [f"CA-{i}" for i in range(1, 701)]
    ids += [f"ML-{i:03d}" for i in range(1, 41)]
    ids += [f"GA-{i:03d}" for i in range(1, 41)]
    doc.write_text("\n".join(f"| {i} | original scope |" for i in ids), encoding="utf-8")
    return doc


def test_all_780_inventory_only_without_evidence(tmp_path):
    fixture_repo(tmp_path)
    result = module.build(tmp_path, SHA)
    assert len(result["tasks"]) == 780
    assert result["counts"]["NOT_WORKED_ON"] == 780
    assert result["counts"]["TESTED_CI"] == 0
    assert result["audited_targeted"] == 0


def test_all_required_evidence_paths_needed_for_partial_status(tmp_path):
    fixture_repo(tmp_path)
    paths = module.TRACED["CA-3101"]
    for path in paths[:1]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("draft", encoding="utf-8")
    report = module.build(tmp_path, SHA)
    item = next(t for t in report["tasks"] if t["task_id"] == "CA-3101")
    assert item["stage"] == "NOT_WORKED_ON"
    assert item["expected_source_paths"] == paths
    for path in paths[1:]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("draft", encoding="utf-8")
    report = module.build(tmp_path, SHA)
    item = next(t for t in report["tasks"] if t["task_id"] == "CA-3101")
    assert item["stage"] == "CODED_UNFINISHED"
    assert report["counts"]["TESTED"] == 0


def test_duplicate_or_missing_original_ids_refused(tmp_path):
    doc = fixture_repo(tmp_path)
    with doc.open("a", encoding="utf-8") as stream:
        stream.write("\n| CA-1 | duplicate |\n")
    with pytest.raises(ValueError, match="780 unique"):
        module.build(tmp_path, SHA)
    fixture_repo(tmp_path)
    doc.write_text(doc.read_text().replace("| GA-040 |", "| GA-041 |"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing ML/GA"):
        module.build(tmp_path, SHA)


def test_refuse_non_exact_revision(tmp_path):
    fixture_repo(tmp_path)
    with pytest.raises(ValueError, match="source_sha"):
        module.build(tmp_path, "main")
