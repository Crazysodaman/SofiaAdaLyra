"""Small-first queue is explicit, dependency-safe and never awards gates."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sofia.verify.v18_work_queue import (
    REVIEW_RELATIVE, build_work_queue,
)
from sofia.verify.v18_gate4 import gate4_snapshot
from sofia.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    return (
        gate4_snapshot(ROOT),
        json.loads((ROOT / REVIEW_RELATIVE).read_text(encoding="utf-8")),
    )


def test_queue_covers_all_780_without_implicit_independence():
    progress, reviews = _inputs()
    report = build_work_queue(
        progress, reviews, reserved=("CA-003", "CA-004", "CA-005", "CA-006"),
    )
    assert len(report["tasks"]) == report["total"] == 780
    assert sum(report["states"].values()) == 780
    assert report["reviewed_dependencies"] == len(reviews["tasks"])
    assert all(item["complexity"] == "small" for item in report["selected"])
    # A queue full of unreviewed Gate 4 claims must not invent five
    # implementation-ready tasks merely to keep the pipeline busy.
    assert len(report["selected"]) <= 5
    assert len(report["selected_independent_review"]) <= 5
    assert len(report["selected"]) + len(report["selected_independent_review"]) > 0
    assert not any(item["id"] in {"CA-003", "CA-004", "CA-005", "CA-006"}
                   for item in report["selected"] + report["selected_independent_review"])
    assert next(row for row in report["tasks"] if row["id"] == "CA-4503")[
        "state"
    ] == "blocked_on_prerequisite"
    assert next(row for row in report["tasks"] if row["id"] == "ML-001")[
        "state"
    ] == "dependency_review_required"
    assert report["gate4_recorded"] == progress["overall_gate4_recorded"]


def test_dependency_is_not_satisfied_by_gate_two_or_source_status():
    progress, reviews = _inputs()
    changed = deepcopy(progress)
    task = next(row for row in changed["tasks"] if row["id"] == "CA-4501")
    task["gate_with_recorded_proof"] = 2
    result = build_work_queue(changed, reviews)
    dependent = next(row for row in result["tasks"] if row["id"] == "CA-4503")
    assert dependent["state"] == "blocked_on_prerequisite"
    assert dependent["blocked_by"] == ["CA-4501", "CA-5401"]


def test_audited_prerequisites_unlock_dependent_at_gate_three():
    progress, reviews = _inputs()
    changed = deepcopy(progress)
    for key in ("CA-4501", "CA-5401"):
        row = next(row for row in changed["tasks"] if row["id"] == key)
        row["gate_with_recorded_proof"] = 3
    report = build_work_queue(changed, reviews)
    dependent = next(row for row in report["tasks"] if row["id"] == "CA-4503")
    # Dependencies are cleared, but the dependent's own recorded
    # Gate 4 still awaits independently reviewed acceptance.
    assert dependent["state"] == "review_pending"
    assert dependent["blocked_by"] == []


def test_cycle_unknown_dependency_and_false_independence_rejected():
    progress, reviews = _inputs()
    changed = deepcopy(reviews)
    changed["tasks"]["CA-4501"]["depends_on"] = ["CA-4503"]
    with pytest.raises(RoadmapIntegrityError, match="cycle"):
        build_work_queue(progress, changed)
    changed = deepcopy(reviews)
    changed["tasks"]["CA-4501"]["depends_on"] = ["CA-999999"]
    with pytest.raises(RoadmapIntegrityError, match="dependencies"):
        build_work_queue(progress, changed)
    changed = deepcopy(reviews)
    changed["tasks"]["CA-4501"].pop("depends_on")
    with pytest.raises(RoadmapIntegrityError, match="dependencies"):
        build_work_queue(progress, changed)


def test_reservations_and_bad_gate_values_fail_closed():
    progress, reviews = _inputs()
    with pytest.raises(RoadmapIntegrityError, match="reservation"):
        build_work_queue(progress, reviews, reserved=("CA-999999",))
    with pytest.raises(RoadmapIntegrityError, match="limit"):
        build_work_queue(progress, reviews, limit=True)
    changed = deepcopy(progress)
    changed["tasks"][0]["gate_with_recorded_proof"] = True
    with pytest.raises(RoadmapIntegrityError, match="canonical task"):
        build_work_queue(changed, reviews)


def test_queue_does_not_modify_gate_evidence():
    progress, reviews = _inputs()
    before = json.dumps(progress, sort_keys=True)
    build_work_queue(progress, reviews)
    assert json.dumps(progress, sort_keys=True) == before


def test_gate_three_tasks_are_deferred_until_final_ci():
    progress, reviews = _inputs()
    # Synthetic before/after gate advancement independent of mutable
    # historical ledger proof counts.
    changed = deepcopy(progress)
    target = next(row for row in changed["tasks"] if row["id"] == "CA-4501")
    target["gate_with_recorded_proof"] = 0
    baseline = build_work_queue(changed, reviews)
    target["gate_with_recorded_proof"] = 3
    report = build_work_queue(changed, reviews)
    assert report["states"]["awaiting_final_ci"] == baseline["states"]["awaiting_final_ci"] + 1
    assert next(row for row in report["tasks"] if row["id"] == "CA-4501")["state"] == "awaiting_final_ci"
    assert all(row["gate"] < 3 for row in report["selected"])


def test_codex_reservations_apply_without_caller_flags():
    progress, reviews = _inputs()
    report = build_work_queue(progress, reviews)
    for key in ("CA-003", "CA-004", "CA-005", "CA-006"):
        assert next(row for row in report["tasks"] if row["id"] == key)["state"] == "reserved"


def test_malformed_input_types_are_rejected_cleanly():
    progress, reviews = _inputs()
    changed = deepcopy(progress)
    changed["tasks"] = {}
    with pytest.raises(RoadmapIntegrityError, match="780 canonical"):
        build_work_queue(changed, reviews)
    changed = deepcopy(reviews)
    changed["tasks"]["CA-4501"]["depends_on"] = [{}]
    with pytest.raises(RoadmapIntegrityError, match="invalid dependencies"):
        build_work_queue(progress, changed)


def test_pending_review_cannot_be_dependency_satisfaction_or_completion():
    progress, reviews = _inputs()
    changed = deepcopy(progress)
    predecessor = next(row for row in changed["tasks"] if row["id"] == "CA-4501")
    successor = next(row for row in changed["tasks"] if row["id"] == "CA-4503")
    predecessor["gate_with_recorded_proof"] = 4
    predecessor["independent_review_pending"] = True
    successor["gate_with_recorded_proof"] = 4
    successor["independent_review_pending"] = True
    report = build_work_queue(changed, reviews)
    outcome = {row["id"]: row for row in report["tasks"]}
    assert outcome["CA-4501"]["state"] != "complete"
    assert "CA-4501" in outcome["CA-4503"]["blocked_by"]
    assert outcome["CA-4503"]["state"] == "blocked_on_prerequisite"
    assert report["gate4_recorded"] == progress["overall_gate4_recorded"]


def test_pending_review_work_has_its_own_noncompletion_queue():
    progress, reviews = _inputs()
    report = build_work_queue(progress, reviews)
    reviewed = report["selected_independent_review"]
    assert all(item["state"] == "review_pending" for item in reviewed)
    assert all(item["state"] != "complete" for item in reviewed)
    assert report["gate4_recorded"] == progress["overall_gate4_recorded"]
    if report["states"]["review_pending"]:
        assert reviewed
