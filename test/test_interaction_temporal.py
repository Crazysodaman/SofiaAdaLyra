"""Isolated I10 journal tests. Never open state/sofia.db or its backup."""
from datetime import datetime, timezone

import pytest

from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.temporal import InteractionStateJournal

AT = datetime(2026, 9, 20, tzinfo=timezone.utc)


@pytest.fixture
def journal(tmp_path):
    return InteractionStateJournal(
        tmp_path / 'isolated-interaction-state.db',
        InteractionCatalog(('head', 'chest', 'left-hand', 'right-hand')),
    )


def preference(journal, revision, direction, prior=None, **overrides):
    fields = dict(revision_id=revision, subject='sofia', semantic_id='pat',
                  region_id='head', context='playful', direction=direction,
                  origin='sofia_explicit', source_id='assistant-message-' + revision,
                  prior_id=prior, at=AT)
    fields.update(overrides)
    return journal.record_preference(**fields)


def boundary(journal, revision, active, prior=None, **overrides):
    fields = dict(revision_id=revision, subject='user', semantic_id='pat',
                  region_id='head', active=active,
                  source_id='user-message-' + revision, prior_id=prior, at=AT)
    fields.update(overrides)
    return journal.record_boundary(**fields)


def test_explicit_preference_changes_both_ways_and_survives_restart(journal):
    scope = dict(subject='sofia', semantic_id='pat', region_id='head', context='playful')
    assert journal.preference(**scope) is None
    preference(journal, 'p1', 'enjoy')
    dislike = preference(journal, 'p2', 'dislike', prior='p1')
    assert preference(journal, 'p2', 'dislike', prior='p1') == dislike
    with pytest.raises(ValueError):
        preference(journal, 'p3', 'enjoy', prior=None)
    with pytest.raises(ValueError):
        preference(journal, 'p2', 'enjoy', prior='p1')
    assert [r.direction for r in journal.preference_history(**scope)] == ['enjoy', 'dislike']
    restarted = InteractionStateJournal(journal.path, journal.catalog)
    assert restarted.preference(**scope).direction == 'dislike'
    assert preference(restarted, 'p4', 'mixed', prior='p2').direction == 'mixed'
    assert [r.direction for r in restarted.preference_history(**scope)] == [
        'enjoy', 'dislike', 'mixed',
    ]


def test_explicit_boundaries_are_scoped_and_revocable(journal):
    def active(actor='user', gesture='pat', region='head'):
        return journal.boundary_active(subject=actor, semantic_id=gesture, region_id=region)
    assert not active()
    first = boundary(journal, 'b1', True)
    assert boundary(journal, 'b1', True) == first
    assert active() and not active(gesture='touch')
    boundary(journal, 'b2', False, prior='b1')
    assert not active()
    boundary(journal, 'b3', True, semantic_id='*', region_id='*')
    assert active(gesture='touch', region='chest')
    assert not active(actor='sofia', gesture='touch', region='chest')
    with pytest.raises(ValueError):
        boundary(journal, 'b4', False, prior='b1')


def test_no_inferred_preference_or_unreviewed_semantics(journal):
    with pytest.raises(ValueError):
        preference(journal, 'p5', 'enjoy', origin='model_inferred')
    with pytest.raises(ValueError):
        preference(journal, 'p5', 'enjoy', semantic_id='unrecognized-act')
    with pytest.raises(ValueError):
        preference(journal, 'p5', 'enjoy', region_id='made-up-anatomy')
    with pytest.raises(ValueError):
        boundary(journal, 'b5', 1)
    with pytest.raises(ValueError):
        preference(journal, 'p5', 'enjoy', at=datetime(2026, 9, 20))
    assert journal.preference_history(
        subject='sofia', semantic_id='pat', region_id='head', context='playful',
    ) == ()
