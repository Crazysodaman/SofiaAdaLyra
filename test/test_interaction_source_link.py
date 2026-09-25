"""Saved-message attestations use isolated SQLite, never production state."""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


@pytest.fixture
def linked(tmp_path):
    db = tmp_path / 'conversation.db'
    with sqlite3.connect(db) as cx:
        cx.execute('''CREATE TABLE conversation_messages
            (id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
             content TEXT, created_at TEXT)''')
        cx.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('msg-1', 'session-1', 'user', 'I dislike head pats.', NOW.isoformat()))
        cx.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('msg-2', 'session-1', 'assistant',
                    'I would rather not be patted.', NOW.isoformat()))
    return VerifiedInteractionState(db, InteractionCatalog(('head', 'left-hand', 'right-hand')))


def test_saved_source_required_and_later_mutation_detected(linked):
    linked.record_preference(
        revision_id='rev-1', subject='user', semantic_id='pat', region_id='head',
        context='general', direction='dislike', source_id='msg-1',
        session_id='session-1', exact_content='I dislike head pats.',
        reviewer_id='review-1', prior_id=None, at=NOW)
    linked.assert_source_unchanged('msg-1')
    with sqlite3.connect(linked.path) as cx:
        cx.execute("UPDATE conversation_messages SET content='changed' WHERE id='msg-1'")
    with pytest.raises(ValueError, match='modified'):
        linked.assert_source_unchanged('msg-1')


def test_wrong_role_or_session_does_not_create_preference(linked):
    with pytest.raises(ValueError):
        linked.record_preference(
            revision_id='bad', subject='sofia', semantic_id='pat', region_id='head',
            context='general', direction='enjoy', source_id='msg-1',
            session_id='session-1', exact_content='I dislike head pats.',
            reviewer_id='review-1', prior_id=None, at=NOW)
    assert linked.journal.preference(
        subject='sofia', semantic_id='pat', region_id='head', context='general') is None
    with pytest.raises(ValueError):
        linked.record_boundary(
            revision_id='bad-boundary', subject='sofia', semantic_id='pat',
            region_id='head', active=True, source_id='msg-2',
            session_id='wrong-session', exact_content='I would rather not be patted.',
            reviewer_id='review-2', prior_id=None, at=NOW)


def test_boundaries_are_scoped_by_subject(linked):
    linked.record_boundary(
        revision_id='b1', subject='sofia', semantic_id='pat', region_id='head',
        active=True, source_id='msg-2', session_id='session-1',
        exact_content='I would rather not be patted.',
        reviewer_id='review-2', prior_id=None, at=NOW)
    assert linked.journal.boundary_active(
        subject='sofia', semantic_id='pat', region_id='head')
    assert not linked.journal.boundary_active(
        subject='user', semantic_id='pat', region_id='head')
