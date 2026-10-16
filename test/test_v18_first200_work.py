"""Strict first-200 order and independently certified acceptance only."""
from copy import deepcopy
from pathlib import Path

import pytest

from sofia.verify.v18_gate4 import gate4_snapshot
from sofia.verify.v18_first200_work import (
    FIRST, LAST, PHASES, ordered_first200,
)
from sofia.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def test_priority_batch_matches_exact_canonical_requirements():
    progress = gate4_snapshot(ROOT)
    report = ordered_first200(progress)
    rows = report["task_rows"]
    assert len(rows) == 200
    assert rows[0]["id"] == FIRST
    assert rows[-1]["id"] == LAST
    assert [r["position"] for r in rows] == list(range(1, 201))
    assert [r["id"] for r in rows] == [
        item["id"] for item in progress["tasks"][:200]
    ]
    assert report["phase_counts"] == PHASES
    assert report["verified_gate4"] == sum(r["gate4_verified"] for r in rows)
    assert report["remaining_unverified"] + report["verified_gate4"] == 200
    assert all(row["requirement"] for row in rows)


def test_unverified_historical_packets_cannot_skip_first_task():
    report = ordered_first200(gate4_snapshot(ROOT))
    assert report["first_unverified"] == FIRST
    assert report["next_ten_unverified"][0] == FIRST
    assert all(not row["gate4_verified"] for row in report["task_rows"])
    assert report["verified_gate4"] == 0


def test_invalid_order_and_invented_acceptance_are_never_auto_corrected():
    data = gate4_snapshot(ROOT)
    swapped = deepcopy(data)
    swapped["tasks"][0], swapped["tasks"][1] = (
        swapped["tasks"][1], swapped["tasks"][0]
    )
    with pytest.raises(RoadmapIntegrityError, match="order"):
        ordered_first200(swapped)
    shifted = deepcopy(data)
    shifted["tasks"][199]["phase"] = "04"
    with pytest.raises(RoadmapIntegrityError, match="phase"):
        ordered_first200(shifted)
    claimed = deepcopy(data)
    claimed["tasks"][0]["gate4"] = "passed"
    with pytest.raises(RoadmapIntegrityError, match="ungrounded"):
        ordered_first200(claimed)


def test_verified_completion_advances_first_unfinished_in_order():
    synthetic = deepcopy(gate4_snapshot(ROOT))
    synthetic["tasks"][0]["gate4"] = True
    report = ordered_first200(synthetic)
    assert report["verified_gate4"] == 1
    assert report["first_unverified"] == synthetic["tasks"][1]["id"]
    assert report["remaining_unverified"] == 199
    # This is a pure function test, not a signed acceptance receipt.
    assert gate4_snapshot(ROOT)["tasks"][0]["gate4"] is False
