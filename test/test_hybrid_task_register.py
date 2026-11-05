"""Hybrid register must not silently turn source anchors into release acceptance."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from tools.hybrid_task_register import (
    EXPECTED_HISTORICAL_COUNTS,
    EXPECTED_LAYER_COUNTS,
    SOURCE,
    build_register,
)


def test_all_700_tasks_have_unique_ids_and_no_fabricated_acceptance():
    registry = build_register()
    tasks = registry["tasks"]
    assert registry["original_task_count"] == 700
    assert len({task["task_id"] for task in tasks}) == 700
    assert registry["historical_status_counts"] == EXPECTED_HISTORICAL_COUNTS
    assert registry["owner_counts"] == EXPECTED_LAYER_COUNTS
    assert all(task["acceptance"] == "NOT_VERIFIED" for task in tasks)
    assert all(task["implementation_sha"] is None for task in tasks)
    assert all(task["go_live_gate"] == "NOT_YET_MAPPED" for task in tasks)
    assert registry["supplements_reconciled_here"] is False
    assert registry["supplemental_ml_ga_task_count"] == 80


def test_core_ownership_never_becomes_rust_cognitive_writer():
    registry = build_register()
    tasks = registry["tasks"]
    assert all(
        task["proposed_hybrid_destination"] == "PYTHON_CORE"
        for task in tasks if task["primary_layer"] == "CORE"
    )
    assert all(
        task["proposed_hybrid_destination"] == "RUST_PLATFORM_CANDIDATE"
        for task in tasks if task["primary_layer"] == "PLATFORM"
    )


def test_modified_or_dropped_crosswalk_fails_closed(tmp_path: Path):
    source = SOURCE.read_text(encoding="utf-8")
    path = tmp_path / "tampered.csv"
    path.write_text(source.replace("CA-001", "CA-002", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate task ID"):
        build_register(path)
    path.write_text("\n".join(source.splitlines()[:-2]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly 700"):
        build_register(path)
