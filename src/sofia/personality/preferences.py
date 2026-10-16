"""Evidence-backed general preferences, separate from interaction consent."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.social.model import PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID


_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")


class PreferenceSubject(str, Enum):
    SOFIA = "sofia"
    SPARKS = "sparks"
    SHARED = "shared"


class PreferenceDisposition(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    FAVORITE = "favorite"
    STRONG_AVERSION = "strong_aversion"
    INDIFFERENT = "indifferent"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PreferenceRecord:
    preference_id: str
    subject: PreferenceSubject
    category: str
    target_id: str
    context: str
    disposition: PreferenceDisposition
    strength: float
    confidence: float
    reason: str
    evidence_ref: str
    audience_id: str
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.preference_id, "preference_id"), (self.category, "category"),
            (self.target_id, "target_id"), (self.context, "context"),
        ):
            if _KEY.fullmatch(value) is None:
                raise ValueError(f"{label} must be canonical")
        if not 0.0 <= self.strength <= 1.0 or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("preference strength/confidence must be in 0..1")
        if not self.reason.strip() or len(self.reason) > 1000:
            raise ValueError("preference reason must be bounded text")
        if not self.evidence_ref.strip() or len(self.evidence_ref) > 300:
            raise ValueError("preference evidence_ref is required")
        if not self.audience_id.strip() or len(self.audience_id) > 160:
            raise ValueError("audience_id is required")
        if self.revision < 1:
            raise ValueError("preference revision must be positive")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")


class PreferenceRegistry:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS personality_preference_revision (
                    preference_id TEXT PRIMARY KEY, subject TEXT NOT NULL,
                    category TEXT NOT NULL, target_id TEXT NOT NULL,
                    context TEXT NOT NULL, disposition TEXT NOT NULL,
                    strength REAL NOT NULL, confidence REAL NOT NULL,
                    reason TEXT NOT NULL, evidence_ref TEXT NOT NULL,
                    audience_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(subject,category,target_id,context,audience_id,revision)
                );
                CREATE INDEX IF NOT EXISTS personality_preference_latest
                    ON personality_preference_revision(
                        subject,category,target_id,context,audience_id,revision DESC
                    );
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _decode(row) -> PreferenceRecord:
        return PreferenceRecord(
            row["preference_id"], PreferenceSubject(row["subject"]),
            row["category"], row["target_id"], row["context"],
            PreferenceDisposition(row["disposition"]), float(row["strength"]),
            float(row["confidence"]), row["reason"], row["evidence_ref"],
            row["audience_id"], int(row["revision"]),
            datetime.fromisoformat(row["recorded_at"]),
        )
    def revise(
        self, *, subject: PreferenceSubject, category: str, target_id: str,
        context: str, disposition: PreferenceDisposition, strength: float,
        confidence: float, reason: str, evidence_ref: str, audience_id: str,
        expected_revision: int | None, now: datetime,
    ) -> PreferenceRecord:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("preference timestamp must be timezone-aware")
        record = PreferenceRecord(
            f"preference:{uuid4()}", subject, category, target_id, context,
            disposition, strength, confidence, reason, evidence_ref,
            audience_id, 1 if expected_revision is None else expected_revision + 1,
            now.astimezone(timezone.utc),
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT revision FROM personality_preference_revision
                WHERE subject=? AND category=? AND target_id=? AND context=?
                AND audience_id=? ORDER BY revision DESC LIMIT 1""",
                (subject.value, category, target_id, context, audience_id),
            ).fetchone()
            current = None if row is None else int(row[0])
            if current != expected_revision:
                raise RuntimeError("preference revision changed; reload before revising")
            db.execute(
                "INSERT INTO personality_preference_revision VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record.preference_id, record.subject.value, record.category,
                 record.target_id, record.context, record.disposition.value,
                 record.strength, record.confidence, record.reason,
                 record.evidence_ref, record.audience_id, record.revision,
                 record.recorded_at.isoformat()),
            )
        return record

    def current(
        self, *, subject: PreferenceSubject, category: str, target_id: str,
        context: str, audience_id: str,
    ) -> PreferenceRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM personality_preference_revision
                WHERE subject=? AND category=? AND target_id=? AND context=?
                AND audience_id=? ORDER BY revision DESC LIMIT 1""",
                (subject.value, category, target_id, context, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, **scope) -> tuple[PreferenceRecord, ...]:
        current = self.current(**scope)
        if current is None:
            return ()
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM personality_preference_revision
                WHERE subject=? AND category=? AND target_id=? AND context=?
                AND audience_id=? ORDER BY revision""",
                (scope["subject"].value, scope["category"], scope["target_id"],
                 scope["context"], scope["audience_id"]),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def eligible_choices(
        self, *, subject: PreferenceSubject, category: str, context: str,
        audience_id: str, minimum_confidence: float = 0.6,
    ) -> tuple[PreferenceRecord, ...]:
        """Project influence only; callers retain authority and factual checks."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT p.* FROM personality_preference_revision p
                JOIN (SELECT target_id,MAX(revision) revision
                      FROM personality_preference_revision
                      WHERE subject=? AND category=? AND context=? AND audience_id=?
                      GROUP BY target_id) latest
                ON p.target_id=latest.target_id AND p.revision=latest.revision
                WHERE p.subject=? AND p.category=? AND p.context=? AND p.audience_id=?
                AND p.confidence>=? AND p.disposition IN ('like','favorite')
                ORDER BY p.strength DESC,p.target_id""",
                (subject.value, category, context, audience_id,
                 subject.value, category, context, audience_id, minimum_confidence),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def latest_for_category(
        self, *, subject: PreferenceSubject, category: str, context: str,
        audience_id: str,
    ) -> tuple[PreferenceRecord, ...]:
        """Return latest scoped records, including dislikes and unknowns."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT p.* FROM personality_preference_revision p
                JOIN (SELECT target_id,MAX(revision) revision
                      FROM personality_preference_revision
                      WHERE subject=? AND category=? AND context=? AND audience_id=?
                      GROUP BY target_id) latest
                ON p.target_id=latest.target_id AND p.revision=latest.revision
                WHERE p.subject=? AND p.category=? AND p.context=? AND p.audience_id=?
                ORDER BY p.target_id""",
                (subject.value, category, context, audience_id,
                 subject.value, category, context, audience_id),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)


@dataclass(frozen=True, slots=True)
class CommunicationStylePreferences:
    """Audience-scoped owner guidance; style only, never authority."""

    humor: float | None = None
    verbosity: float | None = None
    disagreement: float | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("humor", "verbosity", "disagreement"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ValueError(f"{name} must be None or a number in 0..1")


class CommunicationPreferenceService:
    """Typed adapter over the canonical preference revision registry."""

    CATEGORY = "conversation.style"
    CONTEXT = "general"
    TARGETS = frozenset({"humor", "verbosity", "disagreement"})

    def __init__(self, registry: PreferenceRegistry) -> None:
        if not isinstance(registry, PreferenceRegistry):
            raise TypeError("registry must be PreferenceRegistry")
        self.registry = registry

    @staticmethod
    def _level(record: PreferenceRecord | None) -> float | None:
        if record is None or record.disposition is PreferenceDisposition.UNKNOWN:
            return None
        if record.disposition is PreferenceDisposition.INDIFFERENT:
            return 0.5
        if record.disposition in {
            PreferenceDisposition.DISLIKE,
            PreferenceDisposition.STRONG_AVERSION,
        }:
            return round(1.0 - record.strength, 3)
        return round(record.strength, 3)

    def for_principal(
        self, principal: PrincipalContext,
    ) -> CommunicationStylePreferences:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        records = {
            target: self.registry.current(
                subject=PreferenceSubject.SPARKS,
                category=self.CATEGORY,
                target_id=target,
                context=self.CONTEXT,
                audience_id=principal.audience_id,
            )
            for target in self.TARGETS
        }
        return CommunicationStylePreferences(
            humor=self._level(records["humor"]),
            verbosity=self._level(records["verbosity"]),
            disagreement=self._level(records["disagreement"]),
            evidence_refs=tuple(
                record.evidence_ref
                for target in sorted(records)
                if (record := records[target]) is not None
            ),
        )

    def revise_owner_override(
        self, *, principal: PrincipalContext, target: str, level: float,
        reason: str, evidence_ref: str, expected_revision: int | None,
        now: datetime,
    ) -> PreferenceRecord:
        """Record an authenticated owner's preference for one exact audience."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError("only the authenticated owner may set this override")
        if target not in self.TARGETS:
            raise ValueError("unsupported communication preference")
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise TypeError("communication preference level must be numeric")
        level = float(level)
        if not 0.0 <= level <= 1.0:
            raise ValueError("communication preference level must be in 0..1")
        if level == 0.5:
            disposition = PreferenceDisposition.INDIFFERENT
            strength = 0.5
        elif level > 0.5:
            disposition = PreferenceDisposition.LIKE
            strength = level
        else:
            disposition = PreferenceDisposition.DISLIKE
            strength = 1.0 - level
        return self.registry.revise(
            subject=PreferenceSubject.SPARKS,
            category=self.CATEGORY,
            target_id=target,
            context=self.CONTEXT,
            disposition=disposition,
            strength=strength,
            confidence=1.0,
            reason=reason,
            evidence_ref=evidence_ref,
            audience_id=principal.audience_id,
            expected_revision=expected_revision,
            now=now,
        )
