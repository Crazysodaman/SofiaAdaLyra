"""Only source-attested explicit revisions enter interaction context."""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.interaction.preference_context import read_interaction_context
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    db = tmp_path / 'state.db'
    with sqlite3.connect(db) as cx:
        cx.execute('''CREATE TABLE conversation_messages
            (id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
             content TEXT, created_at TEXT)''')
        cx.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('reply', 's', 'assistant', 'I like gentle head pats.', NOW.isoformat()))
        cx.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('stop', 's', 'assistant', 'I do not want head pats.', NOW.isoformat()))
    adapter = VerifiedInteractionState(db, InteractionCatalog(('head', 'left-hand', 'right-hand')))
    return db, adapter


def test_empty_reader_never_creates_database(tmp_path):
    path = tmp_path / 'absent.db'
    assert read_interaction_context(path, subject='sofia',
                                    semantic_id='pat', region_id='head').status == 'no_records'
    assert not path.exists()


def test_attested_preference_and_boundary_precedence(state):
    db, adapter = state
    adapter.record_preference(
        revision_id='p1', subject='sofia', semantic_id='pat', region_id='head',
        context='general', direction='enjoy', source_id='reply', session_id='s',
        exact_content='I like gentle head pats.', reviewer_id='review-p1',
        prior_id=None, at=NOW)
    context = read_interaction_context(db, subject='sofia',
                                       semantic_id='pat', region_id='head')
    assert (context.status, context.preference, context.source_id) == (
        'reviewed', 'enjoy', 'reply')
    adapter.record_boundary(
        revision_id='b1', subject='sofia', semantic_id='pat', region_id='head',
        active=True, source_id='stop', session_id='s',
        exact_content='I do not want head pats.', reviewer_id='review-b1',
        prior_id=None, at=NOW)
    context = read_interaction_context(db, subject='sofia',
                                       semantic_id='pat', region_id='head')
    assert context.blocked and context.status == 'boundary' and context.preference is None
    assert not read_interaction_context(db, subject='user',
                                        semantic_id='pat', region_id='head').blocked


def test_unverified_active_boundary_is_not_ignored(state):
    db, adapter = state
    adapter.journal.record_boundary(
        revision_id='unverified', subject='sofia', semantic_id='*', region_id='*',
        active=True, source_id='not-saved', prior_id=None, at=NOW)
    context = read_interaction_context(db, subject='sofia',
                                       semantic_id='pat', region_id='head')
    assert context.blocked and context.status == 'unverified_boundary'


def test_modified_attested_source_is_visible_error(state):
    db, adapter = state
    adapter.record_preference(
        revision_id='p1', subject='sofia', semantic_id='pat', region_id='head',
        context='general', direction='enjoy', source_id='reply', session_id='s',
        exact_content='I like gentle head pats.', reviewer_id='review-p1',
        prior_id=None, at=NOW)
    with sqlite3.connect(db) as cx:
        cx.execute("UPDATE conversation_messages SET content='changed' WHERE id='reply'")
    with pytest.raises(ValueError, match='modified'):
        read_interaction_context(db, subject='sofia',
                                 semantic_id='pat', region_id='head')
