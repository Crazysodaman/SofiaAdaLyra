"""Regression contracts for exact 700-item V18 source-to-git ledger.

Authoring only. Tests run at the end of the coding campaign by owner request.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sofia.verify.v18_roadmap import (
    LEDGER_RELATIVE, MASTER_RELATIVE, MASTER_SHA256,
    RoadmapIntegrityError, original_tasks, validate_repository,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path):
    master = tmp_path / MASTER_RELATIVE
    ledger = tmp_path / LEDGER_RELATIVE
    master.parent.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    # Materialize immutable LF-normalized Git text on both OS families.
    master.write_bytes((ROOT / MASTER_RELATIVE).read_bytes().replace(
        b"\r\n", b"\n",
    ))
    # The original 700 ledger is supplemented by independently maintained
    # ML/GA plans. Include both source inventories in isolated fixtures.
    for relative in (
        Path("docs/Sofia_V18_700_Tasks_Brief_Table.md"),
        Path("docs/roadmaps/Sofia_Generalization_Lifelong_Learning_40_Task_Addendum.md"),
    ):
        source = tmp_path / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes((ROOT / relative).read_bytes())
    contents = json.loads((ROOT / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    ledger.write_text(json.dumps(contents), encoding="utf-8")
    for item in contents["tasks"]:
        for relative in item["code_paths"]:
            source = tmp_path / relative
            if source in {master, ledger}:
                # CA-3302 cites the ledger. Don't overwrite test authority.
                continue
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("# fixture only\n", encoding="utf-8")
    return master, ledger, contents


def test_v18_original_has_exact_700_unique_ids_and_topic_groups():
    tasks = original_tasks(ROOT / MASTER_RELATIVE)
    assert len(tasks) == 700
    assert len({x[0] for x in tasks.values()}) == 17
    assert len({x[1] for x in tasks.values()}) == 69
    assert tasks["CA-001"][0] == "00"
    assert tasks["CA-812"][0] == "16"


def test_v18_repository_task_inventory_fails_closed_on_missing_task(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    assert validate_repository(tmp_path)["total_original_tasks"] == 700
    records["tasks"].pop()
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="all 700"):
        validate_repository(tmp_path)


def test_v18_accepted_claim_must_have_exact_receipt(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    claimed = records["tasks"][0]
    claimed["status"] = "accepted"
    claimed["accepted"] = True
    claimed["code_paths"] = ["src/sofia/life/coordinator.py"]
    fixture = tmp_path / "src/sofia/life/coordinator.py"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("# mocked local source\n", encoding="utf-8")
    claimed["production_wiring"] = {
        "entrypoint": "sofia.platform.application",
        "remaining": "tests_only",
        "explanation": "A synthetic trace with the fields required to reach receipt validation.",
        "source_review_sha": records["reviewed_main_sha"],
        "composition_path": claimed["code_paths"][0],
        "caller_path": claimed["code_paths"][0],
        "implementation_path": claimed["code_paths"][0],
        "effect_path": claimed["code_paths"][0],
    }
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="acceptance receipt"):
        validate_repository(tmp_path)


def test_v18_missing_source_ref_cannot_be_pretended_coded(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    task = next(r for r in records["tasks"] if r["status"] == "partial_wiring")
    task["code_paths"] = ["src/sofia/does-not-exist.py"]
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="missing or symlinked"):
        validate_repository(tmp_path)


def test_v18_original_wording_is_immutable(tmp_path):
    master, _, _ = _fixture(tmp_path)
    value = master.read_text(encoding="utf-8")
    master.write_text(value.replace("CA-001 [VERIFY]", "CA-001 [DONE]"), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="source bytes changed"):
        validate_repository(tmp_path)


def test_v18_tests_only_claim_requires_production_entrypoint_to_effect_path(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    coded = next(item for item in records["tasks"] if item["status"] == "code_present_unverified")
    assert coded["production_wiring"]["remaining"] == "tests_only"
    coded["production_wiring"].pop("caller_path")
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="caller_path"):
        validate_repository(tmp_path)


def test_v18_unreachable_test_file_cannot_masquerade_as_production_effect(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    coded = next(item for item in records["tasks"] if item["status"] == "code_present_unverified")
    coded["production_wiring"]["effect_path"] = "test/test_life_atomic_admission.py"
    coded["code_paths"].append("test/test_life_atomic_admission.py")
    source = tmp_path / "test/test_life_atomic_admission.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# fixture only\n", encoding="utf-8")
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="only at tests/docs"):
        validate_repository(tmp_path)


def test_v18_partial_source_cannot_be_relabelled_tests_only_without_wiring(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    partial = next(item for item in records["tasks"] if item["status"] == "partial_wiring")
    partial["status"] = "code_present_unverified"
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="production-wired claim"):
        validate_repository(tmp_path)


def test_v18_accepted_without_production_wiring_cannot_claim_green(tmp_path):
    _, ledger, records = _fixture(tmp_path)
    claimed = next(item for item in records["tasks"] if item["status"] == "code_present_unverified")
    claimed["status"] = "accepted"
    claimed["accepted"] = True
    claimed.pop("production_wiring")
    ledger.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="production-wired claim"):
        validate_repository(tmp_path)

def test_v18_crlf_checkout_keeps_original_git_text_binding(tmp_path):
    master, _, _ = _fixture(tmp_path)
    original = master.read_bytes()
    assert b"\r" not in original
    master.write_bytes(original.replace(b"\n", b"\r\n"))
    assert validate_repository(tmp_path)["total_original_tasks"] == 700


def test_v18_crlf_checkout_does_not_accept_changed_roadmap_content(tmp_path):
    master, _, _ = _fixture(tmp_path)
    original = master.read_bytes().replace(b"\n", b"\r\n")
    master.write_bytes(original.replace(b"CA-001", b"CA-999", 1))
    with pytest.raises(RoadmapIntegrityError, match="source bytes changed"):
        validate_repository(tmp_path)


def test_v18_additional_ml_ga_sections_do_not_change_historic_700():
    """Extension remains separate from the immutable original CA ledger."""
    master = (ROOT / MASTER_RELATIVE).read_text(encoding="utf-8")
    assert "## Machine learning addendum | ML-001" in master
    assert "Sofia_Generalization_Lifelong_Learning_40_Task_Addendum.md" in master
    original = original_tasks(ROOT / MASTER_RELATIVE)
    assert len(original) == 700
    assert original["CA-001"][0] == "00"
    assert original["CA-812"][0] == "16"


def test_v18_extension_cannot_inject_a_new_ca_checklist(tmp_path):
    master, _, _ = _fixture(tmp_path)
    with master.open("ab") as stream:
        stream.write(b"\n- [ ] **CA-999 [GAP]** rogue source claim\n")
    with pytest.raises(RoadmapIntegrityError, match="CA checklist injected"):
        validate_repository(tmp_path)


def test_v18_extension_cannot_redefine_a_priority_phase(tmp_path):
    master, _, _ = _fixture(tmp_path)
    with master.open("ab") as stream:
        stream.write(b"\n## Priority phase 00: forged section\n")
    with pytest.raises(RoadmapIntegrityError, match="CA checklist injected"):
        validate_repository(tmp_path)


def test_v18_extension_marker_removal_rejects_tampered_master(tmp_path):
    master, _, _ = _fixture(tmp_path)
    text = master.read_text(encoding="utf-8")
    assert "## Machine learning addendum | ML-001" in text
    master.write_text(text.replace(
        "## Machine learning addendum | ML-001",
        "## Unreviewed tasks | ML-001", 1,
    ), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="source bytes changed"):
        validate_repository(tmp_path)


def test_v18_expanded_planning_inventory_verified_without_acceptance():
    report = validate_repository(ROOT)
    scope = report["expanded_planning_inventory"]
    assert scope == {
        "original_tasks": 700,
        "ml_planned": 40,
        "ga_planned": 40,
        "planned_tasks": 780,
    }


def test_v18_expanded_table_missing_ga_task_fails_closed(tmp_path):
    _fixture(tmp_path)
    brief = tmp_path / "docs/Sofia_V18_700_Tasks_Brief_Table.md"
    text = brief.read_text(encoding="utf-8")
    assert "| GA-040 |" in text
    brief.write_text(text.replace("| GA-040 |", "| GA-999 |", 1), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="expanded table disagrees"):
        validate_repository(tmp_path)


def test_v18_ga_addendum_duplicates_rejected(tmp_path):
    _fixture(tmp_path)
    ga = tmp_path / "docs/roadmaps/Sofia_Generalization_Lifelong_Learning_40_Task_Addendum.md"
    text = ga.read_text(encoding="utf-8")
    assert "**GA-040 [PLANNED" in text
    ga.write_text(text.replace("**GA-040 [PLANNED", "**GA-039 [PLANNED", 1), encoding="utf-8")
    with pytest.raises(RoadmapIntegrityError, match="supplemental ML or GA"):
        validate_repository(tmp_path)


def test_v18_expansion_rejects_missing_ga_addendum(tmp_path):
    _fixture(tmp_path)
    ga = tmp_path / "docs/roadmaps/Sofia_Generalization_Lifelong_Learning_40_Task_Addendum.md"
    ga.unlink()
    with pytest.raises(RoadmapIntegrityError, match="missing or symlinked"):
        validate_repository(tmp_path)
