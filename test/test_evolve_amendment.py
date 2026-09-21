from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError
import pytest
from sofia.evolve import AmendmentProposal, ProtectedTarget, ProposalStatus, inspect

NOW = datetime(2026, 9, 21, 20, tzinfo=timezone.utc)
OLD = "a" * 64
NEW = "b" * 64


def proposal(**kw):
    values = dict(proposal_id="review-1", target=ProtectedTarget.CONSTITUTION,
                  expected_digest=OLD, proposed_digest=NEW, evidence_ids=("user-request-1",),
                  reason="Review proposed wording", rollback_plan="Restore independently verified original",
                  created_at=NOW-timedelta(minutes=1), expires_at=NOW+timedelta(minutes=1))
    values.update(kw)
    return AmendmentProposal(**values)


def test_different_digest_only_requires_explicit_review():
    assert inspect(proposal(), NOW, observed_digest=OLD) is ProposalStatus.REQUIRES_EXPLICIT_REVIEW


def test_identity_also_needs_explicit_review():
    assert inspect(proposal(target=ProtectedTarget.IDENTITY), NOW, observed_digest=OLD) is ProposalStatus.REQUIRES_EXPLICIT_REVIEW


def test_identical_digest_no_change():
    assert inspect(proposal(proposed_digest=OLD), NOW, observed_digest=OLD) is ProposalStatus.UNCHANGED


def test_existing_state_mismatch_fail_closed():
    assert inspect(proposal(), NOW, observed_digest=NEW) is ProposalStatus.SOURCE_MISMATCH


def test_expired_proposal():
    assert inspect(proposal(), NOW+timedelta(minutes=1), observed_digest=OLD) is ProposalStatus.EXPIRED


def test_future_proposal_clock_uncertain():
    assert inspect(proposal(), NOW-timedelta(minutes=2), observed_digest=OLD) is ProposalStatus.CLOCK_UNCERTAIN


def test_timezones_normalize():
    east = timezone(timedelta(hours=2))
    assert inspect(proposal(), NOW.astimezone(east), observed_digest=OLD) is ProposalStatus.REQUIRES_EXPLICIT_REVIEW


@pytest.mark.parametrize("bad", [dict(proposal_id=""), dict(target="constitution"), dict(expected_digest="a" * 63), dict(expected_digest="A" * 64), dict(proposed_digest="x" * 64), dict(evidence_ids=()), dict(evidence_ids=("",)), dict(evidence_ids=("id", "id")), dict(reason=""), dict(rollback_plan=" "), dict(created_at=datetime(2026, 9, 21)), dict(expires_at=NOW-timedelta(minutes=2))])
def test_invalid_proposal_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        proposal(**bad)


def test_unverified_digest_denied():
    with pytest.raises(ValueError):
        inspect(proposal(), NOW, observed_digest="original")


def test_naive_time_denied():
    with pytest.raises(ValueError):
        inspect(proposal(), datetime(2026, 9, 21), observed_digest=OLD)


def test_wrong_object_denied():
    with pytest.raises(TypeError):
        inspect("please change identity", NOW, observed_digest=OLD)


def test_proposal_is_immutable():
    p = proposal()
    with pytest.raises(FrozenInstanceError):
        p.reason = "new reason"


def test_no_approval_or_write_api():
    import sofia.evolve as module
    assert set(module.__all__) == {"AmendmentProposal", "ProtectedTarget", "ProposalStatus", "inspect"}
    assert not hasattr(module, "approve") and not hasattr(module, "apply")
