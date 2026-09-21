"""Read-only, source-checked modeled preference and boundary projection.

Only explicitly reviewed source attestations qualify as trusted preference
context. Unverified boundary additions OR removals fail closed. This read
path does not initialize a schema or write production state.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class InteractionContext:
    subject: str
    semantic_id: str
    region_id: str
    blocked: bool
    preference: str | None
    source_id: str | None
    status: str  # no_records, reviewed, boundary, unverified_boundary


def _table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                      (name,)).fetchone() is not None


def _attested(db: sqlite3.Connection, source_id: str) -> bool:
    if not _table(db, 'interact_evidence_attestations'):
        return False
    row = db.execute('''SELECT a.session_id, a.role, a.content_digest,
        a.source_timestamp, m.session_id, m.role, m.content, m.created_at
        FROM interact_evidence_attestations a LEFT JOIN conversation_messages m
        ON a.source_id=m.id WHERE a.source_id=?''', (source_id,)).fetchone()
    if row is None:
        return False
    if row[4] is None or row[:2] != row[4:6] or row[3] != row[7]:
        raise ValueError('An attested interaction source is missing or changed.')
    if sha256(row[6].encode('utf-8')).hexdigest() != row[2]:
        raise ValueError('An attested interaction source was modified.')
    return True


def read_interaction_context(path: str | Path, *, subject: str,
                             semantic_id: str, region_id: str,
                             context: str = 'general') -> InteractionContext:
    """Read scoped records without opening a writer or inferring consent.

    Caller supplies already-vetted canonical IDs. This function cannot prove
    that the caller's actor, target, message, or permissions were authenticated.
    """
    if subject not in ('user', 'sofia'):
        raise ValueError('Unknown interaction subject.')
    for label, value in (('semantic', semantic_id), ('region', region_id),
                         ('context', context)):
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            raise ValueError(f'{label} requires a bounded canonical ID.')
    state = Path(path)
    empty = InteractionContext(subject, semantic_id, region_id, False,
                               None, None, 'no_records')
    if not state.is_file():
        return empty
    with closing(sqlite3.connect(state, timeout=5)) as db:
        if not _table(db, 'conversation_messages'):
            return empty
        if _table(db, 'interact_boundary_revisions'):
            for semantic in ('*', semantic_id):
                for region in ('*', region_id):
                    row = db.execute('''SELECT active, source_id
                        FROM interact_boundary_revisions
                        WHERE subject=? AND semantic_id=? AND region_id=?
                        ORDER BY seq DESC LIMIT 1''',
                        (subject, semantic, region)).fetchone()
                    if row is None:
                        continue
                    # A fabricated or corrupted deactivation must not erase an
                    # earlier boundary: both activation and revocation need
                    # independently reviewed original-message evidence.
                    verified = _attested(db, row[1])
                    if not verified:
                        return InteractionContext(subject, semantic_id, region_id,
                                                  True, None, None, 'unverified_boundary')
                    if bool(row[0]):
                        return InteractionContext(subject, semantic_id, region_id,
                                                  True, None, row[1], 'boundary')
        if _table(db, 'interact_preference_revisions'):
            for ctx in (context, 'general') if context != 'general' else ('general',):
                for semantic, region in ((semantic_id, region_id), (semantic_id, '*'),
                                         ('*', region_id), ('*', '*')):
                    row = db.execute('''SELECT direction, source_id
                        FROM interact_preference_revisions
                        WHERE subject=? AND semantic_id=? AND region_id=?
                        AND context=? ORDER BY seq DESC LIMIT 1''',
                        (subject, semantic, region, ctx)).fetchone()
                    if row is not None and _attested(db, row[1]):
                        return InteractionContext(subject, semantic_id, region_id,
                                                  False, row[0], row[1], 'reviewed')
    return empty
