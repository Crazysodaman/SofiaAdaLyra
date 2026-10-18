"""Unit tests for V18 audit-before-edit guard, using disposable real Git history."""
import json
import subprocess
from pathlib import Path

import pytest

from scripts.v18_change_guard import verify


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_verify]


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "ci@example.invalid")
    git(repo, "config", "user.name", "CI")
    file = repo / "src" / "sofia" / "feature.py"
    file.parent.mkdir(parents=True)
    file.write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    base = git(repo, "rev-parse", "HEAD")
    file.write_text("VALUE = 2\n", encoding="utf-8")
    git(repo, "commit", "-am", "update")
    manifest = {
        "schema_version": 1,
        "tasks": [{
            "task_id": "CA-005",
            "original_requirement": "Source to sink event ownership",
            "existing_behavior": "Projection already exists",
            "missing_requirement": "Expired event filtering",
            "production_caller": "project_companion_decision",
            "regression_tests": "test/test_v18_phase00_contracts.py",
        }],
        "reviewed_existing_paths": {
            "src/sofia/feature.py": {
                "before": "VALUE = 1",
                "preserved": "Existing public constant",
                "reason": "Correct behavior to VALUE = 2",
            }
        },
    }
    return repo, base, manifest


def test_guard_accepts_prechange_audited_edit(history):
    repo, base, manifest = history
    outcome = verify(repo, manifest, base=base)
    assert outcome["tasks_reviewed"] == ["CA-005"]
    assert outcome["status"] == "change_review_only_not_stage_promotion"


def test_guard_fails_when_existing_production_review_missing(history):
    repo, base, manifest = history
    manifest["reviewed_existing_paths"] = {}
    with pytest.raises(ValueError, match="without review"):
        verify(repo, manifest, base=base)


def test_guard_rejects_fake_stage_and_missing_requirements(history):
    repo, base, manifest = history
    manifest["tasks"][0]["missing_requirement"] = ""
    with pytest.raises(ValueError, match="missing missing_requirement"):
        verify(repo, manifest, base=base)


def test_guard_rejects_unapproved_deletion(history):
    repo, base, manifest = history
    (repo / "src/sofia/feature.py").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "remove implementation")
    with pytest.raises(ValueError, match="explicit approval"):
        verify(repo, manifest, base=base)


def test_guard_requires_real_ancestor(history):
    repo, base, manifest = history
    with pytest.raises(ValueError, match="ancestor"):
        verify(repo, manifest, base=git(repo, "rev-parse", "HEAD"), head=base)


def test_guard_rejects_invented_prechange_evidence(history):
    repo, base, manifest = history
    manifest["reviewed_existing_paths"]["src/sofia/feature.py"]["before"] = (
        "this function never existed"
    )
    with pytest.raises(ValueError, match="pre-change source evidence not found"):
        verify(repo, manifest, base=base)


def test_guard_does_not_accept_postchange_source_as_prechange(history):
    repo, base, manifest = history
    manifest["reviewed_existing_paths"]["src/sofia/feature.py"]["before"] = (
        "VALUE = 2"
    )
    with pytest.raises(ValueError, match="pre-change source evidence not found"):
        verify(repo, manifest, base=base)
