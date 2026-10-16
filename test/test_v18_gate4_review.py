"""Gate 4 proof bookkeeping must not masquerade as acceptance."""
from __future__ import annotations

import json

import pytest

from sofia.verify.v18_gate4_review import main, review_readiness, review_report

pytestmark = pytest.mark.pkg_verify


def proof(reviewer: str) -> dict:
    return {"reviewer": reviewer}


def task(task_id: str, reviewer: str, *, gate4: bool = True) -> dict:
    return {
        "id": task_id,
        "phase": "00",
        "gate4_proofs": [proof(reviewer) for _ in range(4 if gate4 else 0)],
    }


def ledger_with(*items: dict) -> dict:
    filler = [task(f"CA-TEMP-{i:03}", "", gate4=False) for i in range(700 - len(items))]
    return {"tasks": list(items) + filler}


def test_pending_review_never_becomes_certified_just_because_ci_passes():
    item = task("CA-001", "OpenCode source audit (independent human review pending)")
    result = review_readiness(item)
    assert result["recorded_gate4"] is True
    assert result["review_readiness"] == "independent_review_pending"
    assert "pending independent review" in result["reasons"][0]


def test_declared_independent_review_is_not_automatically_authenticated():
    result = review_readiness(task("CA-103", "Independent source and CI review 2026-10-13"))
    assert result["review_readiness"] == "review_claimed_not_independently_authenticated"


def test_historical_gap_requires_reconciliation_not_automatic_retraction():
    item = task("CA-005", "independent review pending")
    item["phase00_batch30_review"] = {"unresolved_requirement": "Missing full receipt"}
    result = review_readiness(item)
    assert result["recorded_gate4"] is True
    assert len(result["reasons"]) == 2


def test_report_separates_pending_review_from_recipient_and_supplemental():
    ledger = ledger_with(
        task("CA-001", "independent human review pending"),
        task("CA-103", "Independent source and CI review 2026-10-13"),
    )
    output = review_report(ledger, {"tasks": {"ML-001": []}})
    assert output["recorded_gate4"] == 2
    assert output["explicitly_pending_independent_review"] == 1
    assert output["review_declared_external_authentication_needed"] == 1
    assert output["certified_by_this_audit"] == 0


def test_reject_duplicate_or_malformed_proofs():
    with pytest.raises(ValueError):
        review_report(ledger_with(task("CA-001", ""), task("CA-001", "")), {"tasks": {}})
    with pytest.raises(ValueError):
        review_readiness({"id": "CA-001", "gate4_proofs": "not a list"})


def test_cli_generates_nonpromoting_read_only_report(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs" / "development"
    docs.mkdir(parents=True)
    (docs / "v18-task-evidence.json").write_text(
        json.dumps(ledger_with(task("CA-001", "independent human review pending"))),
        encoding="utf-8",
    )
    (docs / "v18-supplemental-gate4-proofs.json").write_text(
        json.dumps({"tasks": {}}), encoding="utf-8"
    )
    output_path = tmp_path / "results" / "review.json"
    assert main(["--repo", str(root), "--output", str(output_path)]) == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["explicitly_pending_independent_review"] == 1
    assert output["certified_by_this_audit"] == 0
