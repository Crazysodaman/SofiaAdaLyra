"""Gate 4 proofs are per-task and cannot be fabricated by a green package badge."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from sofia.verify.v18_gate4 import gate4_snapshot, markdown_summary
from sofia.verify.v18_roadmap import LEDGER_RELATIVE, RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def _committed_digest(relative):
    import subprocess
    return sha256(subprocess.run(
        ("git", "show", "HEAD:" + relative),
        cwd=ROOT, capture_output=True, check=True, timeout=15,
    ).stdout).hexdigest()


def ledger():
    return json.loads((ROOT / LEDGER_RELATIVE).read_text(encoding="utf-8"))


def test_every_task_has_next_action_and_phase_tracking():
    report = gate4_snapshot(ROOT)
    assert report["original_total"] == len(report["tasks"]) == 700
    assert report["planned_total"] == 780
    assert len(report["supplemental_tasks"]) == 80
    assert len({x["id"] for x in report["supplemental_tasks"]}) == 80
    assert report["overall_gate4_recorded"] + report["overall_without_gate4_proof"] == 780
    assert len({row["id"] for row in report["tasks"]}) == 700
    assert sum(p["total"] for p in report["phases"].values()) == 700
    n = report["counts"]
    assert n["gate4_recorded"] + n["still_without_gate4_proof"] == 700
    assert sum(n[x] for x in ("unassessed", "partial_wiring",
                              "code_present_unverified", "accepted")) == 700
    assert report["deferred"] == [5, 6]
    assert all(item["next_action"] for item in report["tasks"])
    assert "Next 20 candidate tasks" in markdown_summary(report)


@pytest.mark.parametrize("claim", [True, "passed", {"gate": 4}, [True], [1,2,3,4,5]])
def test_no_self_awarded_gate_from_source_or_claim(claim):
    data = ledger()
    data["tasks"][0]["gate4_proofs"] = claim
    with pytest.raises(RoadmapIntegrityError):
        gate4_snapshot(ROOT, ledger=data)


def test_cannot_skip_to_four_or_claim_ci_without_receipt():
    data = ledger()
    data["tasks"][0]["gate4_proofs"] = [{"gate": 4}]
    with pytest.raises(RoadmapIntegrityError):
        gate4_snapshot(ROOT, ledger=data)
    path = ROOT / "docs/development/v18-phase00-batch30-report.md"
    common = {"revision": "a" * 40, "reviewer": "fixture",
              "evidence_path": "docs/development/v18-phase00-batch30-report.md",
              "sha256": _committed_digest("docs/development/v18-phase00-batch30-report.md")}
    data["tasks"][0]["gate4_proofs"] = [dict(common, gate=n) for n in range(1, 5)]
    with pytest.raises(RoadmapIntegrityError, match="CI test receipt"):
        gate4_snapshot(ROOT, ledger=data)


def test_gate_evidence_is_content_bound_and_sequential():
    data = ledger()
    path = ROOT / "docs/development/v18-phase00-batch30-report.md"
    proof = {"gate": 1, "revision": "b" * 40, "reviewer": "fixture",
             "evidence_path": "docs/development/v18-phase00-batch30-report.md",
             "sha256": _committed_digest("docs/development/v18-phase00-batch30-report.md")}
    data["tasks"][0]["gate4_proofs"] = [deepcopy(proof)]
    row = gate4_snapshot(ROOT, ledger=data)["tasks"][0]
    assert row["gate_with_recorded_proof"] == 1
    assert not row["gate4"]
    data["tasks"][0]["gate4_proofs"][0]["sha256"] = "0" * 64
    with pytest.raises(RoadmapIntegrityError, match="digest"):
        gate4_snapshot(ROOT, ledger=data)


def test_reporting_does_not_edit_task_status():
    path = ROOT / LEDGER_RELATIVE
    before = path.read_bytes()
    gate4_snapshot(ROOT)
    assert path.read_bytes() == before
