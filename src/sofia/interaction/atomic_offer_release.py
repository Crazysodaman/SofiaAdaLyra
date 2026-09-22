"""Atomic, application-owned persistence for a guarded avatar-offer reply.

The user message must already be saved by the trusted conversation host. A
BEGIN IMMEDIATE transaction serializes policy changes with reply persistence
in the same SQLite file. This never executes a gesture or grants permission.
Only use with the currently isolated exact-offer route and an authenticated
session. Do not invoke it directly with model-provided message identifiers.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.decision_expression import CandidateChoice
from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$')
_BLOCKED_REPLIES = {
    'blocked-boundary': (
        'That represented offer conflicts with a recorded interaction boundary, '
        'so I have not treated it as completed. We can keep talking.'
    ),
    'blocked-unverified-boundary': (
        'I cannot verify the interaction boundary right now, so I have not '
        'accepted or carried out that represented offer.'
    ),
    'blocked-stop': (
        'Represented body interactions are paused, so I have not accepted '
        'or carried out that offer.'
    ),
}


def commit_guarded_offer_reply(*, state_path: str | Path, session_id: str,
                               user_message_id: str, user_content: str,
                               result: GuardedOfferResult) -> str:
    """Recheck policy under a write lock and save exactly one assistant reply.

    The saved USER record is independently matched by ID, session, role and
    exact text. A newly activated boundary or stop overrides an in-flight
    model reply. An unverifiable source or schema failure raises and rolls
    back rather than delivering candidate text. No auto-consent is recorded.
    """
    if (not isinstance(user_message_id, str) or _ID.fullmatch(user_message_id) is None
            or not isinstance(session_id, str) or _ID.fullmatch(session_id) is None
            or user_content != OFFER or not isinstance(result, GuardedOfferResult)):
        raise ValueError('Exact saved offer and canonical host identifiers are required.')
    if result.status not in ('responded', *_BLOCKED_REPLIES):
        raise ValueError('Unknown guarded offer status.')
    if result.status == 'responded' and (
        not isinstance(result.choice, CandidateChoice)
        or result.choice.choice not in ('accept', 'decline', 'clarify', 'boundary')
        or not isinstance(result.response, str) or not result.response.strip()
    ):
        raise ValueError('Cannot persist an unvalidated or empty candidate reply.')
    if result.status != 'responded' and (result.choice is not None or result.response is not None):
        raise ValueError('A blocked offer cannot carry model-generated output.')
    path = Path(state_path)
    if not path.is_file():
        raise FileNotFoundError('Existing state database required for atomic reply.')
    with closing(sqlite3.connect(path, timeout=5)) as db:
        db.execute('PRAGMA busy_timeout=5000')
        with db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute(
                'SELECT session_id, role, content FROM conversation_messages WHERE id=?',
                (user_message_id,),
            ).fetchone()
            if row != (session_id, 'user', user_content):
                raise ValueError('Saved user evidence was missing or modified.')
            current = db.execute(
                "SELECT id FROM conversation_messages WHERE session_id=? AND role='user' "
                'ORDER BY created_at DESC, id DESC LIMIT 1', (session_id,),
            ).fetchone()
            if current != (user_message_id,):
                raise ValueError('A later user turn superseded this offer.')
            if db.execute('SELECT 1 FROM conversation_sessions WHERE id=?',
                          (session_id,)).fetchone() is None:
                raise ValueError('Saved conversation session is missing.')
            blocked = _policy_gate(state_path=path, session_id=session_id)
            status = blocked or result.status
            content = _BLOCKED_REPLIES.get(status, result.response)
            if not isinstance(content, str) or not content.strip():
                raise ValueError('No releasable assistant response.')
            now = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO conversation_messages '
                       '(id, session_id, role, content, created_at) '
                       'VALUES (?, ?, ?, ?, ?)',
                       (str(uuid4()), session_id, 'assistant', content, now))
            db.execute('UPDATE conversation_sessions SET updated_at=? '
                       'WHERE id=? AND updated_at<?', (now, session_id, now))
        return content
