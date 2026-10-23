"""CA-3501 oracle contract stays grounded in real code owners."""
from pathlib import Path

import pytest

from sofia.core.life.validation import (
    ArtifactObjectiveReport, ObjectiveDisposition, ObjectiveFinding,
)
from sofia.core.creative.model import ArtifactKind
from test.test_life_objective_parser_bounded import revision_for
from sofia.core.life.validation import inspect_objective_artifact

pytestmark = pytest.mark.pkg_verify

DOC = (Path(__file__).resolve().parents[1]
       / "docs/development/phase09-success-oracle-contract.md")


def test_success_oracle_contract_separates_four_evidence_kinds():
    text = DOC.read_text(encoding="utf-8")
    for term in ("Did an artifact exist?", "Did it satisfy technical objectives?",
                 "Was it useful or liked?", "Did the project reach its milestone?",
                 "CreativeExplorer.verified_preview", "PersonalJudgment",
                 "original RUN", "UNKNOWN", "SHA-256", "principal", "audience"):
        assert term in text


def test_objective_validator_does_not_award_success_for_unknown_work(tmp_path):
    content = b"A measurable result does not assert it was useful."
    path = tmp_path / "note.txt"
    path.write_bytes(content)
    record = revision_for(path, content)
    report = inspect_objective_artifact(
        revision=record, path=path,
        objectives=("min_bytes:4", "Make readers happy"),
    )
    assert report.integrity is ObjectiveDisposition.PASS
    assert report.findings[0].disposition is ObjectiveDisposition.PASS
    assert report.findings[1].disposition is ObjectiveDisposition.UNKNOWN
    assert not report.eligible_for_independent_completion


def test_empty_or_unverified_criteria_cannot_complete_project():
    report = ArtifactObjectiveReport(
        artifact_id="evidence:unused", revision=1, content_sha256="0" * 64,
        integrity=ObjectiveDisposition.PASS, findings=(),
    )
    assert not report.eligible_for_independent_completion
    report = ArtifactObjectiveReport(
        artifact_id="evidence:unused", revision=1, content_sha256="0" * 64,
        integrity=ObjectiveDisposition.FAIL, findings=(
            ObjectiveFinding("min_bytes:1", ObjectiveDisposition.PASS,
                             "min_bytes", "size criterion met"),
        ),
    )
    assert not report.eligible_for_independent_completion
