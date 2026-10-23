"""Thirty original V18 Phase 00 tasks: source proof, non-acceptance and tamper tests."""
from copy import deepcopy
from hashlib import file_digest
import json
from pathlib import Path

import pytest

from sofia.platform.verify.v18_phase00_audit import (
    BATCH_RELATIVE, SCHEMA, audit_phase00_batch,
)
from sofia.platform.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def _manifest():
    return json.loads((ROOT / BATCH_RELATIVE).read_text(encoding="utf-8"))


def test_first_thirty_task_ids_are_ordered_and_all_source_markers_really_exist():
    report = audit_phase00_batch(ROOT)
    assert report["task_count"] == 30
    assert report["source_markers_verified"] == 30
    assert report["related_test_files_verified"] == 30
    assert not report["tests_executed_by_this_command"]
    assert not report["production_accepted_by_this_command"]
    assert not report["live_verification_performed"]
    assert all(not row["production_accepted"] for row in report["tasks"])
    assert len({row["id"] for row in report["tasks"]}) == 30
    assert report["tasks"][0]["id"] == "CA-001"
    assert report["tasks"][-1]["id"] == "CA-3303"


@pytest.mark.parametrize(("field", "replacement"), [
    ("accepted", True),
    ("verification_result", "CI_passed"),
    ("live_result", "production_accepted"),
    ("review_status", "accepted"),
    ("source", "src/sofia/not_a_real_owner.py"),
    ("source_anchor", "invented_no_such_function_signature"),
    ("related_test", "test/missing_v18_test.py"),
    ("missing_evidence", ""),
    ("rejection_rule", "none"),
    ("resource_overhead", "unknown"),
    ("design_choices", ["one option"]),
])
def test_audit_rejects_fabricated_evidence_and_nonactionable_design(
    field, replacement,
):
    manifest = _manifest()
    manifest["tasks"][0][field] = replacement
    with pytest.raises(RoadmapIntegrityError):
        audit_phase00_batch(ROOT, manifest=manifest)


def test_audit_rejects_task_reorder_and_duplicate_without_overwriting_ledger():
    manifest = _manifest()
    manifest["tasks"][1] = deepcopy(manifest["tasks"][0])
    with pytest.raises(RoadmapIntegrityError, match="ID/order"):
        audit_phase00_batch(ROOT, manifest=manifest)


def test_audit_rejects_unrelated_git_revision_before_inspection():
    with pytest.raises(RoadmapIntegrityError, match="does not match"):
        audit_phase00_batch(ROOT, expected_revision="0" * 40)


def _canonical_sqlite_file_snapshot():
    """Check for audit-side mutations even if earlier tests created state."""
    snapshot = {}
    for suffix in ("", "-wal", "-shm"):
        path = ROOT / f"sofia.db{suffix}"
        if not path.exists():
            snapshot[path.name] = None
            continue
        with path.open("rb") as stream:
            snapshot[path.name] = file_digest(stream, "sha256").hexdigest()
    return snapshot


def test_audit_does_not_change_canonical_ledger_or_bootstrap_state():
    original = (ROOT / "docs/development/v18-task-evidence.json").read_bytes()
    state_before = _canonical_sqlite_file_snapshot()
    audit_phase00_batch(ROOT)
    assert (ROOT / "docs/development/v18-task-evidence.json").read_bytes() == original
    assert _canonical_sqlite_file_snapshot() == state_before


def test_act_graph_contract_requires_real_turn_neuro_key_guard_not_literal_false():
    code = (ROOT / "src/sofia/platform/application/decision_trace.py").read_text(
        encoding="utf-8",
    )
    service = (ROOT / "src/sofia/platform/application/conversation_service.py").read_text(
        encoding="utf-8",
    )
    assert "neuro_turn_correlated=neuro_turn_snapshot is not None" in code
    assert "self._current_neuro_message_id != message_id" in service
    assert "self._current_matrix_message_id != message_id" in service
    contract = (ROOT / "docs/development/companion-autonomy-contract.md").read_text(
        encoding="utf-8",
    )
    assert "`neuro_turn_correlated=False`" not in contract
    assert "exact current-message NEURO observation" in contract
    assert "does not prove NEURO caused the reply" in contract


def test_catalog_has_no_duplicate_or_misclassified_test_marker():
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        item.split(":", 1)[0].strip()
        for item in config["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert "pkg_core" in declared
    test = (ROOT / "test/test_ws4_model_admission_positive_metrics.py").read_text(
        encoding="utf-8",
    )
    assert "pytestmark = pytest.mark.pkg_core" in test
    assert "pytest.mark.pkg_cognition" not in test
