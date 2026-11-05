"""Original CA-700 evidence cannot accidentally become hybrid GO LIVE acceptance."""
from __future__ import annotations

import csv

import pytest

from tools.hybrid_700_reconciliation import SOURCE, reconcile


def test_all_700_owner_assignments_are_preserved_without_acceptance():
    projection = reconcile()
    assert projection["count"] == 700
    assert projection["source_anchors_missing"] == 396
    assert projection["supplemental_ml_tasks"] == 40
    assert projection["supplemental_ga_tasks"] == 40
    assert projection["acceptance_state"] == "NOT_PROVEN_BY_SOURCE_CROSSWALK"
    assert {row["task_id"] for row in projection["tasks"]} == {
        f"CA-{number:03d}" for number in range(1, 701)
    }
    assert all(
        row["accepted"] is False
        and row["owner_acceptance_verified"] is False
        and row["go_live_gate"] is None
        and row["rust_gate"] is None
        and row["review_status"] == "UNMAPPED_REQUIRES_INDEPENDENT_REVIEW"
        for row in projection["tasks"]
    )
    assert sum(projection["original_coding_status_counts"].values()) == 700


def _mutate_source(tmp_path, modify):
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    assert fields
    modify(rows)
    destination = tmp_path / "untrusted-crosswalk.csv"
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return destination


def test_duplicate_ca_identity_fails_closed(tmp_path):
    source = _mutate_source(
        tmp_path, lambda rows: rows[-1].update(task_id=rows[0]["task_id"])
    )
    with pytest.raises(ValueError, match="duplicate"):
        reconcile(source)


def test_missing_ca_task_fails_closed(tmp_path):
    source = _mutate_source(tmp_path, lambda rows: rows.pop())
    with pytest.raises(ValueError, match="inventory mismatch"):
        reconcile(source)


def test_missing_owner_fails_closed(tmp_path):
    source = _mutate_source(
        tmp_path, lambda rows: rows[0].update(primary_owner="")
    )
    with pytest.raises(ValueError, match="incomplete"):
        reconcile(source)


def test_missing_source_anchor_remains_unknown_not_missing_task(tmp_path):
    source = _mutate_source(
        tmp_path, lambda rows: rows[0].update(source_anchor="")
    )
    result = reconcile(source)
    assert result["count"] == 700
    assert result["tasks"][0]["source_anchor_present"] is False
    assert result["tasks"][0]["accepted"] is False
