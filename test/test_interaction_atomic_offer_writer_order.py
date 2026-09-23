"""Disposable SQLite cross-connection write-order regression for social replies."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from threading import Event
import sqlite3

from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply
from sofia.interaction.decision_expression import CandidateChoice
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.reviewed_hug_question import CLARIFICATION
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.interaction.trusted_offer_gate import GuardedOfferResult


def test_committed_stop_from_other_connection_blocks_inflight_question(tmp_path):
    """A writer holding BEGIN IMMEDIATE commits a stop before reply's lock.

    This tests one deterministic ordering, not every scheduler interleaving or
    a guarantee against changes made after a reply has committed.
    """
    path = tmp_path / 'writer-order-only.db'
    timestamp = datetime.now(timezone.utc).isoformat()
    question = 'Could I hug you?'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE conversation_sessions (id TEXT PRIMARY KEY, '
                   'created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
        db.execute('CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, '
                   'session_id TEXT NOT NULL, role TEXT NOT NULL, '
                   'content TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('INSERT INTO conversation_sessions VALUES (?,?,?)', ('s1', timestamp, timestamp))
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('q1', 's1', 'user', question, timestamp))
    InteractionLedger(path)
    VerifiedInteractionState(path, InteractionCatalog(('head', 'left-hand')))
    attempted = Event()

    def release():
        attempted.set()
        return commit_guarded_offer_reply(
            state_path=path, session_id='s1', user_message_id='q1',
            user_content=question,
            result=GuardedOfferResult(
                status='responded', choice=CandidateChoice('clarify', 'test only'),
                response=CLARIFICATION,
            ),
        )

    with closing(sqlite3.connect(path, timeout=5)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(release)
            assert attempted.wait(timeout=3)
            # The future cannot finish its own BEGIN IMMEDIATE while this
            # independent writer holds SQLite's write reservation.
            assert not future.done()
            writer.execute('INSERT INTO interaction_session_controls '
                           '(session_id, stopped) VALUES (?, ?) '
                           'ON CONFLICT(session_id) DO UPDATE SET stopped=excluded.stopped',
                           ('s1', 1))
            writer.commit()
            response = future.result(timeout=5)
    assert 'paused' in response
    assert response != CLARIFICATION
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT content FROM conversation_messages "
                          "WHERE role='assistant'").fetchall()
    assert rows == [(response,)]
