from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.evolve import (
    AmendmentApproval,
    AmendmentProposal,
    ApprovalAction,
    ApprovalVerifier,
    ProposalStatus,
    ProtectedTarget,
    approval_matches,
    content_digest,
    inspect,
)

NOW = datetime(2026, 9, 25, 16, tzinfo=timezone.utc)
OLD = "a" * 64
NEW = "b" * 64


def proposal(**changes):
    values = dict(
        proposal_id="review-1",
        target=ProtectedTarget.CONSTITUTION,
        expected_digest=OLD,
        proposed_digest=NEW,
        evidence_ids=("user-request-1",),
        reason="Review proposed wording",
        rollback_plan="Restore independently verified original",
        created_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    values.update(changes)
    return AmendmentProposal(**values)


def approval(p, **changes):
    values = dict(
        approval_id="approval-1",
        proposal_id=p.proposal_id,
        proposal_fingerprint=p.fingerprint,
        target=p.target,
        action=ApprovalAction.APPLY,
        approved_by="Sparks",
        approved_at=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(minutes=30),
        authority_reference="operator-session-1",
    )
    values.update(changes)
    return AmendmentApproval(**values)


def test_different_digest_only_requires_explicit_review():
    assert inspect(proposal(), NOW, observed_digest=OLD) is ProposalStatus.REQUIRES_EXPLICIT_REVIEW


def test_source_mismatch_unchanged_expiry_and_clock_are_distinct():
    assert inspect(proposal(), NOW, observed_digest=NEW) is ProposalStatus.SOURCE_MISMATCH
    assert inspect(proposal(proposed_digest=OLD), NOW, observed_digest=OLD) is ProposalStatus.UNCHANGED
    assert inspect(proposal(), NOW + timedelta(hours=1), observed_digest=OLD) is ProposalStatus.EXPIRED
    assert inspect(proposal(), NOW - timedelta(minutes=2), observed_digest=OLD) is ProposalStatus.CLOCK_UNCERTAIN


def test_proposal_fingerprint_is_stable_and_exact():
    p = proposal()
    assert p.fingerprint == proposal().fingerprint
    assert len(p.fingerprint) == 64
    assert p.fingerprint != proposal(reason="Different reviewed reason").fingerprint


def test_content_digest_is_exact_utf8_sha256():
    value = "Sofía\n"
    assert content_digest(value) == sha256(value.encode("utf-8")).hexdigest()


def test_approval_must_match_exact_proposal_action_and_time():
    p = proposal()
    a = approval(p)
    assert approval_matches(p, a, action=ApprovalAction.APPLY, now=NOW)
    assert not approval_matches(
        p,
        approval(p, proposal_fingerprint="c" * 64),
        action=ApprovalAction.APPLY,
        now=NOW,
    )
    assert not approval_matches(p, a, action=ApprovalAction.ROLLBACK, now=NOW)
    assert not approval_matches(
        p,
        approval(p, expires_at=NOW),
        action=ApprovalAction.APPLY,
        now=NOW,
    )


@pytest.mark.parametrize(
    "bad",
    [
        dict(proposal_id=""),
        dict(target="constitution"),
        dict(expected_digest="a" * 63),
        dict(expected_digest="A" * 64),
        dict(proposed_digest="x" * 64),
        dict(evidence_ids=()),
        dict(evidence_ids=("id", "id")),
        dict(reason=""),
        dict(rollback_plan=" "),
        dict(created_at=datetime(2026, 9, 25)),
        dict(expires_at=NOW - timedelta(minutes=2)),
    ],
)
def test_invalid_proposal_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        proposal(**bad)


def test_proposal_is_immutable():
    p = proposal()
    with pytest.raises(FrozenInstanceError):
        p.reason = "new reason"


def test_approval_verifier_is_abstract_and_no_self_approval_implementation():
    with pytest.raises(TypeError):
        ApprovalVerifier()
    import sofia.evolve as module
    assert not hasattr(module, "approve")
    assert not hasattr(module, "self_approve")
