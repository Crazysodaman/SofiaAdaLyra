import pytest

from sofia.package_foundations.ui import ExpressionDelivery


def test_planned_avatar_does_not_claim_playback():
    delivery = ExpressionDelivery(('text', 'avatar'))
    assert delivery.status('avatar') == 'pending'
    assert delivery.status('voice') == 'not_requested'


def test_receipt_marker_is_explicitly_unverified():
    delivery = ExpressionDelivery(('avatar',), ('avatar',))
    assert delivery.status('avatar') == 'reported_acknowledged_unverified'


def test_unplanned_acknowledgment_rejected():
    with pytest.raises(ValueError):
        ExpressionDelivery(('text',), ('voice',))
