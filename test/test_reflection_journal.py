"""Offline reflection/outbox contracts; no network or synthetic LLM outputs."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from sofia.personality.reflection import ReflectionJournal, _period

UTC = timezone.utc


def _at(year=2026, month=9, day=20, hour=12):
    return datetime(year, month, day, hour, tzinfo=UTC)


def _event(path, *, identifier, when, description, emotions=('curiosity',)):
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS emotional_events (
            event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL,
            source TEXT NOT NULL, evidence_ref TEXT NOT NULL,
            description TEXT NOT NULL, original_emotions TEXT NOT NULL)''')
        db.execute('INSERT INTO emotional_events VALUES (?, ?, ?, ?, ?, ?)',
                   (identifier, when.isoformat(), 'observed', identifier,
                    description, json.dumps(emotions)))


def test_completed_periods_reflect_once_and_survive_restart(tmp_path):
    path = tmp_path / 'state.db'
    store = ReflectionJournal(path)
    _event(path, identifier='e1', when=_at(2026, 8, 31), description='A test failed.', emotions=('frustration',))
    _event(path, identifier='e2', when=_at(2026, 9, 1), description='The fix passed.', emotions=('relief',))
    now = _at(2026, 9, 20)
    ids = store.reflect_due(now=now)
    assert set(ids) == {
        'reflection:daily:2026-08-31', 'reflection:weekly:2026-08-31',
        'reflection:monthly:2026-08-01', 'reflection:daily:2026-09-01',
    }
    assert ReflectionJournal(path).reflect_due(now=now) == ()
    thoughts = ReflectionJournal(path).recent_thoughts()
    assert len(thoughts) == 4
    assert all(t.evidence_refs and t.created_at == now for t in thoughts)
    assert all(t.kind != 'yearly' for t in thoughts)
    assert 'A test failed.' in store.prompt_context()


def test_yearly_and_monthly_boundary_and_utc_calendar(tmp_path):
    path = tmp_path / 'db.sqlite'
    store = ReflectionJournal(path)
    _event(path, identifier='old', when=_at(2025, 12, 31), description='Milestone.')
    assert 'reflection:yearly:2025-01-01' in store.reflect_due(now=_at(2026, 1, 2))
    assert _period(_at(2024, 2, 29), 'monthly')[2] == _at(2024, 3, 1, 0)
    assert _period(_at(2026, 9, 20), 'weekly')[1] == _at(2026, 9, 14, 0)


def test_current_period_not_invented_and_no_empty_periods(tmp_path):
    path = tmp_path / 'db.sqlite'
    store = ReflectionJournal(path)
    assert store.reflect_due(now=_at()) == ()
    _event(path, identifier='today', when=_at(), description='Current event.')
    assert store.reflect_due(now=_at(2026, 9, 20, 13)) == ()
    assert not store.recent_thoughts()
    assert set(store.reflect_due(now=_at(2026, 9, 21))) == {
        'reflection:daily:2026-09-20', 'reflection:weekly:2026-09-14',
    }


def test_grounded_outbox_dedup_spacing_followup_and_delivery(tmp_path):
    path = tmp_path / 'db.sqlite'
    store = ReflectionJournal(path)
    thought = store.record_thought(
        kind='observation', subject='Artemis changes',
        content='A reboot occurred and later another was recorded.',
        evidence_refs=('reboot1', 'reboot2'), emotions=('concern',), created_at=_at(),
    )
    first = store.enqueue(thought_id=thought, evidence_ref='reboot1',
                          content='First reboot observed.', urgency='routine', queued_at=_at())
    assert store.enqueue(thought_id=thought, evidence_ref='reboot1',
                         content='Duplicate request.', urgency='urgent', queued_at=_at()) == first
    with pytest.raises(ValueError, match='spacing'):
        store.enqueue(thought_id=thought, evidence_ref='reboot2', content='New reboot.',
                      urgency='urgent', queued_at=_at(2026, 9, 20, 12) + timedelta(minutes=5),
                      thread_id=thought)
    with pytest.raises(ValueError, match='not linked'):
        store.enqueue(thought_id=thought, evidence_ref='invented', content='Not real.',
                      urgency='urgent', queued_at=_at(2026, 9, 20, 13))
    later = store.enqueue(thought_id=thought, evidence_ref='reboot2',
                          content='Another reboot confirmed.', urgency='urgent',
                          queued_at=_at(2026, 9, 20, 13))
    pending = ReflectionJournal(path).pending()
    assert {e.message_id for e in pending} == {first, later}
    assert pending[-1].urgency == 'urgent'
    store.confirm_delivery(message_id=first, delivered_at=_at(2026, 9, 20, 14))
    assert [e.message_id for e in ReflectionJournal(path).pending()] == [later]
    with pytest.raises(ValueError, match='No pending'):
        store.confirm_delivery(message_id=first, delivered_at=_at(2026, 9, 20, 15))


def test_cannot_forge_period_or_rewrite_thought(tmp_path):
    store = ReflectionJournal(tmp_path / 'state.db')
    with pytest.raises(ValueError, match='require'):
        store.record_thought(kind='daily', subject='Day', content='hi',
                             evidence_refs=('e1',), created_at=_at())
    first = store.record_thought(kind='observation', thought_id='fixed',
                                 subject='First', content='Original',
                                 evidence_refs=('e1',), created_at=_at())
    assert first == 'fixed'
    with pytest.raises(ValueError, match='already in use'):
        store.record_thought(kind='observation', thought_id='fixed',
                             subject='Changed', content='Rewritten',
                             evidence_refs=('e1',), created_at=_at())
    with pytest.raises(ValueError, match='timezone-aware'):
        store.record_thought(kind='observation', subject='bad', content='bad',
                             evidence_refs=('e1',), created_at=datetime(2026, 1, 1))
