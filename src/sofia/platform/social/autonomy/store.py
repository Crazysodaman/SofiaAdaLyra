"""Durable, Core-scoped social autonomy state.

Canonical relationship stances reuse the existing REL ``ImpressionStore``.
Only autonomy bookkeeping (evidence categories, topics, cooldowns, budgets and
turn chains) gets additive tables here. Every query is scoped by the local Core
identity so two Cores sharing one state file cannot observe each other.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from sofia.core.rel.impressions import (
    ImpressionChangeKind,
    ImpressionKind,
    ImpressionRecord,
    ImpressionStatus,
    ImpressionStore,
)
from sofia.platform.social.autonomy.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceStatus,
)
from sofia.platform.social.autonomy.models import (
    Boundary,
    BoundaryKind,
    EmotionalAppraisal,
    FACET_IMPRESSION,
    FacetStance,
    Goal,
    Interest,
    Opinion,
    PeerFacet,
    PeerRelationship,
    TopicStatus,
    UnresolvedTopic,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


def _utc(value: datetime, name: str = "timestamp") -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class SocialAutonomyStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.impressions = ImpressionStore(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS social_autonomy_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    core_id TEXT NOT NULL,
                    peer_core_id TEXT,
                    category TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    message_id TEXT,
                    supersedes TEXT,
                    status TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    UNIQUE(core_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS social_autonomy_evidence_scope
                    ON social_autonomy_evidence(core_id, peer_core_id, status);
                CREATE TABLE IF NOT EXISTS social_autonomy_appraisal (
                    appraisal_id TEXT PRIMARY KEY,
                    core_id TEXT NOT NULL,
                    peer_core_id TEXT,
                    topic TEXT,
                    labels TEXT NOT NULL,
                    valence REAL NOT NULL,
                    intensity REAL NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS social_autonomy_appraisal_scope
                    ON social_autonomy_appraisal(core_id, peer_core_id);
                CREATE TABLE IF NOT EXISTS social_autonomy_interest (
                    core_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    strength REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, name)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_goal (
                    core_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority REAL NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, goal_id)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_opinion (
                    core_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    peer_key TEXT NOT NULL,
                    peer_core_id TEXT,
                    revision INTEGER NOT NULL,
                    opinion_id TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    stance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, topic, peer_key, revision)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_boundary (
                    core_id TEXT NOT NULL,
                    peer_key TEXT NOT NULL,
                    peer_core_id TEXT,
                    kind TEXT NOT NULL,
                    value_key TEXT NOT NULL,
                    value TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, peer_key, kind, value_key)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_topic (
                    core_id TEXT NOT NULL,
                    topic_key TEXT NOT NULL,
                    peer_core_id TEXT,
                    room_id TEXT,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    last_activity_at TEXT NOT NULL,
                    next_revisit_at TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    PRIMARY KEY(core_id, topic_key)
                );
                CREATE INDEX IF NOT EXISTS social_autonomy_topic_scope
                    ON social_autonomy_topic(core_id, status, next_revisit_at);
                CREATE TABLE IF NOT EXISTS social_autonomy_turn (
                    core_id TEXT NOT NULL,
                    chain_id TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    turns INTEGER NOT NULL,
                    last_message_id TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, chain_id)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_cooldown (
                    core_id TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    until_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY(core_id, target_key, action)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_seen (
                    core_id TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, room_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_event (
                    core_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS social_autonomy_budget (
                    core_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    contacts INTEGER NOT NULL,
                    inference_units INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(core_id, day)
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _core(core_id: UUID) -> str:
        if not isinstance(core_id, UUID):
            raise TypeError("core_id must be a UUID")
        return str(core_id)

    @staticmethod
    def _peer(peer_core_id: UUID | None) -> str | None:
        if peer_core_id is None:
            return None
        if not isinstance(peer_core_id, UUID):
            raise TypeError("peer_core_id must be a UUID")
        return str(peer_core_id)

    @staticmethod
    def _audience(core_id: UUID, peer_core_id: UUID) -> str:
        return f"peer:{core_id}:{peer_core_id}"

    @staticmethod
    def _subject(peer_core_id: UUID, facet: PeerFacet) -> str:
        return f"peer.{peer_core_id}.{facet.value}"

    def append_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("record must be EvidenceRecord")
        if record.category not in {
            EvidenceCategory.CORRECTION,
            EvidenceCategory.WITHDRAWAL,
        } and record.supersedes is not None:
            raise ValueError("only corrections and withdrawals supersede evidence")
        core = self._core(record.core_id)
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            sequence = db.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM social_autonomy_evidence "
                "WHERE core_id=?",
                (core,),
            ).fetchone()[0]
            if record.sequence != sequence:
                raise ValueError("evidence sequence must be assigned by the store")
            if record.supersedes is not None:
                target = db.execute(
                    "SELECT status FROM social_autonomy_evidence "
                    "WHERE evidence_id=? AND core_id=?",
                    (record.supersedes, core),
                ).fetchone()
                if target is None:
                    raise LookupError("superseded evidence does not exist")
                if target["status"] != EvidenceStatus.ACTIVE.value:
                    raise ValueError("only active evidence can be corrected")
                replacement = (
                    EvidenceStatus.CORRECTED.value
                    if record.category is EvidenceCategory.CORRECTION
                    else EvidenceStatus.WITHDRAWN.value
                )
                db.execute(
                    "UPDATE social_autonomy_evidence SET status=? "
                    "WHERE evidence_id=? AND core_id=?",
                    (replacement, record.supersedes, core),
                )
            db.execute(
                """INSERT INTO social_autonomy_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.evidence_id, core, self._peer(record.peer_core_id),
                    record.category.value, record.claim, record.evidence_ref,
                    record.recorded_at.isoformat(), record.message_id,
                    record.supersedes, record.status.value, record.sequence,
                ),
            )
        return record

    def new_evidence_id(self) -> str:
        return f"evidence:{uuid4()}"

    def record_evidence(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID | None,
        category: EvidenceCategory,
        claim: str,
        evidence_ref: str,
        recorded_at: datetime,
        message_id: str | None = None,
        supersedes: str | None = None,
    ) -> EvidenceRecord:
        if supersedes is not None and peer_core_id is None:
            original = self.evidence(core_id, supersedes)
            if original is None:
                raise LookupError("superseded evidence does not exist")
            peer_core_id = original.peer_core_id
        return self.append_evidence(
            EvidenceRecord(
                evidence_id=self.new_evidence_id(),
                core_id=core_id,
                peer_core_id=peer_core_id,
                category=category,
                claim=claim,
                evidence_ref=evidence_ref,
                recorded_at=recorded_at,
                message_id=message_id,
                supersedes=supersedes,
                status=EvidenceStatus.ACTIVE,
                sequence=self.next_evidence_sequence(core_id),
            )
        )

    def next_evidence_sequence(self, core_id: UUID) -> int:
        with closing(self._open()) as db:
            return int(
                db.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 FROM "
                    "social_autonomy_evidence WHERE core_id=?",
                    (self._core(core_id),),
                ).fetchone()[0]
            )

    @staticmethod
    def _decode_evidence(row: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=row["evidence_id"],
            core_id=UUID(row["core_id"]),
            peer_core_id=(
                None if row["peer_core_id"] is None else UUID(row["peer_core_id"])
            ),
            category=EvidenceCategory(row["category"]),
            claim=row["claim"],
            evidence_ref=row["evidence_ref"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            message_id=row["message_id"],
            supersedes=row["supersedes"],
            status=EvidenceStatus(row["status"]),
            sequence=int(row["sequence"]),
        )

    def evidence(self, core_id: UUID, evidence_id: str) -> EvidenceRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT * FROM social_autonomy_evidence "
                "WHERE core_id=? AND evidence_id=?",
                (self._core(core_id), evidence_id),
            ).fetchone()
        return None if row is None else self._decode_evidence(row)

    def evidence_rows(
        self,
        core_id: UUID,
        *,
        peer_core_id: UUID | None = None,
        category: EvidenceCategory | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        query = "SELECT * FROM social_autonomy_evidence WHERE core_id=?"
        params: list[object] = [self._core(core_id)]
        if peer_core_id is not None:
            query += " AND peer_core_id=?"
            params.append(self._peer(peer_core_id))
        if category is not None:
            query += " AND category=?"
            params.append(category.value)
        query += " ORDER BY sequence ASC"
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        return tuple(self._decode_evidence(row) for row in rows)

    def active_evidence(
        self,
        core_id: UUID,
        *,
        peer_core_id: UUID | None = None,
        category: EvidenceCategory | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        return tuple(
            item
            for item in self.evidence_rows(
                core_id, peer_core_id=peer_core_id, category=category
            )
            if item.status is EvidenceStatus.ACTIVE
        )

    def record_appraisal(self, appraisal: EmotionalAppraisal) -> EmotionalAppraisal:
        if not isinstance(appraisal, EmotionalAppraisal):
            raise TypeError("appraisal must be EmotionalAppraisal")
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT INTO social_autonomy_appraisal VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    appraisal.appraisal_id, self._core(appraisal.core_id),
                    self._peer(appraisal.peer_core_id), appraisal.topic,
                    json.dumps(list(appraisal.labels)), appraisal.valence,
                    appraisal.intensity, appraisal.evidence_ref,
                    appraisal.recorded_at.isoformat(),
                ),
            )
        return appraisal

    def new_appraisal_id(self) -> str:
        return f"appraisal:{uuid4()}"

    def appraisals(
        self, core_id: UUID, *, peer_core_id: UUID | None = None
    ) -> tuple[EmotionalAppraisal, ...]:
        query = "SELECT * FROM social_autonomy_appraisal WHERE core_id=?"
        params: list[object] = [self._core(core_id)]
        if peer_core_id is not None:
            query += " AND peer_core_id=?"
            params.append(self._peer(peer_core_id))
        query += " ORDER BY recorded_at ASC, appraisal_id ASC"
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        return tuple(
            EmotionalAppraisal(
                appraisal_id=row["appraisal_id"],
                core_id=UUID(row["core_id"]),
                peer_core_id=(
                    None
                    if row["peer_core_id"] is None
                    else UUID(row["peer_core_id"])
                ),
                topic=row["topic"],
                labels=tuple(json.loads(row["labels"])),
                valence=float(row["valence"]),
                intensity=float(row["intensity"]),
                evidence_ref=row["evidence_ref"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
            )
            for row in rows
        )

    def set_interest(
        self, core_id: UUID, name: str, strength: float, at: datetime
    ) -> Interest:
        interest = Interest(name, strength)
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_interest VALUES(?,?,?,?)",
                (self._core(core_id), interest.name, interest.strength,
                 _utc(at).isoformat()),
            )
        return interest

    def interests(self, core_id: UUID) -> tuple[Interest, ...]:
        with closing(self._open()) as db:
            rows = db.execute(
                "SELECT name,strength FROM social_autonomy_interest "
                "WHERE core_id=? ORDER BY name ASC",
                (self._core(core_id),),
            ).fetchall()
        return tuple(Interest(row["name"], float(row["strength"])) for row in rows)

    def interest_strength(self, *, core_id: UUID, topic: str) -> float:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT strength FROM social_autonomy_interest "
                "WHERE core_id=? AND name=?",
                (self._core(core_id), topic),
            ).fetchone()
        return 0.0 if row is None else float(row["strength"])

    def set_goal(
        self,
        core_id: UUID,
        goal_id: str,
        description: str,
        priority: float,
        *,
        active: bool,
        at: datetime,
    ) -> Goal:
        goal = Goal(goal_id, description, priority, active)
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_goal VALUES(?,?,?,?,?,?)",
                (self._core(core_id), goal.goal_id, goal.description,
                 goal.priority, 1 if goal.active else 0, _utc(at).isoformat()),
            )
        return goal

    def goals(self, core_id: UUID) -> tuple[Goal, ...]:
        with closing(self._open()) as db:
            rows = db.execute(
                "SELECT goal_id,description,priority,active FROM "
                "social_autonomy_goal WHERE core_id=? ORDER BY priority DESC, goal_id",
                (self._core(core_id),),
            ).fetchall()
        return tuple(
            Goal(
                row["goal_id"], row["description"], float(row["priority"]),
                bool(row["active"]),
            )
            for row in rows
        )

    def record_opinion(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID | None,
        topic: str,
        statement: str,
        stance: float,
        confidence: float,
        evidence_refs: tuple[str, ...],
        recorded_at: datetime,
    ) -> Opinion:
        peer_key = "*" if peer_core_id is None else str(peer_core_id)
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT COALESCE(MAX(revision),0) FROM social_autonomy_opinion "
                "WHERE core_id=? AND topic=? AND peer_key=?",
                (self._core(core_id), topic, peer_key),
            ).fetchone()
            revision = int(row[0]) + 1
            opinion = Opinion(
                opinion_id=f"opinion:{uuid4()}",
                core_id=core_id,
                peer_core_id=peer_core_id,
                topic=topic,
                statement=statement,
                stance=stance,
                confidence=confidence,
                evidence_refs=tuple(evidence_refs),
                revision=revision,
                recorded_at=_utc(recorded_at),
            )
            db.execute(
                "INSERT INTO social_autonomy_opinion VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    self._core(core_id), topic, peer_key,
                    self._peer(peer_core_id), revision, opinion.opinion_id,
                    statement, stance, confidence,
                    json.dumps(list(evidence_refs)),
                    opinion.recorded_at.isoformat(),
                ),
            )
        return opinion

    def opinions(
        self, core_id: UUID, *, peer_core_id: UUID | None = None
    ) -> tuple[Opinion, ...]:
        query = (
            "SELECT * FROM social_autonomy_opinion WHERE core_id=?"
        )
        params: list[object] = [self._core(core_id)]
        if peer_core_id is not None:
            query += " AND peer_key=?"
            params.append(str(peer_core_id))
        query += " ORDER BY topic ASC, revision ASC"
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        latest: dict[tuple[str, str], Opinion] = {}
        for row in rows:
            opinion = Opinion(
                opinion_id=row["opinion_id"],
                core_id=UUID(row["core_id"]),
                peer_core_id=(
                    None
                    if row["peer_core_id"] is None
                    else UUID(row["peer_core_id"])
                ),
                topic=row["topic"],
                statement=row["statement"],
                stance=float(row["stance"]),
                confidence=float(row["confidence"]),
                evidence_refs=tuple(json.loads(row["evidence_refs"])),
                revision=int(row["revision"]),
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
            )
            latest[(opinion.topic, row["peer_key"])] = opinion
        return tuple(
            latest[key] for key in sorted(latest, key=lambda item: item[0])
        )

    def set_boundary(
        self,
        core_id: UUID,
        peer_core_id: UUID | None,
        kind: BoundaryKind,
        value: str | None,
        at: datetime,
    ) -> Boundary:
        boundary = Boundary(peer_core_id, kind, value)
        peer_key = "*" if peer_core_id is None else str(peer_core_id)
        value_key = "*" if value is None else value
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_boundary VALUES(?,?,?,?,?,?,?)",
                (
                    self._core(core_id), peer_key, self._peer(peer_core_id),
                    kind.value, value_key, value, _utc(at).isoformat(),
                ),
            )
        return boundary

    def boundaries(
        self, core_id: UUID, *, peer_core_id: UUID | None = None
    ) -> tuple[Boundary, ...]:
        query = "SELECT * FROM social_autonomy_boundary WHERE core_id=?"
        params: list[object] = [self._core(core_id)]
        if peer_core_id is not None:
            query += " AND (peer_core_id IS NULL OR peer_core_id=?)"
            params.append(self._peer(peer_core_id))
        query += " ORDER BY kind ASC, value_key ASC"
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        return tuple(
            Boundary(
                None if row["peer_core_id"] is None else UUID(row["peer_core_id"]),
                BoundaryKind(row["kind"]),
                row["value"],
            )
            for row in rows
        )

    def contact_allowed(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID,
        room_id: str | None,
        private: bool = False,
    ) -> bool:
        for boundary in self.boundaries(core_id, peer_core_id=peer_core_id):
            if boundary.kind is BoundaryKind.NO_CONTACT:
                return False
            if private and boundary.kind is BoundaryKind.NO_PRIVATE:
                return False
            if (
                boundary.kind is BoundaryKind.NO_TOPIC
                and room_id is not None
                and boundary.value == room_id
            ):
                return False
        return True

    def set_topic(
        self,
        *,
        core_id: UUID,
        topic_key: str,
        peer_core_id: UUID | None,
        room_id: str | None,
        summary: str,
        status: TopicStatus,
        now: datetime,
        next_revisit_at: datetime,
    ) -> UnresolvedTopic:
        stamp = _utc(now)
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT opened_at,revision FROM social_autonomy_topic "
                "WHERE core_id=? AND topic_key=?",
                (self._core(core_id), topic_key),
            ).fetchone()
            if row is None:
                opened = stamp
                revision = 1
            else:
                opened = datetime.fromisoformat(row["opened_at"])
                revision = int(row["revision"]) + 1
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_topic VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    self._core(core_id), topic_key, self._peer(peer_core_id),
                    room_id, summary, status.value, opened.isoformat(),
                    stamp.isoformat(), _utc(next_revisit_at).isoformat(), revision,
                ),
            )
        return UnresolvedTopic(
            topic_key=topic_key,
            peer_core_id=peer_core_id,
            room_id=room_id,
            summary=summary,
            status=status,
            opened_at=opened,
            last_activity_at=stamp,
            next_revisit_at=_utc(next_revisit_at),
            revision=revision,
        )

    @staticmethod
    def _decode_topic(row: sqlite3.Row) -> UnresolvedTopic:
        return UnresolvedTopic(
            topic_key=row["topic_key"],
            peer_core_id=(
                None if row["peer_core_id"] is None else UUID(row["peer_core_id"])
            ),
            room_id=row["room_id"],
            summary=row["summary"],
            status=TopicStatus(row["status"]),
            opened_at=datetime.fromisoformat(row["opened_at"]),
            last_activity_at=datetime.fromisoformat(row["last_activity_at"]),
            next_revisit_at=datetime.fromisoformat(row["next_revisit_at"]),
            revision=int(row["revision"]),
        )

    def topic(self, core_id: UUID, topic_key: str) -> UnresolvedTopic | None:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT * FROM social_autonomy_topic "
                "WHERE core_id=? AND topic_key=?",
                (self._core(core_id), topic_key),
            ).fetchone()
        return None if row is None else self._decode_topic(row)

    def topics(
        self,
        core_id: UUID,
        *,
        peer_core_id: UUID | None = None,
        status: TopicStatus | None = None,
        due_before: datetime | None = None,
    ) -> tuple[UnresolvedTopic, ...]:
        query = "SELECT * FROM social_autonomy_topic WHERE core_id=?"
        params: list[object] = [self._core(core_id)]
        if peer_core_id is not None:
            query += " AND peer_core_id=?"
            params.append(self._peer(peer_core_id))
        if status is not None:
            query += " AND status=?"
            params.append(status.value)
        if due_before is not None:
            query += " AND next_revisit_at<=?"
            params.append(_utc(due_before).isoformat())
        query += " ORDER BY next_revisit_at ASC, topic_key ASC"
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        return tuple(self._decode_topic(row) for row in rows)

    def turn_count(self, core_id: UUID, chain_id: str) -> int:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT turns FROM social_autonomy_turn "
                "WHERE core_id=? AND chain_id=?",
                (self._core(core_id), chain_id),
            ).fetchone()
        return 0 if row is None else int(row["turns"])

    def bump_turn(
        self,
        *,
        core_id: UUID,
        chain_id: str,
        room_id: str,
        message_id: str | None,
        now: datetime,
    ) -> int:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT turns FROM social_autonomy_turn "
                "WHERE core_id=? AND chain_id=?",
                (self._core(core_id), chain_id),
            ).fetchone()
            turns = (0 if row is None else int(row["turns"])) + 1
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_turn VALUES(?,?,?,?,?,?)",
                (self._core(core_id), chain_id, room_id, turns, message_id,
                 _utc(now).isoformat()),
            )
        return turns

    def set_cooldown(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID,
        action: str,
        until_at: datetime,
        reason: str,
        now: datetime,
    ) -> None:
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_cooldown VALUES(?,?,?,?,?)",
                (
                    self._core(core_id), self._peer(peer_core_id), action,
                    _utc(until_at).isoformat(), reason,
                ),
            )

    def cooldown_until(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID,
        action: str,
        now: datetime,
    ) -> datetime | None:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT until_at FROM social_autonomy_cooldown "
                "WHERE core_id=? AND target_key=? AND action=?",
                (self._core(core_id), self._peer(peer_core_id), action),
            ).fetchone()
        if row is None:
            return None
        until = datetime.fromisoformat(row["until_at"])
        return until if until > _utc(now) else None

    def is_seen(self, core_id: UUID, room_id: str, message_id: str) -> bool:
        with closing(self._open()) as db:
            return db.execute(
                "SELECT 1 FROM social_autonomy_seen "
                "WHERE core_id=? AND room_id=? AND message_id=?",
                (self._core(core_id), room_id, message_id),
            ).fetchone() is not None

    def mark_seen(
        self, *, core_id: UUID, room_id: str, message_id: str, now: datetime
    ) -> None:
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO social_autonomy_seen VALUES(?,?,?,?)",
                (self._core(core_id), room_id, message_id, _utc(now).isoformat()),
            )

    def event_processed(self, core_id: UUID, event_id: str) -> bool:
        with closing(self._open()) as db:
            return db.execute(
                "SELECT 1 FROM social_autonomy_event WHERE core_id=? AND event_id=?",
                (self._core(core_id), event_id),
            ).fetchone() is not None

    def mark_event(
        self, *, core_id: UUID, event_id: str, now: datetime
    ) -> None:
        with closing(self._open()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO social_autonomy_event VALUES(?,?,?)",
                (self._core(core_id), event_id, _utc(now).isoformat()),
            )

    def budget_usage(self, core_id: UUID, day: str) -> tuple[int, int]:
        with closing(self._open()) as db:
            row = db.execute(
                "SELECT contacts,inference_units FROM social_autonomy_budget "
                "WHERE core_id=? AND day=?",
                (self._core(core_id), day),
            ).fetchone()
        return (0, 0) if row is None else (
            int(row["contacts"]), int(row["inference_units"])
        )

    def consume_budget(
        self,
        *,
        core_id: UUID,
        day: str,
        contacts: int,
        inference_units: int,
        now: datetime,
    ) -> None:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT contacts,inference_units FROM social_autonomy_budget "
                "WHERE core_id=? AND day=?",
                (self._core(core_id), day),
            ).fetchone()
            used_contacts = 0 if row is None else int(row["contacts"])
            used_inference = 0 if row is None else int(row["inference_units"])
            db.execute(
                "INSERT OR REPLACE INTO social_autonomy_budget VALUES(?,?,?,?,?)",
                (
                    self._core(core_id), day,
                    used_contacts + max(0, contacts),
                    used_inference + max(0, inference_units),
                    _utc(now).isoformat(),
                ),
            )

    def set_facet(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID,
        facet: PeerFacet,
        level: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        recorded_at: datetime,
    ) -> FacetStance:
        if facet not in FACET_IMPRESSION:
            raise ValueError("unsupported facet")
        kind, polarity = FACET_IMPRESSION[facet]
        audience = self._audience(core_id, peer_core_id)
        principal = f"core:{peer_core_id}"
        subject = self._subject(peer_core_id, facet)
        current = self.impressions.current(
            principal_id=principal,
            subject=subject,
            kind=kind,
            audience_id=audience,
        )
        if current is None:
            record = ImpressionRecord(
                impression_id=self.impressions.new_impression_id(),
                revision=1,
                principal_id=principal,
                subject=subject,
                kind=kind,
                level=level,
                reason=reason,
                evidence_refs=tuple(evidence_refs),
                audience_id=audience,
                change_kind=ImpressionChangeKind.ORIGIN,
                status=ImpressionStatus.ACTIVE,
                recorded_at=recorded_at,
            )
            self.impressions.hold(record, expected_revision=None)
        else:
            record = ImpressionRecord(
                impression_id=current.impression_id,
                revision=current.revision + 1,
                principal_id=principal,
                subject=subject,
                kind=kind,
                level=level,
                reason=reason,
                evidence_refs=tuple(evidence_refs),
                audience_id=audience,
                change_kind=ImpressionChangeKind.RECONCILE,
                status=ImpressionStatus.ACTIVE,
                recorded_at=recorded_at,
            )
            self.impressions.hold(record, expected_revision=current.revision)
        return FacetStance(
            impression_id=record.impression_id,
            facet=facet,
            kind=kind,
            level=level,
            polarity=polarity,
            reason=reason,
            evidence_refs=tuple(evidence_refs),
            revision=record.revision,
            recorded_at=record.recorded_at,
        )

    def relationship(
        self, core_id: UUID, peer_core_id: UUID
    ) -> PeerRelationship:
        audience = self._audience(core_id, peer_core_id)
        principal = f"core:{peer_core_id}"
        records = self.impressions.active_impressions(
            principal_id=principal, audience_id=audience, limit=64
        )
        by_subject = {record.subject: record for record in records}
        stances: list[FacetStance] = []
        for facet, (kind, polarity) in FACET_IMPRESSION.items():
            record = by_subject.get(self._subject(peer_core_id, facet))
            if record is None or record.kind is not kind:
                continue
            stances.append(
                FacetStance(
                    impression_id=record.impression_id,
                    facet=facet,
                    kind=record.kind,
                    level=record.level,
                    polarity=polarity,
                    reason=record.reason,
                    evidence_refs=record.evidence_refs,
                    revision=record.revision,
                    recorded_at=record.recorded_at,
                )
            )
        return PeerRelationship(
            core_id=core_id,
            peer_core_id=peer_core_id,
            stances=tuple(stances),
        )
