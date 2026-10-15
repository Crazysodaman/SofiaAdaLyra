"""CA-2708 / CA-2310: Gate-4 CI metadata must agree with GitHub's actual run."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from sofia.verify.v18_ci_receipts import (
    audit_ci_receipts,
    gate4_ci_claims,
    validate_ci_run,
)
from sofia.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Crazysodaman/SofiaAdaLyra"


def _proof():
    return {
        "revision": "a" * 40,
        "ci": {
            "run_id": 12345, "head_sha": "a" * 40,
            "conclusion": "success",
            "test_ids": ["test/test_safe_operator_stop_revision.py"],
        },
    }


def _run():
    return {
        "id": 12345,
        "status": "completed",
        "conclusion": "success",
        "head_sha": "a" * 40,
        "head_branch": "main",
        "repository": {"full_name": REPOSITORY},
        "event": "push",
        "path": ".github/workflows/package-tests.yml",
    }


def test_true_completed_exact_revision_ci_metadata_is_acceptable():
    validate_ci_run("CA-1907", _proof(), _run())


@pytest.mark.parametrize("field,value", [
    ("id", 12346),
    ("status", "queued"),
    ("conclusion", "failure"),
    ("head_sha", "b" * 40),
    ("head_branch", "different-branch"),
    ("event", "schedule"),
    ("path", "outside/actions/run.sh"),
    ("repository", {"full_name": "attacker/forgery"}),
])
def test_mismatched_remote_ci_run_fails_closed(field, value):
    run = _run()
    run[field] = value
    with pytest.raises(RoadmapIntegrityError, match="contradicts"):
        validate_ci_run("CA-1907", _proof(), run)


@pytest.mark.parametrize("selector", [
    "../test/test_private.py",
    "test/../../safe.py",
    "docs/fake.md",
    "test/test_safe_operator_stop_revision.py; echo success",
    "test/test_safe_operator_stop_revision.py::invalid/selector",
])
def test_ci_test_selector_is_not_an_arbitrary_shell_string(selector):
    p = _proof()
    p["ci"]["test_ids"] = [selector]
    with pytest.raises(RoadmapIntegrityError, match="selector"):
        validate_ci_run("CA-1907", p, _run())


def test_invalid_external_receipt_cannot_be_repaired_by_a_local_success_claim():
    proof = _proof()
    run = _run()
    run["conclusion"] = "failure"
    proof["ci"]["conclusion"] = "success"
    with pytest.raises(RoadmapIntegrityError):
        validate_ci_run("CA-1907", proof, run)


def test_existing_gate4_claims_are_grouped_by_run_and_never_request_network():
    """Integration: real task evidence, a fake remote API, and no privilege grant."""
    claims = gate4_ci_claims(ROOT)
    by_run = {}
    for _task_id, proof in claims:
        run_id = proof["ci"]["run_id"]
        revision = proof["revision"]
        if run_id in by_run:
            assert by_run[run_id] == revision
        by_run[run_id] = revision

    visited = []
    def fake_loader(run_id):
        visited.append(run_id)
        return {
            "id": run_id,
            "status": "completed",
            "conclusion": "success",
            "head_sha": by_run[run_id],
            "head_branch": "main",
            "repository": {"full_name": REPOSITORY},
            "event": "push",
            "path": ".github/workflows/v18-gate4-fifty.yml",
        }

    receipt = audit_ci_receipts(ROOT, loader=fake_loader)
    assert receipt["authenticated_claims"] == len(claims)
    assert set(receipt["authenticated_run_ids"]) == set(by_run)
    assert sorted(visited) == sorted(by_run)
    assert receipt["authenticated_task_ids"] == sorted(id for id, _ in claims)
