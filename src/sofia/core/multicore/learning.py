"""Evidence-based preference and belief revision for independent Aegis Cores.

Preferences are never established by a single enthusiastic statement.  Each
change is derived from accumulated, owner-scoped observations with explicit
evidence state.  Corrections are retained so a Core can revise a strongly held
opinion when better evidence arrives without erasing its prior position.

No Core starts with seeded hobbies, beliefs or preferences.  Nova's interests,
like Mack's opinions, exist only when evidence produces them.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import NAMESPACE_URL, UUID, uuid5

from sofia.core.multicore.contracts import (
    EvidenceState,
    PreferenceRecord,
    PreferenceState,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

DORMANCY = timedelta(days=180)
MAX_SUBJECT = 160
MAX_STATEMENT = 4000
_DOMAINS = {
    "preference": "preference",
    "belief": "belief",
    "interest": "interest",
    "hobby": "interest",
}
_EVIDENCE_WEIGHT = {
    EvidenceState.VERIFIED: 1.0,
    EvidenceState.REPORTED: 0.5,
    EvidenceState.INFERRED: 0.25,
    EvidenceState.SPECULATIVE: 0.1,
}
_STRONG_STATES = frozenset({
    PreferenceState.DEVELOPING,
    PreferenceState.ESTABLISHED,
    PreferenceState.REVISED,
})


def _uuid(value: UUID | str, label: str) -> UUID:
    if isinstance(value, UUID):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a UUID") from exc
    else:
        raise TypeError(f"{label} must be a UUID or UUID string")
    if result.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return result


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _domain(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("domain must be text")
    try:
        return _DOMAINS[value.strip().casefold()]
    except KeyError as exc:
        raise ValueError("domain must be preference, belief, interest or hobby") from exc


def _subject(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_SUBJECT:
        raise ValueError("subject must be bounded nonempty text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class PreferenceObservation:
    evidence_id: UUID
    owner_core_id: UUID
    subject: str
    domain: str
    stance: bool
    evidence: EvidenceState
    source: str
    statement: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class PreferenceCorrection:
    correction_id: UUID
    owner_core_id: UUID
    subject: str
    domain: str
    prior_state: PreferenceState
    prior_stance: bool
    new_state: PreferenceState
    new_stance: bool
    reason: str
    occurred_at: datetime
    revision: int


@dataclass(frozen=True, slots=True)
class _Stored:
    preference_id: UUID
    owner_core_id: UUID
    subject: str
    domain: str
    state: PreferenceState
    stance: bool
    confidence: float
    evidence: tuple[UUID, ...]
    updated_at: datetime
    revision: int


class MulticoreLearningService:
    """Owner-scoped evidence ledger and preference/belief projection."""

    def __init__(
        self,
        state_path: str | Path,
        owner_core_id: UUID | str | None = None,
    ) -> None:
        self._owner_core_id = None if owner_core_id is None else _uuid(owner_core_id, "owner_core_id")
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._initialize()

    @property
    def owner_core_id(self) -> UUID | None:
        return self._owner_core_id

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10, check_same_thread=False)

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 10000")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS multicore_preference_observation(
                    evidence_id TEXT PRIMARY KEY,
                    owner_core_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    stance INTEGER NOT NULL,
                    evidence_state TEXT NOT NULL,
                    source TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS multicore_preference_observation_subject
                ON multicore_preference_observation(
                    owner_core_id, domain, subject, observed_at
                );
                CREATE TABLE IF NOT EXISTS multicore_preference(
                    preference_id TEXT PRIMARY KEY,
                    owner_core_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    state TEXT NOT NULL,
                    stance INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(owner_core_id, domain, subject)
                );
                CREATE TABLE IF NOT EXISTS multicore_preference_correction(
                    correction_id TEXT PRIMARY KEY,
                    owner_core_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    prior_state TEXT NOT NULL,
                    prior_stance INTEGER NOT NULL,
                    new_state TEXT NOT NULL,
                    new_stance INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS multicore_preference_correction_subject
                ON multicore_preference_correction(owner_core_id, domain, subject, occurred_at);
                """
            )

    def _require_owner(self, explicit: UUID | str | None = None) -> UUID:
        candidate = None if explicit is None else _uuid(explicit, "owner_core_id")
        if self._owner_core_id is not None:
            if candidate is not None and candidate != self._owner_core_id:
                raise PermissionError("preference owner does not match this bound service")
            return self._owner_core_id
        if candidate is None:
            raise PermissionError("an explicit owner_core_id is required")
        return candidate

    @staticmethod
    def _observation_id(
        *,
        owner: UUID,
        subject: str,
        domain: str,
        stance: bool,
        evidence: EvidenceState,
        source: str,
        statement: str,
        observed_at: datetime,
    ) -> UUID:
        body = _canonical({
            "owner": str(owner),
            "subject": subject,
            "domain": domain,
            "stance": bool(stance),
            "evidence": evidence.value,
            "source": source,
            "statement": statement,
            "observed_at": _iso(observed_at),
        })
        return uuid5(NAMESPACE_URL, "aegis-preference-observation:" + sha256(
            body.encode("utf-8")
        ).hexdigest())

    @staticmethod
    def _row_stored(row: tuple[object, ...]) -> _Stored:
        return _Stored(
            preference_id=UUID(str(row[0])),
            owner_core_id=UUID(str(row[1])),
            subject=str(row[2]),
            domain=str(row[3]),
            state=PreferenceState(str(row[4])),
            stance=bool(row[5]),
            confidence=float(row[6]),
            evidence=tuple(UUID(str(item)) for item in json.loads(str(row[7]))),
            updated_at=datetime.fromisoformat(str(row[8])),
            revision=int(row[9]),
        )

    @staticmethod
    def _to_record(stored: _Stored) -> PreferenceRecord:
        return PreferenceRecord(
            preference_id=stored.preference_id,
            owner_core_id=stored.owner_core_id,
            subject=stored.subject,
            state=stored.state,
            confidence=stored.confidence,
            evidence=stored.evidence,
            updated_at=stored.updated_at,
            revision=stored.revision,
        )

    def _select_stored(
        self,
        db: sqlite3.Connection,
        owner: UUID,
        domain: str,
        subject: str,
    ) -> _Stored | None:
        row = db.execute(
            "SELECT preference_id,owner_core_id,subject,domain,state,stance,"
            "confidence,evidence_json,updated_at,revision FROM multicore_preference "
            "WHERE owner_core_id=? AND domain=? AND subject=?",
            (str(owner), domain, subject),
        ).fetchone()
        return None if row is None else self._row_stored(tuple(row))

    def observe(
        self,
        owner_core_id: UUID | str,
        subject: str,
        *,
        stance: bool,
        evidence: EvidenceState,
        source: str,
        statement: str,
        observed_at: datetime,
        domain: str = "preference",
    ) -> PreferenceRecord:
        """Record one evidence item and recompute the owner's projection."""
        owner = self._require_owner(owner_core_id)
        subject = _subject(subject)
        domain = _domain(domain)
        if type(stance) is not bool:
            raise TypeError("stance must be boolean")
        if not isinstance(evidence, EvidenceState):
            raise TypeError("evidence must be EvidenceState")
        for label, value in (("source", source), ("statement", statement)):
            if not isinstance(value, str) or not value.strip() or len(value) > (
                MAX_STATEMENT if label == "statement" else 512
            ):
                raise ValueError(f"{label} must be bounded nonempty text")
        moment = _utc(observed_at, "observed_at")
        evidence_id = self._observation_id(
            owner=owner,
            subject=subject,
            domain=domain,
            stance=stance,
            evidence=evidence,
            source=source,
            statement=statement,
            observed_at=moment,
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            inserted = db.execute(
                "INSERT OR IGNORE INTO multicore_preference_observation VALUES("
                "?,?,?,?,?,?,?,?,?)",
                (
                    str(evidence_id),
                    str(owner),
                    subject,
                    domain,
                    int(stance),
                    evidence.value,
                    source,
                    statement,
                    _iso(moment),
                ),
            ).rowcount == 1
            rows = db.execute(
                "SELECT evidence_id,stance,evidence_state,observed_at,statement "
                "FROM multicore_preference_observation "
                "WHERE owner_core_id=? AND domain=? AND subject=? "
                "ORDER BY observed_at,evidence_id",
                (str(owner), domain, subject),
            ).fetchall()
            observations = tuple(
                (
                    UUID(str(row[0])),
                    bool(row[1]),
                    EvidenceState(str(row[2])),
                    datetime.fromisoformat(str(row[3])),
                    str(row[4]),
                )
                for row in rows
            )
            previous = self._select_stored(db, owner, domain, subject)
            stored = self._derive(
                owner=owner,
                subject=subject,
                domain=domain,
                observations=observations,
                previous=previous,
                now=moment,
                force_active=inserted,
            )
            self._upsert(db, stored)
            self._record_correction(db, previous, stored, observations[-1], moment)
        return self._to_record(stored)

    def observe_preference(
        self,
        owner_core_id: UUID | str,
        subject: str,
        **kwargs,
    ) -> PreferenceRecord:
        kwargs["domain"] = "preference"
        return self.observe(owner_core_id, subject, **kwargs)

    def observe_belief(
        self,
        owner_core_id: UUID | str,
        subject: str,
        **kwargs,
    ) -> PreferenceRecord:
        kwargs["domain"] = "belief"
        return self.observe(owner_core_id, subject, **kwargs)

    def observe_interest(
        self,
        owner_core_id: UUID | str,
        subject: str,
        **kwargs,
    ) -> PreferenceRecord:
        kwargs["domain"] = "interest"
        return self.observe(owner_core_id, subject, **kwargs)

    def _derive(
        self,
        *,
        owner: UUID,
        subject: str,
        domain: str,
        observations: tuple[
            tuple[UUID, bool, EvidenceState, datetime, str], ...
        ],
        previous: _Stored | None,
        now: datetime,
        force_active: bool = False,
    ) -> _Stored:
        if not observations:
            raise ValueError("at least one observation is required")
        last_id, last_stance, last_evidence, last_at, last_statement = observations[-1]

        net = sum(
            _EVIDENCE_WEIGHT[item[2]] * (1.0 if item[1] else -1.0)
            for item in observations
        )
        stance = bool(net > 0) if net != 0 else last_stance
        corrected = bool(
            previous is not None
            and previous.state in _STRONG_STATES
            and last_evidence is EvidenceState.VERIFIED
            and last_stance != previous.stance
        )
        if corrected:
            stance = last_stance

        supporting = tuple(item for item in observations if item[1] == stance)
        support_count = len(supporting)
        verified_support = sum(
            1 for item in supporting if item[2] is EvidenceState.VERIFIED
        )
        support_weight = sum(_EVIDENCE_WEIGHT[item[2]] for item in supporting)
        confidence = min(1.0, abs(net) / 3.0)

        dormant = bool(
            not force_active
            and previous is not None
            and not corrected
            and last_at <= previous.updated_at
            and (
                (
                    previous.state in _STRONG_STATES
                    and now - previous.updated_at >= DORMANCY
                )
                or previous.state is PreferenceState.DORMANT
            )
        )

        if dormant:
            state = PreferenceState.DORMANT
            stance = previous.stance
            confidence = previous.confidence
        elif corrected:
            state = PreferenceState.REVISED
        elif support_count == 0:
            state = PreferenceState.TENTATIVE
        elif verified_support >= 3 and support_weight >= 3.0:
            state = PreferenceState.ESTABLISHED
        elif support_count >= 2:
            state = PreferenceState.DEVELOPING
        else:
            state = PreferenceState.TENTATIVE

        revision = previous.revision if previous is not None else 1
        if previous is not None and (
            previous.state is not state or previous.stance is not stance
        ):
            revision = previous.revision + 1

        preference_id = (
            previous.preference_id
            if previous is not None
            else uuid5(
                NAMESPACE_URL,
                f"aegis-preference:{owner}:{domain}:{subject}",
            )
        )
        updated_at = now if dormant else last_at
        evidence_ids = tuple(item[0] for item in observations)
        return _Stored(
            preference_id=preference_id,
            owner_core_id=owner,
            subject=subject,
            domain=domain,
            state=state,
            stance=stance,
            confidence=confidence,
            evidence=evidence_ids,
            updated_at=updated_at,
            revision=revision,
        )

    @staticmethod
    def _upsert(db: sqlite3.Connection, stored: _Stored) -> None:
        db.execute(
            "INSERT INTO multicore_preference("
            "preference_id,owner_core_id,subject,domain,state,stance,confidence,"
            "evidence_json,updated_at,revision) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(owner_core_id,domain,subject) DO UPDATE SET "
            "state=excluded.state,stance=excluded.stance,"
            "confidence=excluded.confidence,evidence_json=excluded.evidence_json,"
            "updated_at=excluded.updated_at,revision=excluded.revision",
            (
                str(stored.preference_id),
                str(stored.owner_core_id),
                stored.subject,
                stored.domain,
                stored.state.value,
                int(stored.stance),
                float(stored.confidence),
                json.dumps([str(item) for item in stored.evidence]),
                _iso(stored.updated_at),
                int(stored.revision),
            ),
        )

    @staticmethod
    def _record_correction(
        db: sqlite3.Connection,
        previous: _Stored | None,
        stored: _Stored,
        latest: tuple[UUID, bool, EvidenceState, datetime, str],
        moment: datetime,
    ) -> None:
        if previous is None:
            return
        flipped = previous.stance is not stored.stance
        revised = stored.state is PreferenceState.REVISED
        if not (flipped or revised):
            return
        body = _canonical({
            "owner": str(stored.owner_core_id),
            "subject": stored.subject,
            "domain": stored.domain,
            "revision": stored.revision,
            "prior": previous.state.value,
            "new": stored.state.value,
            "at": _iso(moment),
        })
        correction_id = uuid5(
            NAMESPACE_URL,
            "aegis-preference-correction:" + sha256(body.encode("utf-8")).hexdigest(),
        )
        db.execute(
            "INSERT OR IGNORE INTO multicore_preference_correction VALUES("
            "?,?,?,?,?,?,?,?,?,?,?)",
            (
                str(correction_id),
                str(stored.owner_core_id),
                stored.subject,
                stored.domain,
                previous.state.value,
                int(previous.stance),
                stored.state.value,
                int(stored.stance),
                latest[4][:512],
                _iso(moment),
                int(stored.revision),
            ),
        )

    def get_preference(
        self,
        owner_core_id: UUID | str | None = None,
        subject: str | None = None,
        *,
        domain: str = "preference",
    ) -> PreferenceRecord | None:
        owner = self._require_owner(owner_core_id)
        if subject is None:
            raise ValueError("subject is required")
        subject = _subject(subject)
        domain = _domain(domain)
        with closing(self._connect()) as db:
            stored = self._select_stored(db, owner, domain, subject)
        return None if stored is None else self._to_record(stored)

    def preferences(
        self,
        owner_core_id: UUID | str | None = None,
        *,
        domain: str | None = None,
        state: PreferenceState | None = None,
    ) -> tuple[PreferenceRecord, ...]:
        owner = self._require_owner(owner_core_id)
        clauses = ["owner_core_id=?"]
        params: list[object] = [str(owner)]
        if domain is not None:
            clauses.append("domain=?")
            params.append(_domain(domain))
        if state is not None:
            if not isinstance(state, PreferenceState):
                raise TypeError("state must be PreferenceState or None")
            clauses.append("state=?")
            params.append(state.value)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT preference_id,owner_core_id,subject,domain,state,stance,"
                "confidence,evidence_json,updated_at,revision FROM multicore_preference "
                "WHERE " + " AND ".join(clauses) + " ORDER BY subject,domain",
                tuple(params),
            ).fetchall()
        return tuple(self._to_record(self._row_stored(tuple(row))) for row in rows)

    def interests(
        self,
        owner_core_id: UUID | str | None = None,
    ) -> tuple[PreferenceRecord, ...]:
        """Return only evidence-derived interest/hobby preferences."""
        return self.preferences(owner_core_id, domain="interest")

    def established_interests(
        self,
        owner_core_id: UUID | str | None = None,
    ) -> tuple[PreferenceRecord, ...]:
        return self.preferences(
            owner_core_id,
            domain="interest",
            state=PreferenceState.ESTABLISHED,
        )

    def refresh(
        self,
        *,
        now: datetime,
        owner_core_id: UUID | str | None = None,
    ) -> tuple[PreferenceRecord, ...]:
        """Apply time-based dormancy without creating new evidence."""
        owner = self._require_owner(owner_core_id)
        moment = _utc(now, "now")
        changed: list[PreferenceRecord] = []
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT preference_id,owner_core_id,subject,domain,state,stance,"
                "confidence,evidence_json,updated_at,revision FROM multicore_preference "
                "WHERE owner_core_id=? ORDER BY subject,domain",
                (str(owner),),
            ).fetchall()
            for row in rows:
                previous = self._row_stored(tuple(row))
                observations = db.execute(
                    "SELECT evidence_id,stance,evidence_state,observed_at,statement "
                    "FROM multicore_preference_observation "
                    "WHERE owner_core_id=? AND domain=? AND subject=? "
                    "ORDER BY observed_at,evidence_id",
                    (str(owner), previous.domain, previous.subject),
                ).fetchall()
                decoded = tuple(
                    (
                        UUID(str(item[0])),
                        bool(item[1]),
                        EvidenceState(str(item[2])),
                        datetime.fromisoformat(str(item[3])),
                        str(item[4]),
                    )
                    for item in observations
                )
                updated = self._derive(
                    owner=owner,
                    subject=previous.subject,
                    domain=previous.domain,
                    observations=decoded,
                    previous=previous,
                    now=moment,
                )
                if (
                    updated.state is not previous.state
                    or updated.stance is not previous.stance
                    or updated.confidence != previous.confidence
                    or updated.revision != previous.revision
                ):
                    self._upsert(db, updated)
                    changed.append(self._to_record(updated))
        return tuple(changed)

    def observations(
        self,
        owner_core_id: UUID | str | None = None,
        subject: str | None = None,
        *,
        domain: str = "preference",
    ) -> tuple[PreferenceObservation, ...]:
        owner = self._require_owner(owner_core_id)
        if subject is None:
            raise ValueError("subject is required")
        subject = _subject(subject)
        domain = _domain(domain)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT evidence_id,owner_core_id,subject,domain,stance,"
                "evidence_state,source,statement,observed_at "
                "FROM multicore_preference_observation "
                "WHERE owner_core_id=? AND domain=? AND subject=? "
                "ORDER BY observed_at,evidence_id",
                (str(owner), domain, subject),
            ).fetchall()
        return tuple(
            PreferenceObservation(
                evidence_id=UUID(str(row[0])),
                owner_core_id=UUID(str(row[1])),
                subject=str(row[2]),
                domain=str(row[3]),
                stance=bool(row[4]),
                evidence=EvidenceState(str(row[5])),
                source=str(row[6]),
                statement=str(row[7]),
                observed_at=datetime.fromisoformat(str(row[8])),
            )
            for row in rows
        )

    def corrections(
        self,
        owner_core_id: UUID | str | None = None,
        subject: str | None = None,
        *,
        domain: str = "preference",
    ) -> tuple[PreferenceCorrection, ...]:
        owner = self._require_owner(owner_core_id)
        if subject is None:
            raise ValueError("subject is required")
        subject = _subject(subject)
        domain = _domain(domain)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT correction_id,owner_core_id,subject,domain,prior_state,"
                "prior_stance,new_state,new_stance,reason,occurred_at,revision "
                "FROM multicore_preference_correction "
                "WHERE owner_core_id=? AND domain=? AND subject=? "
                "ORDER BY occurred_at,correction_id",
                (str(owner), domain, subject),
            ).fetchall()
        return tuple(
            PreferenceCorrection(
                correction_id=UUID(str(row[0])),
                owner_core_id=UUID(str(row[1])),
                subject=str(row[2]),
                domain=str(row[3]),
                prior_state=PreferenceState(str(row[4])),
                prior_stance=bool(row[5]),
                new_state=PreferenceState(str(row[6])),
                new_stance=bool(row[7]),
                reason=str(row[8]),
                occurred_at=datetime.fromisoformat(str(row[9])),
                revision=int(row[10]),
            )
            for row in rows
        )

    def close(self) -> None:
        return None

    def open(self) -> None:
        self._guard.validate()
