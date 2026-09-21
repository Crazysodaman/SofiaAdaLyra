import pytest

from sofia.package_foundations.act import DeliveryIntent


def test_default_is_not_eligible():
    assert not DeliveryIntent('discord', 'recipient', 'event').eligible_for_authorization


def test_delivery_requires_explicit_opt_in_and_no_quiet_or_mute():
    intent = DeliveryIntent('discord', 'recipient', 'event', True, False, False)
    assert intent.eligible_for_authorization
    assert not DeliveryIntent('discord', 'recipient', 'event', True, True).eligible_for_authorization
    assert not DeliveryIntent('discord', 'recipient', 'event', True, False, True).eligible_for_authorization


def test_empty_recipient_is_rejected():
    with pytest.raises(ValueError):
        DeliveryIntent('discord', '', 'event')
