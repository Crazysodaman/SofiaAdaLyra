"""Disposable-state tests for final transactional guarded-offer persistence."""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.interaction.trusted_offer_gate import GuardedOfferResult

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
SESSION = 'session1'
OFFER = 'I ask to hug you'


@pytest.fixture
def state(tmp_path):
    path = tmp_path / 'isolated.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE conversation_sessions (id TEXT PRIMARY KEY, '
                   'created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
        db.execute('CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, '
                   'session_id TEXT NOT NULL, role TEXT NOT NULL, '
                   'content TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('INSERT INTO conversation_sessions VALUES (?,?,?)',
                   (SESSION, NOW.isoformat(), NOW.isoformat()))
        db.executemany('INSERT INTO conversation_messages VALUES (?,?,?,?,?)', (
            ('offer1', SESSION, 'user', OFFER, NOW.isoformat()),
            ('stop-source', SESSION, 'assistant', 'I do not want hugs in this avatar scene.',
             '2026-09-21T00:00:00+00:00'),
            ('revoke-source', SESSION, 'assistant', 'I am lifting my no-hugs boundary.',
             '2026-09-21T00:01:00+00:00'),
        ))
    InteractionLedger(path)
    adapter = VerifiedInteractionState(path, InteractionCatalog(('head', 'left-hand')))
    return path, adapter


def _commit(path, result=None, *, message_id='offer1', content=OFFER):
    if result is None:
        result = GuardedOfferResult(status='responded', response='A natural model reply.')
    return commit_guarded_offer_reply(
        state_path=path, session_id=SESSION, user_message_id=message_id,
        user_content=content, result=result,
    )


def _messages(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT content FROM conversation_messages WHERE role='assistant' "
                          "AND content NOT LIKE 'I do not want%' "
                          "AND content NOT LIKE 'I am lifting%' ORDER BY created_at").fetchall()


def _boundary(adapter, *, active=True, rev='b1', prior=None):
    adapter.record_boundary(
        revision_id=rev, subject='sofia', semantic_id='hug', region_id='*',
        active=active, source_id='stop-source' if active else 'revoke-source',
        session_id=SESSION,
        exact_content=('I do not want hugs in this avatar scene.' if active
                       else 'I am lifting my no-hugs boundary.'),
        reviewer_id='test-reviewer', prior_id=prior, at=NOW,
    )


def test_clear_policy_persists_exact_candidate_and_updates_session(state):
    path, _ = state
    assert _commit(path) == 'A natural model reply.'
    assert _messages(path) == [('A natural model reply.',)]
    with sqlite3.connect(path) as db:
        updated = db.execute('SELECT updated_at FROM conversation_sessions '
                             'WHERE id=?', (SESSION,)).fetchone()[0]
    assert datetime.fromisoformat(updated) >= NOW


def test_new_attested_boundary_overrides_inflight_model_reply(state):
    path, adapter = state
    _boundary(adapter)
    released = _commit(path)
    assert 'recorded interaction boundary' in released
    assert 'A natural model reply.' not in str(_messages(path))
    assert _messages(path) == [(released,)]


def test_unverified_boundary_cannot_release_model_reply(state):
    path, adapter = state
    adapter.journal.record_boundary(
        revision_id='b1', subject='sofia', semantic_id='hug',
        region_id='*', active=True, source_id='missing', prior_id=None, at=NOW,
    )
    released = _commit(path)
    assert 'cannot verify' in released
    assert 'A natural model reply.' not in str(_messages(path))


def test_stopped_session_overrides_model_reply(state):
    path, _ = state
    InteractionLedger(path).control(
        session_id=SESSION, message_id='stop1',
        content='Sofía, stop interactions', occurred_at=NOW,
    )
    released = _commit(path)
    assert 'paused' in released
    assert _messages(path) == [(released,)]


def test_verified_revocation_does_not_force_acceptance(state):
    path, adapter = state
    _boundary(adapter)
    _boundary(adapter, active=False, rev='b2', prior='b1')
    decline = GuardedOfferResult(status='responded', response='No hugs for me today.')
    assert _commit(path, decline) == 'No hugs for me today.'


def test_missing_or_changed_user_message_fails_without_assistant_write(state):
    path, _ = state
    with pytest.raises(ValueError, match='missing or modified'):
        _commit(path, message_id='fake')
    with pytest.raises(ValueError, match='missing or modified'):
        _commit(path, content='changed')
    assert _messages(path) == []


def test_later_saved_user_turn_supersedes_candidate(state):
    path, _ = state
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('later', SESSION, 'user', 'New question',
                    '2026-09-23T00:00:00+00:00'))
    with pytest.raises(ValueError, match='later user turn'):
        _commit(path)
    assert _messages(path) == []


def test_attested_source_tamper_rolls_back(state):
    path, adapter = state
    _boundary(adapter)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE conversation_messages SET content='corrupt' "
                   "WHERE id='stop-source'")
    with pytest.raises(ValueError, match='modified'):
        _commit(path)
    assert _messages(path) == []


def test_failed_schema_rolls_back_and_does_not_recreate_tables(state):
    path, _ = state
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE interact_boundary_revisions')
    with pytest.raises(ValueError, match='schema missing'):
        _commit(path)
    assert _messages(path) == []


def test_malformed_guarded_result_fails_before_persistence(state):
    path, _ = state
    with pytest.raises(ValueError, match='empty candidate'):
        _commit(path, GuardedOfferResult(status='responded'))
    with pytest.raises(ValueError, match='Unknown guarded'):
        _commit(path, GuardedOfferResult(status='unexpected'))
    assert _messages(path) == []
