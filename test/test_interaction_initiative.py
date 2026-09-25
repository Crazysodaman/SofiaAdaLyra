"""Pure reciprocal initiative gates, no model or background worker."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.interaction.initiative import InitiativeGate
from sofia.interaction.registry import InteractionCatalog

T = datetime(2026, 9, 20, tzinfo=timezone.utc)


@pytest.fixture
def gate():
    return InitiativeGate(InteractionCatalog(('head', 'chest', 'left-hand', 'right-hand')))


def proposed(gate, kind='gesture', expiration=None, **overrides):
    fields = dict(proposal_id='p1', source_id='saved-message', kind=kind,
                  semantic_id='touch' if kind in ('gesture', 'offer') else None,
                  at=T, expires_at=expiration)
    fields.update(overrides)
    return gate.propose(**fields)


def transition(gate, proposal, action='describe', **overrides):
    fields = dict(at=T + timedelta(seconds=1), stopped=False,
                  user_boundary_active=False)
    fields.update(overrides)
    return gate.transition(proposal, action=action, **fields)


def test_contact_requires_per_event_permission_and_fresh_stop_check(gate):
    item = proposed(gate)
    with pytest.raises(ValueError):
        transition(gate, item)
    permitted = transition(gate, item, 'permit', permission_source_id='user-accepts')
    assert permitted.state == 'permitted'
    assert transition(gate, permitted, stopped=True).state == 'cancelled'
    assert transition(gate, permitted, user_boundary_active=True).state == 'cancelled'
    described = transition(gate, permitted)
    assert described.state == 'described'
    assert transition(gate, described, 'permit') == described  # No replay.


def test_an_offer_is_not_contact_and_decline_is_terminal(gate):
    offered = proposed(gate, kind='offer')
    assert transition(gate, offered).state == 'described'
    assert transition(gate, offered, stopped=True).state == 'cancelled'
    declined = transition(gate, offered, 'decline')
    assert declined.state == 'declined'
    assert transition(gate, declined, 'describe') == declined


def test_questions_are_non_contact_and_unknown_acts_abstain(gate):
    assert transition(gate, proposed(gate, kind='question')).state == 'described'
    with pytest.raises(ValueError):
        proposed(gate, kind='question', semantic_id='pat')
    with pytest.raises(ValueError):
        proposed(gate, semantic_id='unreviewed-act')
    with pytest.raises(ValueError):
        proposed(gate, region_id='invented-region')
    with pytest.raises(ValueError):
        transition(gate, proposed(gate), 'permit', permission_source_id='')
    with pytest.raises(TypeError):
        transition(gate, proposed(gate), stopped=None)


def test_expiry_and_cancel_do_not_create_contact(gate):
    item = proposed(gate, expiration=T + timedelta(milliseconds=500))
    assert transition(gate, item).state == 'expired'
    assert transition(gate, item, 'cancel').state == 'cancelled'
