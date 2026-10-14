"""Regression: independent artifact checks fail closed on malformed criteria."""
from datetime import datetime, timezone
from hashlib import sha256
import pytest

from sofia.creative.model import ArtifactKind, ArtifactRevision
from sofia.life.validation import ObjectiveDisposition, inspect_objective_artifact

pytestmark = pytest.mark.pkg_verify


def revision_for(path, content):
    return ArtifactRevision(
        artifact_id="proof-1", project_id="proof-2", revision=1,
        kind=ArtifactKind.STORY, title="Test artifact",
        content_sha256=sha256(content).hexdigest(),
        content_path=str(path), media_type="text/plain",
        byte_size=len(content), tool_id="local-probe", tool_version="1",
        preview_sha256=None, test_summary="untrusted score",
        license_id="internal", author_principal_id="owner",
        audience_id="private", evidence_ref="receipt-1", source_receipt_id=None,
        created_at=datetime.now(timezone.utc),
    )


def test_size_criterion_cannot_raise_on_extremely_long_decimal(tmp_path):
    content = b"checked content"
    path = tmp_path / "item.txt"
    path.write_bytes(content)
    result = inspect_objective_artifact(
        revision=revision_for(path, content),
        path=path, objectives=("min_bytes:" + "9" * 5000,),
    )
    assert result.integrity is ObjectiveDisposition.PASS
    assert result.findings[0].disposition is ObjectiveDisposition.UNKNOWN
    assert not result.eligible_for_independent_completion


def test_file_integrity_and_unreviewed_objectives_do_not_claim_success(tmp_path):
    content = b"A required verified phrase"
    path = tmp_path / "item.txt"
    path.write_bytes(content)
    revision = revision_for(path, content)
    good = inspect_objective_artifact(
        revision=revision, path=path,
        objectives=("text_contains:verified phrase", "min_bytes:3"),
    )
    assert good.eligible_for_independent_completion
    unknown = inspect_objective_artifact(
        revision=revision, path=path,
        objectives=("Make a critically acclaimed novel",),
    )
    assert unknown.findings[0].disposition is ObjectiveDisposition.UNKNOWN
    assert not unknown.eligible_for_independent_completion
    empty = inspect_objective_artifact(
        revision=revision, path=path, objectives=(),
    )
    assert not empty.eligible_for_independent_completion
    path.write_bytes(b"mutated")
    corrupted = inspect_objective_artifact(
        revision=revision, path=path,
        objectives=("min_bytes:1",),
    )
    assert corrupted.integrity is ObjectiveDisposition.FAIL
    assert not corrupted.eligible_for_independent_completion
