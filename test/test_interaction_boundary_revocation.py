"""An unverified clear operation cannot silently bypass an active boundary."""
from datetime import datetime, timezone
import sqlite3

from sofia.interaction.preference_context import read_interaction_context
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_unverified_revocation_cannot_clear_reviewed_stop(tmp_path):
    path = tmp_path / 'isolated.db'
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE conversation_messages (id TEXT PRIMARY KEY,
            session_id TEXT, role TEXT, content TEXT, created_at TEXT)''')
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('no', 's1', 'assistant', 'Please do not pat my head.', NOW.isoformat()))
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('yes', 's1', 'assistant', 'I am okay with new head pats.', NOW.isoformat()))
    attested = VerifiedInteractionState(path, InteractionCatalog(('head',)))
    base = dict(subject='sofia', semantic_id='pat', region_id='head')
    attested.record_boundary(
        revision_id='b1', active=True, source_id='no', session_id='s1',
        exact_content='Please do not pat my head.', reviewer_id='review-no',
        prior_id=None, at=NOW, **base)
    assert read_interaction_context(path, **base).blocked
    attested.journal.record_boundary(
        revision_id='b2', active=False, source_id='invented',
        prior_id='b1', at=NOW, **base)
    context = read_interaction_context(path, **base)
    assert context.blocked and context.status == 'unverified_boundary'
    attested.record_boundary(
        revision_id='b3', active=False, source_id='yes', session_id='s1',
        exact_content='I am okay with new head pats.', reviewer_id='review-yes',
        prior_id='b2', at=NOW, **base)
    assert not read_interaction_context(path, **base).blocked
