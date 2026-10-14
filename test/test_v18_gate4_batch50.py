"""Exact 50-task development batch: sourced requirements, no false promotion."""
import json
from pathlib import Path

import pytest

from sofia.verify.v18_roadmap import (
    LEDGER_RELATIVE, MASTER_RELATIVE, _within, RoadmapIntegrityError,
)
from sofia.verify.v18_gate4 import gate4_snapshot

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]
BATCH = Path("docs/development/v18-gate4-fifty-batch.json")
FOCUS = {"CA-2201", "CA-2204", "CA-3001", "CA-3003", "CA-103", "CA-111"}


def test_original_fifty_requirements_are_in_order_and_have_real_sources():
    packet = json.loads(_within(ROOT, BATCH.as_posix()).read_text(encoding="utf-8"))
    source = json.loads(_within(ROOT, LEDGER_RELATIVE.as_posix()).read_text(encoding="utf-8"))
    assert packet["schema"] == "sofia.v18-gate4-fifty-batch-v1"
    assert packet["goal_gate"] == 4
    assert packet["production_gates_deferred"] == [5, 6]
    assert packet["progress_is_not_acceptance"] is True
    assert packet["total"] == len(packet["tasks"]) == 50
    assert len({t["id"] for t in packet["tasks"]}) == 50
    original_lines = _within(ROOT, MASTER_RELATIVE.as_posix()).read_text(
        encoding="utf-8").splitlines()
    all_ids = {t["id"]: t for t in source["tasks"]}
    for task in packet["tasks"]:
        original = all_ids[task["id"]]
        assert task["original_requirement"] == original_lines[original["master_line"] - 1]
        assert task["phase"] == original["phase"]
        assert task["ledger_status"] == original["status"]
        assert task["production_code_paths"] == original["code_paths"]
        assert task["gate4_claim"] is False
        assert task["gate4_blocker"]
        for path in task["production_code_paths"]:
            assert _within(ROOT, path).is_file()
        for path in task["focused_test_paths"]:
            assert path.startswith("test/test_")
            assert _within(ROOT, path).is_file()
    assert {t["id"] for t in packet["tasks"] if t["focused_test_paths"]} == FOCUS


def test_one_focused_suite_is_not_full_gate4_coverage():
    packet = json.loads(_within(ROOT, BATCH.as_posix()).read_text(encoding="utf-8"))
    report = gate4_snapshot(ROOT)
    current = {t["id"]: t for t in report["tasks"]}
    assert len(packet["tasks"]) == 50
    for task in packet["tasks"]:
        assert not task["gate4_claim"]
        assert current[task["id"]]["source_status"] == task["ledger_status"]
        assert current[task["id"]]["gate4"] is False
