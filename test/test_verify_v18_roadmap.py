"""Regression contracts for exact 700-item V18 source-to-git ledger.

Authoring only. Tests run at the end of the coding campaign by owner request.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

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
    shutil.copy2(ROOT / MASTER_RELATIVE, master)
    contents = json.loads((ROOT / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    ledger.write_text(json.dumps(contents), encoding="utf-8")
    for item in contents["tasks"]:
        for relative in item["code_paths"]:
            source = tmp_path / relative
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
