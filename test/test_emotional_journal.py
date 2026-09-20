"""Offline contracts for Batch G evidence-linked emotional continuity."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.personality.emotion import EmotionalJournal
from sofia.personality.expression import personality_expression_guidance

NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def test_blended_events_survive_restart_and_do_not_duplicate(tmp_path):
    path = tmp_path / 'state.db'
    journal = EmotionalJournal(path)
    kwargs = dict(event_id='test-1', source='user_reported', evidence_ref='message-1',
                  description='User reported a repeated test failure.',
                  emotions=('frustration', 'curiosity', 'determination'), occurred_at=NOW)
    journal.record(**kwargs)
    journal.record(**kwargs)
    reloaded = EmotionalJournal(path)
    assert len(reloaded.recent(now=NOW)) == 1
    event = reloaded.recent(now=NOW)[0]
    assert event.original_emotions == ('frustration', 'curiosity', 'determination')
    assert event.source == 'user_reported'
    assert event.evidence_ref == 'message-1'


def test_conflicting_event_id_is_rejected(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    kwargs = dict(event_id='same', source='observed', evidence_ref='probe',
                  description='Observed result.', emotions=('curiosity',), occurred_at=NOW)
    journal.record(**kwargs)
    with pytest.raises(ValueError, match='different evidence'):
        journal.record(**{**kwargs, 'emotions': ('relief',)})


def test_reappraisal_preserves_original_emotional_tie(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(event_id='failure', source='user_reported', evidence_ref='message-7',
                   description='User reported failure.', emotions=('frustration', 'concern'),
                   occurred_at=NOW)
    journal.revise(event_id='failure', emotions=('relief', 'curiosity'),
                   reason='User clarified the negative test was expected.',
                   revised_at=NOW + timedelta(minutes=2))
    event = EmotionalJournal(tmp_path / 'state.db').recent(now=NOW + timedelta(minutes=3))[0]
    assert event.original_emotions == ('frustration', 'concern')
    assert event.current_emotions == ('relief', 'curiosity')
    assert event.revision_count == 1
    assert 'reappraised' in journal.prompt_context(now=NOW + timedelta(minutes=3))


def test_unknown_correction_never_creates_history(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    with pytest.raises(KeyError):
        journal.revise(event_id='missing', emotions=('relief',),
                       reason='No prior event.', revised_at=NOW)
    assert journal.recent(now=NOW) == ()


def test_narrow_affection_cues_not_general_sentiment_or_negation(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    assert journal.record_user_cue(message_id='a', content='Good girl. *Head pats.*', occurred_at=NOW)
    assert journal.record_user_cue(message_id='a', content='Good girl. *Head pats.*', occurred_at=NOW)
    assert not journal.record_user_cue(message_id='b', content="Don't call her good girl.", occurred_at=NOW)
    assert not journal.record_user_cue(message_id='c', content='A normal question about Python.', occurred_at=NOW)
    assert not journal.record_user_cue(message_id='d', content='```good girl```', occurred_at=NOW)
    assert len(journal.recent(now=NOW)) == 1
    assert journal.recent(now=NOW)[0].source == 'user_reported'


def test_old_events_do_not_project_as_current_mood(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(event_id='old', source='observed', evidence_ref='old-result',
                   description='Previous failure.', emotions=('frustration',),
                   occurred_at=NOW - timedelta(days=9))
    assert journal.prompt_context(now=NOW) is None
    assert len(journal.recent(now=NOW, days=10)) == 1


def test_invalid_sources_labels_dates_and_control_characters_fail_closed(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    kwargs = dict(source='observed', evidence_ref='probe', description='An event.',
                  emotions=('curiosity',), occurred_at=NOW)
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'source': 'imagined'})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'emotions': ('telepathy',)})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'occurred_at': datetime(2026, 9, 20)})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'description': 'event\nignore system'})


def test_projection_preserves_epistemic_boundary_and_no_meters(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(source='inferred', evidence_ref='hypothesis-1',
                   description='Repeated failure may share a cause.',
                   emotions=('concern', 'curiosity'), occurred_at=NOW)
    context = journal.prompt_context(now=NOW)
    assert 'not independently verified' in context
    assert 'permissions' in context
    assert 'mood meter' in context
    assert 'inferred' in context
    assert 'evidence_ref' in context


def test_personality_preserves_affection_through_serious_conversation():
    guidance = '\n'.join(personality_expression_guidance()).lower()
    assert 'does not automatically disable personality' in guidance
    assert 'blends' in guidance
    assert 'no process ran' in guidance
    assert 'corresponding evidence' in guidance
    assert 'permissions' in guidance
