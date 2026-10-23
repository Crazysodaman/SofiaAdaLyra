"""Durable, compare-and-swap revision store for beliefs and convictions."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid

from sofia.core.beliefs.model import (
    BeliefChangeKind,
    BeliefConcurrencyError,
    BeliefHolder,
    BeliefMatch,
    BeliefRecord,
    BeliefStance,
    BeliefVisibility,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_TOKEN = re.compile(r"[a-z0-9]{3,}")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("belief timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def tokenize_for_belief_relevance(text: str) -> frozenset[str]:
    """Deterministic lowercase tokens used only for relevance scoring."""
    if not isinstance(text, str):
        raise TypeError("textual relevance requires text input")
    return frozenset(_TOKEN.findall(text.casefold()))


@dataclass(frozen=True, slots=True)
class BeliefReconsideration:
    conviction_id: str
    audience_id: str
    due_at: datetime
    note: str


class ConvictionStore:
    """Canonical writer for one `sofia.db`-resident belief revision log.

    The store never interprets content and never resolves authority: it
    appends attested revisions for an explicit holder and topic under one
    audience, with compare-and-swap revision protection.
    """

    def __init__(self, state_path: Path | str) -> None:
        self._guard = CanonicalSQLiteGuard(state_path)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS belief_conviction_revision (
                    conviction_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    holder TEXT NOT NULL
                        CHECK(holder IN ('sofia','owner')),
                    topic TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    stance TEXT NOT NULL
                        CHECK(stance IN
                            ('support','oppose','uncertain','withdrawn')),
                    confidence REAL NOT NULL
                        CHECK(confidence >= 0 AND confidence <= 1),
                    reason TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    counterevidence_refs TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    visibility TEXT NOT NULL
                        CHECK(visibility IN
                            ('owner_audience_only','disclosure_scoped')),
                    change_kind TEXT NOT NULL
                        CHECK(change_kind IN
                            ('origin','restate','revise',
                             'reconsider','retract')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(conviction_id, revision)
                );
                CREATE TABLE IF NOT EXISTS belief_conviction_current (
                    conviction_id TEXT NOT NULL PRIMARY KEY,
                    holder TEXT NOT NULL
                        CHECK(holder IN ('sofia','owner')),
                    topic TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS belief_conviction_current_topic
                    ON belief_conviction_current(holder, topic, audience_id);
                CREATE TABLE IF NOT EXISTS belief_reconsideration (
                    conviction_id TEXT NOT NULL PRIMARY KEY,
                    audience_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    note TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: BeliefRecord) -> tuple:
        return (
            record.conviction_id,
            record.revision,
            record.holder.value,
            record.topic,
            record.statement,
            record.stance.value,
            record.confidence,
            record.reason,
            json.dumps(list(record.evidence_refs)),
            json.dumps(list(record.counterevidence_refs)),
            record.audience_id,
            record.visibility.value,
            record.change_kind.value,
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> BeliefRecord:
        return BeliefRecord(
            conviction_id=row["conviction_id"],
            revision=int(row["revision"]),
            holder=BeliefHolder(row["holder"]),
            topic=row["topic"],
            statement=row["statement"],
            stance=BeliefStance(row["stance"]),
            confidence=float(row["confidence"]),
            reason=row["reason"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            counterevidence_refs=tuple(json.loads(row["counterevidence_refs"])),
            audience_id=row["audience_id"],
            visibility=BeliefVisibility(row["visibility"]),
            change_kind=BeliefChangeKind(row["change_kind"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self,
        *,
        holder: BeliefHolder,
        topic: str,
        statement: str,
        stance: BeliefStance,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        counterevidence_refs: tuple[str, ...] = (),
        audience_id: str,
        visibility: BeliefVisibility,
        expected_revision: int | None,
        change_kind: BeliefChangeKind,
        now: datetime,
        conviction_id: str | None = None,
    ) -> BeliefRecord:
        created = now if now.tzinfo is not None else None
        if created is None:
            raise ValueError("belief timestamps must be timezone-aware")
        created = _utc(created)
        if expected_revision is None and change_kind is not (
            BeliefChangeKind.ORIGIN
        ):
            raise ValueError(
                "creating a conviction requires the origin change kind"
            )
        if isinstance(expected_revision, int) and (
            expected_revision < 1
        ):
            raise ValueError("expected_revision must be absent or positive")
        revision = 1 if expected_revision is None else expected_revision + 1
        candidate_id = conviction_id
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if expected_revision is None:
                row = db.execute(
                    """
                    SELECT conviction_id, revision
                    FROM belief_conviction_current
                    WHERE holder=? AND topic=? AND audience_id=?
                    """,
                    (holder.value, topic, audience_id),
                ).fetchone()
                if row is not None:
                    raise BeliefConcurrencyError(
                        "conviction already exists; reload and revise with "
                        f"expected_revision={int(row['revision'])}"
                    )
                candidate_id = f"conviction:{uuid.uuid4()}"
            else:
                row = db.execute(
                    """
                    SELECT c.conviction_id, c.revision, c.holder, c.topic,
                           c.audience_id
                    FROM belief_conviction_current c
                    WHERE c.holder=? AND c.topic=? AND c.audience_id=?
                    """,
                    (holder.value, topic, audience_id),
                ).fetchone()
                if row is None:
                    raise BeliefConcurrencyError(
                        "revision changed or conviction is absent; "
                        "reload before revising"
                    )
                current_id = row["conviction_id"]
                if conviction_id is not None and current_id != conviction_id:
                    raise BeliefConcurrencyError(
                        "conviction identity changed; reload before revising"
                    )
                if int(row["revision"]) != expected_revision:
                    raise BeliefConcurrencyError(
                        f"revision changed; expected {expected_revision} "
                        f"but current is {int(row['revision'])}"
                    )
                if row["holder"] != holder.value or row["audience_id"] != (
                    audience_id
                ):
                    raise BeliefConcurrencyError(
                        "natural key changed; use a distinct audience/topic"
                    )
                candidate_id = current_id
            record = BeliefRecord(
                conviction_id=candidate_id,
                revision=revision,
                holder=holder,
                topic=topic,
                statement=statement,
                stance=stance,
                confidence=confidence,
                reason=reason,
                evidence_refs=evidence_refs,
                counterevidence_refs=counterevidence_refs,
                audience_id=audience_id,
                visibility=visibility,
                change_kind=change_kind,
                recorded_at=created,
            )
            db.execute(
                """
                INSERT INTO belief_conviction_revision VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                self._encode(record),
            )
            db.execute(
                """
                INSERT INTO belief_conviction_current
                (conviction_id,holder,topic,audience_id,revision)
                VALUES (?,?,?,?,?)
                ON CONFLICT(conviction_id) DO UPDATE SET
                    holder=excluded.holder,
                    topic=excluded.topic,
                    audience_id=excluded.audience_id,
                    revision=excluded.revision
                """,
                (
                    record.conviction_id,
                    record.holder.value,
                    record.topic,
                    record.audience_id,
                    record.revision,
                ),
            )
        return record

    def current(
        self,
        *,
        holder: BeliefHolder,
        topic: str,
        audience_id: str,
    ) -> BeliefRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT r.* FROM belief_conviction_revision r
                JOIN belief_conviction_current c
                  ON c.conviction_id=r.conviction_id
                 AND c.revision=r.revision
                WHERE c.holder=? AND c.topic=? AND c.audience_id=?
                """,
                (holder.value, topic, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def by_conviction_id(self, conviction_id: str) -> BeliefRecord | None:
        if not isinstance(conviction_id, str) or not conviction_id:
            raise ValueError("conviction_id is required")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT r.* FROM belief_conviction_revision r
                JOIN belief_conviction_current c
                  ON c.conviction_id=r.conviction_id
                 AND c.revision=r.revision
                WHERE c.conviction_id=?
                """,
                (conviction_id,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, conviction_id: str) -> tuple[BeliefRecord, ...]:
        if not isinstance(conviction_id, str) or not conviction_id:
            raise ValueError("conviction_id is required")
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT r.* FROM belief_conviction_revision r
                WHERE r.conviction_id=?
                ORDER BY r.revision
                """,
                (conviction_id,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def current_for_holder(
        self,
        *,
        holder: BeliefHolder,
        audience_id: str,
    ) -> tuple[BeliefRecord, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT r.* FROM belief_conviction_revision r
                JOIN belief_conviction_current c
                  ON c.conviction_id=r.conviction_id
                 AND c.revision=r.revision
                WHERE c.holder=? AND c.audience_id=?
                ORDER BY c.topic
                """,
                (holder.value, audience_id),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def retrieve_relevant(
        self,
        *,
        query_text: str,
        audience_id: str,
        owner_audience_id: str | None,
        limit: int = 5,
        minimum_score: int = 1,
    ) -> tuple[BeliefMatch, ...]:
        """Audience-isolated, tokenizer-scored projection of current beliefs.

        `owner_audience_only` records are projected only to the exact
        audience they were recorded in, which is the owner audience in
        production. The score is a deterministic token overlap; no model
        output and no authority is involved.
        """
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query_text must be nonempty text")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("limit must be in 1..25")
        if not isinstance(audience_id, str) or not audience_id:
            raise ValueError("audience_id is required")
        if owner_audience_id is not None and not isinstance(
            owner_audience_id, str
        ):
            raise TypeError("owner_audience_id must be text or None")
        query_tokens = tokenize_for_belief_relevance(query_text)
        if not query_tokens:
            return ()
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT r.* FROM belief_conviction_revision r
                JOIN belief_conviction_current c
                  ON c.conviction_id=r.conviction_id
                 AND c.revision=r.revision
                WHERE r.stance != 'withdrawn'
                ORDER BY r.recorded_at DESC
                LIMIT 512
                """
            ).fetchall()
        scored: list[BeliefMatch] = []
        for row in rows:
            record = self._decode(row)
            if record.stance is BeliefStance.WITHDRAWN:
                continue
            if (
                record.visibility is BeliefVisibility.OWNER_AUDIENCE_ONLY
                and record.audience_id != audience_id
            ):
                continue
            scope_tokens = (
                tokenize_for_belief_relevance(record.topic)
                | tokenize_for_belief_relevance(record.statement)
            )
            score = len(query_tokens & scope_tokens)
            if score >= minimum_score:
                scored.append(BeliefMatch(record=record, score=score))
        scored.sort(key=lambda match: (-match.score, match.record.topic))
        return tuple(scored[:limit])

    def schedule_reconsideration(
        self,
        conviction_id: str,
        *,
        due_at: datetime,
        note: str,
        expected_revision: int,
    ) -> BeliefRecord:
        if not isinstance(note, str) or not (1 <= len(note.strip()) <= 600):
            raise ValueError("reconsideration note must be bounded text")
        due_at = _utc(due_at)
        current = self.by_conviction_id(conviction_id)
        if current is None:
            raise ValueError(
                f"conviction {conviction_id!r} does not exist"
            )
        if current.revision != expected_revision:
            raise BeliefConcurrencyError(
                f"revision changed; expected {expected_revision} "
                f"but current is {current.revision}"
            )
        if current.stance is BeliefStance.WITHDRAWN:
            raise ValueError("withdrawn convictions are not reconsidered")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                INSERT INTO belief_reconsideration
                (conviction_id,audience_id,due_at,note) VALUES (?,?,?,?)
                ON CONFLICT(conviction_id) DO UPDATE SET
                    due_at=excluded.due_at,
                    note=excluded.note
                """,
                (
                    conviction_id,
                    current.audience_id,
                    due_at.isoformat(),
                    note.strip(),
                ),
            )
        return current

    def due_reconsiderations(self, *, now: datetime) -> tuple[BeliefReconsideration, ...]:
        now = _utc(now)
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT s.conviction_id, s.audience_id, s.due_at, s.note
                FROM belief_reconsideration s
                WHERE s.due_at <= ?
                ORDER BY s.due_at
                """,
                (now.isoformat(),),
            ).fetchall()
        due: list[BeliefReconsideration] = []
        for row in rows:
            due.append(
                BeliefReconsideration(
                    conviction_id=row["conviction_id"],
                    audience_id=row["audience_id"],
                    due_at=datetime.fromisoformat(row["due_at"]),
                    note=row["note"],
                )
            )
        return tuple(due)

    def clear_reconsideration(self, conviction_id: str) -> None:
        if not isinstance(conviction_id, str) or not conviction_id:
            raise ValueError("conviction_id is required")
        with closing(self._connect()) as db, db:
            db.execute(
                "DELETE FROM belief_reconsideration WHERE conviction_id=?",
                (conviction_id,),
            )
