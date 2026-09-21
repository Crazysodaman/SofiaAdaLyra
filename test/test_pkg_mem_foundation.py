import pytest

from sofia.package_foundations.mem import PromotionProposal


def test_unreviewed_candidate_is_never_eligible():
    proposal = PromotionProposal(('message-1',), 'A tentative preference')
    assert proposal.eligible_for_reviewed_promotion is False


def test_explicit_reviewer_is_only_eligibility_not_persistence():
    proposal = PromotionProposal(('message-1', 'message-2'), 'A tentative preference', 'reviewer-1')
    assert proposal.eligible_for_reviewed_promotion is True
    assert proposal.original_message_ids == ('message-1', 'message-2')


@pytest.mark.parametrize('ids', [(), ('',), ('same', 'same')])
def test_missing_or_duplicate_sources_are_rejected(ids):
    with pytest.raises(ValueError):
        PromotionProposal(ids, 'candidate')
