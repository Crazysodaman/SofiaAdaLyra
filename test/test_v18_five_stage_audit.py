"""Contract regressions for the conservative five-stage V18 inventory."""
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.pkg_verify

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v18_five_stage_audit.py"
spec = importlib.util.spec_from_file_location("v18_five_stage_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40


def fixture_repo(tmp_path):
    doc = tmp_path / "docs" / "development" / "v18-full-780-task-design-code-gate-status-2026-10-17.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    ids = [f"CA-{i}" for i in range(1, 691)] + [f"CA-{i}" for i in range(3101, 3111)]
    ids += [f"ML-{i:03d}" for i in range(1, 41)]
    ids += [f"GA-{i:03d}" for i in range(1, 41)]
    doc.write_text("\n".join(f"| {i} | P0 | Build | unassessed | Open | Open | Open | Open | Original objective for {i} | remaining |" for i in ids), encoding="utf-8")
    return doc


def test_all_780_inventory_only_without_evidence(tmp_path):
    fixture_repo(tmp_path)
    result = module.build(tmp_path, SHA)
    assert len(result["tasks"]) == 780
    assert result["counts"]["NOT_WORKED_ON"] == 780
    assert result["counts"]["TESTED_CI"] == 0
    assert result["audited_targeted"] == 0
    assert result["tasks"][0]["original_requirement"].startswith("Original objective")
    assert result["tasks"][0]["task_type"] == "Build"


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


def test_sparse_audited_evidence_promotes_only_exact_task(tmp_path):
    import json

    fixture_repo(tmp_path)
    source = tmp_path / "src" / "sofia" / "life" / "coordinator.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# reviewed production source\n", encoding="utf-8")
    evidence = tmp_path / module.EVIDENCE_FILE
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({
        "schema_version": 1,
        "tasks": [{
            "task_id": "CA-103",
            "stage": "TESTED",
            "source_sha": SHA,
            "source_paths": ["src/sofia/life/coordinator.py"],
            "production_entrypoint": "application background LIFE tick",
            "tests": [{"command": "pytest focused", "result": "1 passed"}],
            "ci_runs": [],
            "open_clauses": ["exact-revision CI not yet observed"],
            "last_audited_at": "2026-10-17T00:00:00+00:00",
        }],
    }), encoding="utf-8")
    result = module.build(tmp_path, SHA)
    promoted = next(x for x in result["tasks"] if x["task_id"] == "CA-103")
    assert promoted["stage"] == "TESTED"
    assert promoted["source_sha"] == SHA
    assert promoted["audit_depth"] == "task_clause_and_production_path_audit"
    assert result["counts"]["TESTED"] == 1
    assert result["counts"]["NOT_WORKED_ON"] == 779


def test_duplicate_or_missing_original_ids_refused(tmp_path):
    doc = fixture_repo(tmp_path)
    with doc.open("a", encoding="utf-8") as stream:
        stream.write("\n| CA-1 | P0 | Build | unassessed | Open | Open | Open | Open | Another objective | remaining |\n")
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


def test_blank_original_requirement_refused(tmp_path):
    doc = fixture_repo(tmp_path)
    contents = doc.read_text(encoding="utf-8")
    doc.write_text(contents.replace("Original objective for CA-1", ""), encoding="utf-8")
    with pytest.raises(ValueError, match="missing original requirement"):
        module.build(tmp_path, SHA)


def test_phase_labels_are_scoped_to_original_addenda(tmp_path):
    doc = fixture_repo(tmp_path)
    original = doc.read_text(encoding="utf-8")
    original = original.replace("| CA-1 |", "### Phase 00 | Architecture and source ownership\n| CA-1 |", 1)
    original = original.replace("| ML-001 |", "### Machine Learning addendum: ML-001 through ML-040\n| ML-001 |", 1)
    original = original.replace("| GA-001 |", "### Generalization / lifelong-learning addendum: GA-001 through GA-040\n| GA-001 |", 1)
    doc.write_text(original, encoding="utf-8")
    result = module.build(tmp_path, SHA)
    by_id = {row["task_id"]: row for row in result["tasks"]}
    assert by_id["CA-1"]["phase"].startswith("Phase 00")
    assert by_id["ML-001"]["phase"].startswith("Machine Learning addendum")
    assert by_id["GA-001"]["phase"].startswith("Generalization / lifelong-learning addendum")


def test_markdown_progress_bars_match_machine_counts(tmp_path, monkeypatch):
    fixture_repo(tmp_path)
    report_file = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", [
        "v18_five_stage_audit", "--repo", str(tmp_path), "--sha", SHA,
        "--output", str(report_file), "--markdown-output", str(markdown),
    ])
    module.main()
    import json
    report = json.loads(report_file.read_text(encoding="utf-8"))
    summary = markdown.read_text(encoding="utf-8")
    assert report["counts"]["NOT_WORKED_ON"] == 780
    assert report["audit_coverage_percent"] == 0
    assert "780/780" in summary
    assert "0/780" in summary
    assert "Targeted evidence traced: **0/780**" in summary
    assert SHA in summary


def test_verify_head_rejects_wrong_commit_before_report(tmp_path, monkeypatch):
    import subprocess
    fixture_repo(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit",
                    "--allow-empty", "-m", "fixture", "-q"], check=True)
    actual = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual != SHA
    report_path = tmp_path / "must-not-exist.json"
    monkeypatch.setattr("sys.argv", [
        "v18_five_stage_audit", "--repo", str(tmp_path), "--sha", SHA,
        "--verify-head", "--output", str(report_path),
    ])
    with pytest.raises(ValueError, match="differs from actual"):
        module.main()
    assert not report_path.exists()
