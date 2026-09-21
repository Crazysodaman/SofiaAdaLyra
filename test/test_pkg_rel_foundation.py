import pytest

from sofia.package_foundations.rel import PreferenceRevision, Stance


def test_user_gesture_does_not_implicitly_review_sofia_preference():
    proposed = PreferenceRevision('sofia', 'head pats', Stance.UNCERTAIN, 'msg-1')
    assert not proposed.reviewed
    assert proposed.stance is Stance.UNCERTAIN


def test_explicit_review_does_not_grant_permission():
    revision = PreferenceRevision('sofia', 'head pats', Stance.DISLIKES, 'msg-2', 'review-1')
    assert revision.reviewed
    assert revision.stance is Stance.DISLIKES


def test_missing_original_is_rejected():
    with pytest.raises(ValueError):
        PreferenceRevision('sofia', 'head pats', Stance.LIKES, '')
