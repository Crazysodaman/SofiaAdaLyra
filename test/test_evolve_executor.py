from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

import pytest

from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.evolve import (
    AmendmentApproval,
    AmendmentExecutionStatus,
    AmendmentProposal,
    ApprovalAction,
    ApprovalVerifier,
    ProtectedAmendmentError,
    ProtectedAmendmentExecutor,
    ProtectedPaths,
    ProtectedTarget,
    content_digest,
)

NOW = datetime(2026, 9, 25, 17, tzinfo=timezone.utc)


class ExactVerifier(ApprovalVerifier):
    def __init__(self, accepted_ids):
        self.accepted_ids = set(accepted_ids)
        self.calls = []

    def verify(self, proposal, approval, *, now):
        self.calls.append((proposal.proposal_id, approval.approval_id, approval.action))
        return (
            approval.approval_id in self.accepted_ids
            and approval.approved_by == "Sparks"
        )


@pytest.fixture
def protected(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE original_state (value TEXT)")
        db.execute("INSERT INTO original_state VALUES ('keep')")

    identity = tmp_path / "identity.json"
    old_identity = json.dumps(
        {"name": "Sofía Ada Lyra", "instance_id": str(uuid4())},
        ensure_ascii=False,
        indent=2,
    )
    identity.write_text(old_identity, encoding="utf-8")

    constitution = tmp_path / "constitution.md"
    old_constitution = "# Constitution\n\nOriginal protected text.\n"
    constitution.write_text(old_constitution, encoding="utf-8")
    constitution_hash = tmp_path / "constitution.sha256"
    constitution_hash.write_text(
        f"{content_digest(old_constitution)}\n",
        encoding="utf-8",
    )

    paths = ProtectedPaths(
        identity_path=identity,
        constitution_path=constitution,
        constitution_hash_path=constitution_hash,
        backup_dir=tmp_path / "backups",
    )
    return {
        "state": state,
        "paths": paths,
        "old_identity": old_identity,
        "old_constitution": old_constitution,
    }


def make_proposal(target, old_content, new_content, proposal_id="p1"):
    return AmendmentProposal(
        proposal_id=proposal_id,
        target=target,
        expected_digest=content_digest(old_content),
        proposed_digest=content_digest(new_content),
        evidence_ids=("review-source-1",),
        reason="Reviewed exact revision",
        rollback_plan="Restore verified pre-change backup",
        created_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=2),
    )


def make_approval(p, approval_id, action):
    return AmendmentApproval(
        approval_id=approval_id,
        proposal_id=p.proposal_id,
        proposal_fingerprint=p.fingerprint,
        target=p.target,
        action=action,
        approved_by="Sparks",
        approved_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
        authority_reference="trusted-operator-session",
    )


def executor(protected, accepted=("apply-1", "rollback-1")):
    verifier = ExactVerifier(accepted)
    return (
        ProtectedAmendmentExecutor(
            state_path=protected["state"],
            paths=protected["paths"],
            verifier=verifier,
        ),
        verifier,
    )


def test_identity_apply_and_separately_approved_rollback(protected):
    old = protected["old_identity"]
    identity = json.loads(old)
    identity["name"] = "Sofía Ada Lyra"
    identity["instance_id"] = str(uuid4())
    new = json.dumps(identity, ensure_ascii=False, indent=2)

    p = make_proposal(ProtectedTarget.IDENTITY, old, new)
    apply = make_approval(p, "apply-1", ApprovalAction.APPLY)
    rollback = make_approval(p, "rollback-1", ApprovalAction.ROLLBACK)
    ex, verifier = executor(protected)

    applied = ex.apply(p, apply, proposed_content=new, now=NOW)
    assert applied.status is AmendmentExecutionStatus.APPLIED
    assert protected["paths"].identity_path.read_text(encoding="utf-8") == new
    assert applied.backup_path.read_text(encoding="utf-8") == old
    assert verifier.calls[-1][2] is ApprovalAction.APPLY

    restored = ex.rollback(p, rollback, now=NOW + timedelta(minutes=10))
    assert restored.status is AmendmentExecutionStatus.ROLLED_BACK
    assert protected["paths"].identity_path.read_text(encoding="utf-8") == old
    assert restored.rollback_approval_id == "rollback-1"
    assert verifier.calls[-1][2] is ApprovalAction.ROLLBACK


def test_constitution_apply_updates_trusted_hash_and_rollback_restores_both(protected):
    old = protected["old_constitution"]
    new = "# Constitution\n\nReviewed replacement text.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, new)
    ex, _ = executor(protected)

    applied = ex.apply(
        p,
        make_approval(p, "apply-1", ApprovalAction.APPLY),
        proposed_content=new,
        now=NOW,
    )
    assert applied.hash_backup_path is not None
    assert protected["paths"].constitution_path.read_text(encoding="utf-8") == new
    assert (
        protected["paths"].constitution_hash_path.read_text(encoding="utf-8").strip()
        == content_digest(new)
    )
    ConstitutionIntegrityVerifier(
        str(protected["paths"].constitution_hash_path)
    ).verify(ConstitutionStore(protected["paths"].constitution_path).load())

    ex.rollback(
        p,
        make_approval(p, "rollback-1", ApprovalAction.ROLLBACK),
        now=NOW + timedelta(minutes=10),
    )
    assert protected["paths"].constitution_path.read_text(encoding="utf-8") == old
    assert (
        protected["paths"].constitution_hash_path.read_text(encoding="utf-8").strip()
        == content_digest(old)
    )


def test_unverified_approval_cannot_mutate_protected_state(protected):
    old = protected["old_constitution"]
    new = "# Constitution\nDenied replacement.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, new)
    ex, _ = executor(protected, accepted=())
    with pytest.raises(PermissionError, match="verification"):
        ex.apply(
            p,
            make_approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content=new,
            now=NOW,
        )
    assert protected["paths"].constitution_path.read_text(encoding="utf-8") == old
    assert not protected["paths"].backup_dir.exists()


def test_wrong_action_or_revision_approval_cannot_apply(protected):
    old = protected["old_identity"]
    new = json.dumps(
        {"name": "Sofía Ada Lyra", "instance_id": str(uuid4())},
        ensure_ascii=False,
        indent=2,
    )
    p = make_proposal(ProtectedTarget.IDENTITY, old, new)
    ex, _ = executor(protected)

    with pytest.raises(PermissionError, match="exact proposal"):
        ex.apply(
            p,
            make_approval(p, "rollback-1", ApprovalAction.ROLLBACK),
            proposed_content=new,
            now=NOW,
        )

    wrong = make_approval(p, "apply-1", ApprovalAction.APPLY)
    wrong = AmendmentApproval(
        approval_id=wrong.approval_id,
        proposal_id=wrong.proposal_id,
        proposal_fingerprint="f" * 64,
        target=wrong.target,
        action=wrong.action,
        approved_by=wrong.approved_by,
        approved_at=wrong.approved_at,
        expires_at=wrong.expires_at,
        authority_reference=wrong.authority_reference,
    )
    with pytest.raises(PermissionError, match="exact proposal"):
        ex.apply(p, wrong, proposed_content=new, now=NOW)


def test_proposed_content_digest_must_match_reviewed_revision(protected):
    old = protected["old_constitution"]
    reviewed = "# Constitution\nReviewed.\n"
    unreviewed = "# Constitution\nDifferent.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, reviewed)
    ex, _ = executor(protected)
    with pytest.raises(ProtectedAmendmentError, match="does not match"):
        ex.apply(
            p,
            make_approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content=unreviewed,
            now=NOW,
        )
    assert protected["paths"].constitution_path.read_text(encoding="utf-8") == old


def test_source_drift_blocks_apply_even_with_valid_approval(protected):
    old = protected["old_constitution"]
    new = "# Constitution\nReviewed.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, new)
    protected["paths"].constitution_path.write_text(
        "# Constitution\nConcurrent edit.\n",
        encoding="utf-8",
    )
    ex, _ = executor(protected)
    with pytest.raises(ProtectedAmendmentError, match="source_mismatch"):
        ex.apply(
            p,
            make_approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content=new,
            now=NOW,
        )


def test_tamper_after_apply_blocks_rollback_instead_of_overwriting_newer_state(protected):
    old = protected["old_constitution"]
    new = "# Constitution\nReviewed.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, new)
    ex, _ = executor(protected)
    ex.apply(
        p,
        make_approval(p, "apply-1", ApprovalAction.APPLY),
        proposed_content=new,
        now=NOW,
    )
    tampered = "# Constitution\nLater independent change.\n"
    protected["paths"].constitution_path.write_text(tampered, encoding="utf-8")

    with pytest.raises(ProtectedAmendmentError, match="changed since"):
        ex.rollback(
            p,
            make_approval(p, "rollback-1", ApprovalAction.ROLLBACK),
            now=NOW + timedelta(minutes=10),
        )
    assert protected["paths"].constitution_path.read_text(encoding="utf-8") == tampered


def test_duplicate_apply_is_idempotent_only_when_exact_applied_state_still_exists(protected):
    old = protected["old_constitution"]
    new = "# Constitution\nReviewed.\n"
    p = make_proposal(ProtectedTarget.CONSTITUTION, old, new)
    ex, _ = executor(protected)
    a = make_approval(p, "apply-1", ApprovalAction.APPLY)
    first = ex.apply(p, a, proposed_content=new, now=NOW)
    second = ex.apply(p, a, proposed_content=new, now=NOW)
    assert first == second


def test_invalid_identity_content_is_rejected_before_backup_or_write(protected):
    old = protected["old_identity"]
    invalid = '{"name": "Sofía Ada Lyra", "instance_id": "not-a-uuid"}'
    p = make_proposal(ProtectedTarget.IDENTITY, old, invalid)
    ex, _ = executor(protected)
    with pytest.raises(ProtectedAmendmentError, match="UUID"):
        ex.apply(
            p,
            make_approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content=invalid,
            now=NOW,
        )
    assert protected["paths"].identity_path.read_text(encoding="utf-8") == old


def test_existing_state_database_is_required(tmp_path, protected):
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        ProtectedAmendmentExecutor(
            state_path=missing,
            paths=protected["paths"],
            verifier=ExactVerifier({"apply-1"}),
        )
