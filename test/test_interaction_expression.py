"""Test expression intent vs actual output; no audio or animation is played."""
import pytest

from sofia.interaction.expression import ExpressionPlanner
from sofia.interaction.registry import InteractionCatalog


@pytest.fixture
def planner():
    return ExpressionPlanner(InteractionCatalog(('head', 'left-ear', 'right-ear')))


def planned(planner, **overrides):
    fields = dict(plan_id='p1', source_id='source1', expression_id='laugh')
    fields.update(overrides)
    return planner.plan(**fields)


def test_text_expression_is_only_described_after_message_receipt(planner):
    item = planned(planner)
    assert item.state == 'planned' and item.acknowledgment_id is None
    described = planner.acknowledge(item, receipt_id='saved-assistant-message')
    assert described.state == 'described'
    assert described.acknowledgment_id == 'saved-assistant-message'
    with pytest.raises(ValueError):
        planner.acknowledge(described, receipt_id='another-receipt')


def test_voice_and_avatar_are_unsupported_without_a_verified_adapter(planner):
    assert planned(planner, channel='voice').state == 'unsupported'
    capable = ExpressionPlanner(
        planner.catalog, frozenset(('text', 'voice', 'avatar')),
    )
    for channel in ('voice', 'avatar'):
        item = planned(capable, channel=channel)
        with pytest.raises(ValueError):
            capable.acknowledge(item, receipt_id='unverified')
        confirmed = capable.acknowledge(
            item, receipt_id='verified-external-ack', adapter_verified=True,
        )
        assert confirmed.state == 'executed'


def test_blocked_contact_never_generates_expression_as_completed(planner):
    assert planned(planner, originating_contact=True).state == 'blocked'
    item = planned(planner, originating_contact=True, contact_permitted=True)
    assert planner.acknowledge(
        item, receipt_id='saved-message', contact_still_permitted=False,
    ).state == 'blocked'
    assert planned(planner, expression_id='none').state == 'silent'
    assert planner.cancel(item).state == 'cancelled'


def test_cry_and_laugh_are_not_fixed_emotion_equations(planner):
    assert planned(planner, expression_id='cry').expression_id == 'cry'
    assert planned(planner, expression_id='giggle').expression_id == 'giggle'
    with pytest.raises(ValueError):
        planned(planner, expression_id='unknown-expression')
    with pytest.raises(ValueError):
        planned(planner, intensity='unreviewed-intensity')
