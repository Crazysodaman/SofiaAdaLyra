"""The next fifty original V18 task reviews cannot fake execution or acceptance."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sofia.platform.verify.v18_next50_audit import BATCH_RELATIVE, audit_next50
from sofia.platform.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def _manifest():
    return json.loads((ROOT / BATCH_RELATIVE).read_text(encoding="utf-8"))


def test_exact_original_fifty_present_without_promotion():
    report = audit_next50(ROOT)
    assert report["reviewed_task_count"] == 50
    assert report["source_files_found"] == 50
    assert report["review_documents_bound"] == 50
    assert report["production_accepted_task_count"] == 0
    assert not report["tests_executed_by_this_command"]
    assert not report["live_host_verified"]
    ids = [t["id"] for t in report["tasks"]]
    assert len(set(ids)) == 50
    assert ids[0] == "CA-3304"
    assert ids[-1] == "CA-2201"
    assert all(not t["production_accepted"] for t in report["tasks"])


@pytest.mark.parametrize(("field", "changed"), [
    ("accepted", True),
    ("review_state", "complete"),
    ("manifest_claims_tests_executed", True),
    ("manifest_claims_host_verified", True),
    ("source", "src/sofia/does_not_exist.py"),
    ("review_document", "docs/development/does_not_exist.md"),
    ("acceptance_blocker", ""),
    ("original_status", "accepted"),
    ("phase", "99"),
])
def test_rejects_false_claims_missing_sources_and_status_forgery(field, changed):
    original = _manifest()
    source = deepcopy(original)
    source["tasks"][0][field] = changed
    with pytest.raises(RoadmapIntegrityError):
        audit_next50(ROOT, manifest=source)


def test_rejects_duplicate_reordered_tasks():
    source = _manifest()
    source["tasks"][1] = deepcopy(source["tasks"][0])
    with pytest.raises(RoadmapIntegrityError, match="ID/order/status"):
        audit_next50(ROOT, manifest=source)


def test_rejects_bad_checkout_revision():
    with pytest.raises(RoadmapIntegrityError, match="does not match"):
        audit_next50(ROOT, expected_revision="0" * 40)


def test_review_does_not_write_canonical_task_ledger():
    path = ROOT / "docs/development/v18-task-evidence.json"
    before = path.read_bytes()
    audit_next50(ROOT)
    assert path.read_bytes() == before



def test_historical_review_status_can_advance_without_faking_acceptance():
    # CA-910 was unassessed when the review was recorded.
    original = _manifest()
    item = next(row for row in original["tasks"] if row["id"] == "CA-910")
    assert item["original_status"] == "unassessed"
    report = audit_next50(ROOT)
    current = next(row for row in report["tasks"] if row["id"] == "CA-910")
    assert current["ledger_status"] == "partial_wiring"
    assert current["production_accepted"] is False
