"""Opt-in, append-only *modeled* preferences and explicit boundaries.

Not integrated into live interaction. Construct only with an authorized DB path;
never use the user's production state in tests. A gesture never writes a preference.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from sofia.interaction.registry import (
    ACTION_DEFINITIONS, GESTURE_DEFINITIONS, InteractionCatalog,
)

DIRECTIONS = frozenset({'enjoy', 'dislike', 'mixed', 'neutral', 'unknown'})
PARTICIPANTS = frozenset({'user', 'sofia'})


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError(f'{label} must be a nonempty ID of at most 160 characters.')
    return value


def _time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Source timestamp must be timezone-aware.')
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class PreferenceRevision:
    id: str
    subject: str
    semantic_id: str
    region_id: str
    context: str
    direction: str
    origin: str
    source_id: str
    prior_id: str | None
    recorded_at: str


@dataclass(frozen=True)
class BoundaryRevision:
    id: str
    subject: str
    semantic_id: str
    region_id: str
    active: bool
    source_id: str
    prior_id: str | None
    recorded_at: str


class InteractionStateJournal:
    """Explicit write API; no model calls, timers, background work, or permission grant."""

    def __init__(self, path: str | Path, catalog: InteractionCatalog) -> None:
        if not isinstance(catalog, InteractionCatalog):
            raise TypeError('A validated interaction catalog is required.')
        self.path = Path(path)
        self.catalog = catalog
        self._semantic_ids = frozenset(
            definition.id for definition in (*GESTURE_DEFINITIONS, *ACTION_DEFINITIONS)
        )
        with self._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS interact_preference_revisions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL, subject TEXT NOT NULL,
                    semantic_id TEXT NOT NULL, region_id TEXT NOT NULL,
                    context TEXT NOT NULL, direction TEXT NOT NULL,
                    origin TEXT NOT NULL, source_id TEXT NOT NULL,
                    prior_id TEXT, recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interact_boundary_revisions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL, subject TEXT NOT NULL,
                    semantic_id TEXT NOT NULL, region_id TEXT NOT NULL,
                    active INTEGER NOT NULL, source_id TEXT NOT NULL,
                    prior_id TEXT, recorded_at TEXT NOT NULL
                );
            ''')

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def _scope(self, subject: str, semantic_id: str, region_id: str) -> None:
        if subject not in PARTICIPANTS:
            raise ValueError('Unknown subject.')
        if semantic_id != '*' and semantic_id not in self._semantic_ids:
            raise ValueError('Unknown gesture/action ID.')
        if region_id != '*' and region_id not in self.catalog.region_ids:
            raise ValueError('Unknown canonical region ID.')

    @staticmethod
    def _latest(db: sqlite3.Connection, table: str, fields: tuple[str, ...],
                values: tuple[str, ...]) -> tuple | None:
        if table not in ('interact_preference_revisions', 'interact_boundary_revisions'):
            raise ValueError('Invalid revision table.')
        where = ' AND '.join(f'{field}=?' for field in fields)
        return db.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY seq DESC LIMIT 1', values).fetchone()

    @staticmethod
    def _append(db: sqlite3.Connection, table: str, columns: tuple[str, ...],
                values: tuple, key: tuple[str, ...], prior_id: str | None) -> None:
        existing = db.execute(f'SELECT {", ".join(columns)} FROM {table} WHERE id=?', (values[0],)).fetchone()
        if existing is not None:
            if existing == values:
                return  # Same evidence/revision ID is a true idempotent replay.
            raise ValueError('Revision ID was reused with different evidence.')
        latest = InteractionStateJournal._latest(db, table, columns[1:1 + len(key)], key)
        actual_prior = latest[1] if latest else None  # seq is the first column.
        if prior_id != actual_prior:
            raise ValueError('Stale or missing prior revision; reload before writing.')
        placeholders = ', '.join('?' for _ in columns)
        db.execute(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})', values)

    def record_preference(self, *, revision_id: str, subject: str, semantic_id: str,
                          region_id: str, context: str, direction: str, origin: str,
                          source_id: str, prior_id: str | None, at: datetime) -> PreferenceRevision:
        """Commit an explicitly sourced statement, not a gesture-derived inference."""
        self._scope(subject, semantic_id, region_id)
        if direction not in DIRECTIONS or origin != f'{subject}_explicit':
            raise ValueError('Preference requires a valid direction and explicit subject statement.')
        if not isinstance(context, str) or not context.strip() or len(context) > 80:
            raise ValueError('A bounded context is required.')
        record = PreferenceRevision(_id(revision_id, 'Revision'), subject, semantic_id,
                                    region_id, context.strip(), direction, origin,
                                    _id(source_id, 'Source'), prior_id, _time(at))
        columns = tuple(PreferenceRevision.__dataclass_fields__)
        values = tuple(getattr(record, column) for column in columns)
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._append(db, 'interact_preference_revisions', columns, values,
                         (subject, semantic_id, region_id, record.context), prior_id)
        return record

    def preference(self, *, subject: str, semantic_id: str, region_id: str,
                   context: str) -> PreferenceRevision | None:
        self._scope(subject, semantic_id, region_id)
        with self._connection() as db:
            row = self._latest(db, 'interact_preference_revisions',
                               ('subject', 'semantic_id', 'region_id', 'context'),
                               (subject, semantic_id, region_id, context))
        return PreferenceRevision(*row[1:]) if row else None

    def preference_history(self, *, subject: str, semantic_id: str, region_id: str,
                           context: str) -> tuple[PreferenceRevision, ...]:
        self._scope(subject, semantic_id, region_id)
        with self._connection() as db:
            rows = db.execute('''SELECT id, subject, semantic_id, region_id, context,
                direction, origin, source_id, prior_id, recorded_at
                FROM interact_preference_revisions WHERE subject=? AND semantic_id=?
                AND region_id=? AND context=? ORDER BY seq''',
                (subject, semantic_id, region_id, context)).fetchall()
        return tuple(PreferenceRevision(*row) for row in rows)

    def record_boundary(self, *, revision_id: str, subject: str, semantic_id: str,
                        region_id: str, active: bool, source_id: str,
                        prior_id: str | None, at: datetime) -> BoundaryRevision:
        self._scope(subject, semantic_id, region_id)
        if not isinstance(active, bool):
            raise ValueError('Boundary state must be explicitly boolean.')
        record = BoundaryRevision(_id(revision_id, 'Revision'), subject, semantic_id,
                                  region_id, active, _id(source_id, 'Source'),
                                  prior_id, _time(at))
        columns = tuple(BoundaryRevision.__dataclass_fields__)
        values = tuple(getattr(record, column) for column in columns)
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._append(db, 'interact_boundary_revisions', columns, values,
                         (subject, semantic_id, region_id), prior_id)
        return record

    def boundary_active(self, *, subject: str, semantic_id: str, region_id: str) -> bool:
        """Look up narrow and wildcard explicit restrictions. Never grants consent."""
        self._scope(subject, semantic_id, region_id)
        with self._connection() as db:
            for semantic in ('*', semantic_id):
                for region in ('*', region_id):
                    row = self._latest(db, 'interact_boundary_revisions',
                                       ('subject', 'semantic_id', 'region_id'),
                                       (subject, semantic, region))
                    if row and bool(row[5]):  # seq, id, subject, semantic, region, active
                        return True
        return False
