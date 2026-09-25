"""Explicit, source-verified adapter for the interaction revision journal.

This is an application-side commit API, not a free-text preference detector.
A privileged caller must review whether the saved statement actually supports
its proposed revision. A message ID, model output or repeated gesture alone
never grants permission or writes a preference. No code runs at import time.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import sqlite3

from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.temporal import InteractionStateJournal


class VerifiedInteractionState:
    """Explicitly review evidence against the saved conversation before commit."""

    def __init__(self, state_path: str | Path, catalog: InteractionCatalog) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError('An existing conversation state DB is required.')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                          "AND name='conversation_messages'").fetchone() is None:
                raise ValueError('Conversation evidence table is missing.')
        # Only explicit construction creates the separate optional tables.
        self.journal = InteractionStateJournal(self.path, catalog)
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS interact_evidence_attestations (
                source_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                role TEXT NOT NULL, content_digest TEXT NOT NULL,
                source_timestamp TEXT NOT NULL, reviewer_id TEXT NOT NULL
            )''')
            db.commit()

    @staticmethod
    def _required(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f'{label} must be a bounded nonempty value.')
        return value

    def _attest(self, *, source_id: str, session_id: str, subject: str,
                exact_content: str, reviewer_id: str) -> None:
        """Check source ID, correct role/session and unchanged exact content.

        reviewer_id is an audit reference provided by a trusted caller; this
        module does not authenticate it or parse natural-language meaning.
        """
        self._required(source_id, 'source_id')
        self._required(session_id, 'session_id')
        self._required(reviewer_id, 'reviewer_id')
        if not isinstance(exact_content, str) or not exact_content.strip():
            raise ValueError('An exact reviewed statement is required.')
        if subject not in ('user', 'sofia'):
            raise ValueError('Unknown subject.')
        expected_role = 'user' if subject == 'user' else 'assistant'
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT session_id, role, content, created_at
                FROM conversation_messages WHERE id=?''', (source_id,)).fetchone()
            if row is None or row[:3] != (session_id, expected_role, exact_content):
                raise ValueError('Source is absent, wrong role/session or changed.')
            try:
                timestamp = datetime.fromisoformat(row[3])
            except (TypeError, ValueError) as exc:
                raise ValueError('Source has an invalid timestamp.') from exc
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError('Source timestamp must include a timezone.')
            attestation = (source_id, session_id, expected_role,
                           sha256(exact_content.encode('utf-8')).hexdigest(),
                           row[3], reviewer_id)
            existing = db.execute('''SELECT source_id, session_id, role,
                content_digest, source_timestamp, reviewer_id
                FROM interact_evidence_attestations WHERE source_id=?''',
                (source_id,)).fetchone()
            if existing is not None and existing != attestation:
                raise ValueError('Previously attested evidence was modified.')
            if existing is None:
                db.execute('INSERT INTO interact_evidence_attestations VALUES (?,?,?,?,?,?)',
                           attestation)
            db.commit()

    def assert_source_unchanged(self, source_id: str) -> None:
        """Detect mutable legacy conversation rows after an attestation."""
        self._required(source_id, 'source_id')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            row = db.execute('''SELECT a.session_id, a.role, a.content_digest,
                a.source_timestamp, m.session_id, m.role, m.content, m.created_at
                FROM interact_evidence_attestations a LEFT JOIN conversation_messages m
                ON a.source_id=m.id WHERE a.source_id=?''', (source_id,)).fetchone()
        if row is None or row[4] is None or row[:2] != row[4:6] or row[3] != row[7]:
            raise ValueError('Attested conversation source is missing or changed.')
        if sha256(row[6].encode('utf-8')).hexdigest() != row[2]:
            raise ValueError('Attested conversation content was modified.')

    def record_preference(self, *, revision_id: str, subject: str,
                          semantic_id: str, region_id: str, context: str,
                          direction: str, source_id: str, session_id: str,
                          exact_content: str, reviewer_id: str,
                          prior_id: str | None, at: datetime):
        self._attest(source_id=source_id, session_id=session_id, subject=subject,
                     exact_content=exact_content, reviewer_id=reviewer_id)
        return self.journal.record_preference(
            revision_id=revision_id, subject=subject, semantic_id=semantic_id,
            region_id=region_id, context=context, direction=direction,
            origin=f'{subject}_explicit', source_id=source_id,
            prior_id=prior_id, at=at)

    def record_boundary(self, *, revision_id: str, subject: str,
                        semantic_id: str, region_id: str, active: bool,
                        source_id: str, session_id: str, exact_content: str,
                        reviewer_id: str, prior_id: str | None, at: datetime):
        self._attest(source_id=source_id, session_id=session_id, subject=subject,
                     exact_content=exact_content, reviewer_id=reviewer_id)
        return self.journal.record_boundary(
            revision_id=revision_id, subject=subject, semantic_id=semantic_id,
            region_id=region_id, active=active, source_id=source_id,
            prior_id=prior_id, at=at)
