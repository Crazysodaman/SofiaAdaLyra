"""Independent-agency ledger: internal dilemmas and anticipations.

These records represent Sofía's own reasoning state, not facts about the
world: dilemmas are internal tension with an explicit resolution or
restraint; anticipations are expectations that may end in surprise. All
rows are append-only with evidence-linked revisions; nothing here grants
execution authority and nothing here is a forgiveness timer.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.social.principals import (
    PrincipalContext,
    SPARKS_PRINCIPAL_ID,
)


_TARGET = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,119}$")
_EVIDENCE = re.compile(r"^[a-z0-9][a-z0-9_.:@/-]{0,159}$")


class ConcurrencyError(RuntimeError):
    """Race or stale revision in an agency ledger write."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("agency timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bounded(value: object, *, name: str, minimum: int, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or len(value.strip()) < minimum
        or len(value.strip()) > maximum
    ):
        raise ValueError(
            f"{name} must be bounded text in {minimum}..{maximum} chars"
        )
    return value.strip()


class DilemmaStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    RETIRED = "retired"


class DilemmaChangeKind(str, Enum):
    OPEN = "open"
    RESOLVE = "resolve"
    RETIRE = "retire"


@dataclass(frozen=True, slots=True)
class DilemmaRecord:
    """One append-only revision of an internal dilemma."""

    dilemma_id: str
    revision: int
    question: str
    options: tuple[str, ...]
    chosen: str | None
    reasoning: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    change_kind: DilemmaChangeKind
    status: DilemmaStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.dilemma_id, str)
            or not self.dilemma_id.startswith("dilemma:")
            or len(self.dilemma_id) > 120
        ):
            raise ValueError("dilemma_id must be a canonical dilemma id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("dilemma revision must be a positive integer")
        _bounded(self.question, name="question", minimum=10, maximum=600)
        if type(self.options) is not tuple:
            raise TypeError("options must be a tuple")
        if (
            not self.options
            or len(self.options) > 5
            or len(set(self.options)) != len(self.options)
        ):
            raise ValueError("dilemma options must be 2..5 distinct choices")
        for option in self.options:
            _bounded(option, name="option", minimum=1, maximum=300)
        if type(self.evidence_refs) is not tuple:
            raise TypeError("evidence_refs must be a tuple")
        if (
            len(self.evidence_refs) > 8
            or any(
                not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None
                for value in self.evidence_refs
            )
        ):
            raise ValueError("dilemmma evidence must be 0..8 bounded refs")
        _bounded(self.reasoning, name="reasoning", minimum=1, maximum=600)
        if (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 160
        ):
            raise ValueError("audience_id must be bounded nonempty text")
        if not isinstance(self.change_kind, DilemmaChangeKind):
            raise TypeError("change_kind must be DilemmaChangeKind")
        if not isinstance(self.status, DilemmaStatus):
            raise TypeError("status must be DilemmaStatus")
        if self.status is DilemmaStatus.OPEN:
            if self.chosen is not None:
                raise ValueError("open dilemmas must not carry a choice")
            if self.change_kind is DilemmaChangeKind.RESOLVE:
                raise ValueError("open status cannot come from resolve")
        else:
            if self.status is DilemmaStatus.RESOLVED:
                if self.change_kind is not DilemmaChangeKind.RESOLVE:
                    raise ValueError("resolved status requires a resolve change")
                if self.chosen is None or self.chosen not in self.options:
                    raise ValueError("resolved dilemmas choose an option")
            else:
                if self.change_kind is not DilemmaChangeKind.RETIRE:
                    raise ValueError("retired status requires a retire change")
                if self.chosen is not None:
                    raise ValueError("retired dilemmas must not carry a choice")
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


class DilemmaStore:
    """Canonical append-only persistence for internal dilemmas."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agency_dilemma_revision (
                    dilemma_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    options TEXT NOT NULL,
                    chosen TEXT,
                    reasoning TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    change_kind TEXT NOT NULL CHECK(change_kind IN (
                        'open','resolve','retire')),
                    status TEXT NOT NULL CHECK(status IN (
                        'open','resolved','retired')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(dilemma_id,revision)
                );
                CREATE TABLE IF NOT EXISTS agency_dilemma_current (
                    dilemma_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: DilemmaRecord) -> tuple:
        return (
            record.dilemma_id, record.revision, record.question,
            json.dumps(list(record.options)),
            None if record.chosen is None else record.chosen,
            record.reasoning, json.dumps(list(record.evidence_refs)),
            record.audience_id, record.change_kind.value, record.status.value,
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> DilemmaRecord:
        return DilemmaRecord(
            dilemma_id=row["dilemma_id"],
            revision=int(row["revision"]),
            question=row["question"],
            options=tuple(json.loads(row["options"])),
            chosen=row["chosen"],
            reasoning=row["reasoning"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            audience_id=row["audience_id"],
            change_kind=DilemmaChangeKind(row["change_kind"]),
            status=DilemmaStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self, value: DilemmaRecord, *, expected_revision: int | None,
    ) -> DilemmaRecord:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM agency_dilemma_current WHERE dilemma_id=?",
                (value.dilemma_id,),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ConcurrencyError(
                        "dilemma already exists; reload before revising"
                    )
                if value.revision != 1 or value.change_kind is not (
                    DilemmaChangeKind.OPEN
                ):
                    raise ConcurrencyError(
                        "creating a dilemma requires open revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise ConcurrencyError(
                        "revision changed or dilemma is absent; reload first"
                    )
            db.execute(
                """INSERT INTO agency_dilemma_revision VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                self._encode(value),
            )
            if row is None:
                db.execute(
                    """INSERT INTO agency_dilemma_current(dilemma_id,revision)
                    VALUES(?,?)""",
                    (value.dilemma_id, value.revision),
                )
            else:
                db.execute(
                    """UPDATE agency_dilemma_current SET revision=?
                    WHERE dilemma_id=?""",
                    (value.revision, value.dilemma_id),
                )
        return value

    def current(self, dilemma_id: str) -> DilemmaRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM agency_dilemma_current c
                JOIN agency_dilemma_revision r
                ON r.dilemma_id=c.dilemma_id AND r.revision=c.revision
                WHERE c.dilemma_id=?""",
                (dilemma_id,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, dilemma_id: str) -> tuple[DilemmaRecord, ...]:
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT * FROM agency_dilemma_revision
                WHERE dilemma_id=? ORDER BY revision ASC""",
                (dilemma_id,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def open_dilemmas(self, *, audience_id: str, limit: int = 16) -> tuple[DilemmaRecord, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM agency_dilemma_current c
                JOIN agency_dilemma_revision r
                ON r.dilemma_id=c.dilemma_id AND r.revision=c.revision
                WHERE c.dilemma_id IN (
                    SELECT dilemma_id FROM agency_dilemma_current)
                AND r.audience_id=? AND r.status='open'
                ORDER BY r.recorded_at ASC LIMIT ?""",
                (audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_dilemma_id(self) -> str:
        return f"dilemma:{uuid4()}"


class AnticipationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SURPRISED = "surprised"
    WITHDRAWN = "withdrawn"


class AnticipationChangeKind(str, Enum):
    OPEN = "open"
    CONFIRM = "confirm"
    SURPRISE = "surprise"
    WITHDRAW = "withdraw"


@dataclass(frozen=True, slots=True)
class AnticipationRecord:
    """One append-only revision of an anticipation or surprise."""

    anticipation_id: str
    revision: int
    expectation: str
    about: str
    basis_refs: tuple[str, ...]
    outcome_note: str | None
    audience_id: str
    change_kind: AnticipationChangeKind
    status: AnticipationStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.anticipation_id, str)
            or not self.anticipation_id.startswith("anticipation:")
            or len(self.anticipation_id) > 140
        ):
            raise ValueError("anticipation_id must be canonical")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("anticipation revision must be a positive integer")
        _bounded(self.expectation, name="expectation", minimum=5, maximum=600)
        if isinstance(self.about, str) and _TARGET.fullmatch(self.about):
            pass
        else:
            raise ValueError("about must be a canonical bounded identifier")
        if type(self.basis_refs) is not tuple:
            raise TypeError("basis_refs must be a tuple")
        if (
            len(self.basis_refs) > 8
            or any(
                not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None
                for value in self.basis_refs
            )
        ):
            raise ValueError("anticipation basis must be 0..8 bounded refs")
        if self.outcome_note is not None:
            _bounded(
                self.outcome_note, name="outcome_note", minimum=1, maximum=600
            )
        if (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 160
        ):
            raise ValueError("audience_id must be bounded nonempty text")
        if not isinstance(self.change_kind, AnticipationChangeKind):
            raise TypeError("change_kind must be AnticipationChangeKind")
        if not isinstance(self.status, AnticipationStatus):
            raise TypeError("status must be AnticipationStatus")
        if self.status is AnticipationStatus.PENDING:
            if self.outcome_note is not None:
                raise ValueError("pending anticipations cannot carry outcomes")
            if self.change_kind is AnticipationChangeKind.CONFIRM:
                raise ValueError("pending status cannot come from confirm change")
            if self.change_kind is AnticipationChangeKind.SURPRISE:
                raise ValueError("pending status cannot come from surprise change")
        elif self.status is AnticipationStatus.WITHDRAWN:
            if self.change_kind is not AnticipationChangeKind.WITHDRAW:
                raise ValueError("withdrawn status requires a withdraw change")
            if self.outcome_note is not None:
                raise ValueError("withdrawn anticipations cannot carry outcomes")
        else:
            expected = (
                AnticipationChangeKind.CONFIRM
                if self.status is AnticipationStatus.CONFIRMED
                else AnticipationChangeKind.SURPRISE
            )
            if self.change_kind is not expected:
                raise ValueError(
                    "settled anticipations must match their change kind"
                )
            if self.outcome_note is None:
                raise ValueError(
                    "settled anticipations record what actually happened"
                )
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


class AnticipationStore:
    """Canonical append-only persistence for anticipations and surprises."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agency_anticipation_revision (
                    anticipation_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    expectation TEXT NOT NULL,
                    about TEXT NOT NULL,
                    basis_refs TEXT NOT NULL,
                    outcome_note TEXT,
                    audience_id TEXT NOT NULL,
                    change_kind TEXT NOT NULL CHECK(change_kind IN (
                        'open','confirm','surprise','withdraw')),
                    status TEXT NOT NULL CHECK(status IN (
                        'pending','confirmed','surprised','withdrawn')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(anticipation_id,revision)
                );
                CREATE TABLE IF NOT EXISTS agency_anticipation_current (
                    anticipation_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: AnticipationRecord) -> tuple:
        return (
            record.anticipation_id, record.revision, record.expectation,
            record.about, json.dumps(list(record.basis_refs)),
            record.outcome_note, record.audience_id,
            record.change_kind.value, record.status.value,
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> AnticipationRecord:
        return AnticipationRecord(
            anticipation_id=row["anticipation_id"],
            revision=int(row["revision"]),
            expectation=row["expectation"],
            about=row["about"],
            basis_refs=tuple(json.loads(row["basis_refs"])),
            outcome_note=row["outcome_note"],
            audience_id=row["audience_id"],
            change_kind=AnticipationChangeKind(row["change_kind"]),
            status=AnticipationStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self, value: AnticipationRecord, *, expected_revision: int | None,
    ) -> AnticipationRecord:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT revision FROM agency_anticipation_current
                WHERE anticipation_id=?""",
                (value.anticipation_id,),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ConcurrencyError(
                        "anticipation already exists; reload before revising"
                    )
                if value.revision != 1 or value.change_kind is not (
                    AnticipationChangeKind.OPEN
                ):
                    raise ConcurrencyError(
                        "creating an anticipation requires open revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise ConcurrencyError(
                        "revision changed or anticipation is absent; reload first"
                    )
            db.execute(
                """INSERT INTO agency_anticipation_revision
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                self._encode(value),
            )
            if row is None:
                db.execute(
                    """INSERT INTO agency_anticipation_current
                    (anticipation_id,revision) VALUES(?,?)""",
                    (value.anticipation_id, value.revision),
                )
            else:
                db.execute(
                    """UPDATE agency_anticipation_current SET revision=?
                    WHERE anticipation_id=?""",
                    (value.revision, value.anticipation_id),
                )
        return value

    def current(self, anticipation_id: str) -> AnticipationRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM agency_anticipation_current c
                JOIN agency_anticipation_revision r
                ON r.anticipation_id=c.anticipation_id AND r.revision=c.revision
                WHERE c.anticipation_id=?""",
                (anticipation_id,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, anticipation_id: str) -> tuple[AnticipationRecord, ...]:
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT * FROM agency_anticipation_revision
                WHERE anticipation_id=? ORDER BY revision ASC""",
                (anticipation_id,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def pending(self, *, audience_id: str, limit: int = 16) -> tuple[AnticipationRecord, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM agency_anticipation_current c
                JOIN agency_anticipation_revision r
                ON r.anticipation_id=c.anticipation_id AND r.revision=c.revision
                WHERE r.audience_id=? AND r.status='pending'
                ORDER BY r.recorded_at ASC LIMIT ?""",
                (audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def recent_surprises(
        self, *, audience_id: str, limit: int = 16,
    ) -> tuple[AnticipationRecord, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM agency_anticipation_current c
                JOIN agency_anticipation_revision r
                ON r.anticipation_id=c.anticipation_id AND r.revision=c.revision
                WHERE r.audience_id=? AND r.status='surprised'
                ORDER BY r.recorded_at DESC LIMIT ?""",
                (audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_anticipation_id(self) -> str:
        return f"anticipation:{uuid4()}"


def _require_sparks(principal: PrincipalContext) -> None:
    if not isinstance(principal, PrincipalContext):
        raise TypeError("principal must be a PrincipalContext")
    if principal.principal_id != SPARKS_PRINCIPAL_ID:
        raise PermissionError(
            "agency ledger writes require the authenticated Sparks principal"
        )


class AgencyService:
    """Owner-session-gated writer for the independent-agency ledger."""

    def __init__(
        self, dilemmas: DilemmaStore, anticipations: AnticipationStore,
    ) -> None:
        self._dilemmas = dilemmas
        self._anticipations = anticipations

    @property
    def dilemmas(self) -> DilemmaStore:
        return self._dilemmas

    @property
    def anticipations(self) -> AnticipationStore:
        return self._anticipations

    def record_dilemma(
        self, principal: PrincipalContext, *, question: str,
        options: tuple[str, ...], reasoning: str,
        evidence_refs: tuple[str, ...] = (), audience_id: str,
        recorded_at: datetime | None = None,
    ) -> DilemmaRecord:
        _require_sparks(principal)
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = DilemmaRecord(
            dilemma_id=self._dilemmas.new_dilemma_id(),
            revision=1,
            question=question,
            options=options,
            chosen=None,
            reasoning=reasoning,
            evidence_refs=tuple(evidence_refs),
            audience_id=audience_id,
            change_kind=DilemmaChangeKind.OPEN,
            status=DilemmaStatus.OPEN,
            recorded_at=stamp,
        )
        return self._dilemmas.hold(record, expected_revision=None)

    def resolve_dilemma(
        self, principal: PrincipalContext, *, dilemma_id: str,
        expected_revision: int, chosen: str, reasoning: str,
        evidence_refs: tuple[str, ...] = (),
        recorded_at: datetime | None = None,
    ) -> DilemmaRecord:
        _require_sparks(principal)
        history = self._dilemmas.history(dilemma_id)
        if not history:
            raise LookupError("unknown dilemma id")
        latest = history[-1]
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = DilemmaRecord(
            dilemma_id=latest.dilemma_id,
            revision=expected_revision + 1,
            question=latest.question,
            options=latest.options,
            chosen=chosen,
            reasoning=reasoning,
            evidence_refs=tuple(evidence_refs),
            audience_id=latest.audience_id,
            change_kind=DilemmaChangeKind.RESOLVE,
            status=DilemmaStatus.RESOLVED,
            recorded_at=stamp,
        )
        return self._dilemmas.hold(record, expected_revision=expected_revision)

    def retire_dilemma(
        self, principal: PrincipalContext, *, dilemma_id: str,
        expected_revision: int, reasoning: str,
        recorded_at: datetime | None = None,
    ) -> DilemmaRecord:
        _require_sparks(principal)
        history = self._dilemmas.history(dilemma_id)
        if not history:
            raise LookupError("unknown dilemma id")
        latest = history[-1]
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = DilemmaRecord(
            dilemma_id=latest.dilemma_id,
            revision=expected_revision + 1,
            question=latest.question,
            options=latest.options,
            chosen=None,
            reasoning=reasoning,
            evidence_refs=(),
            audience_id=latest.audience_id,
            change_kind=DilemmaChangeKind.RETIRE,
            status=DilemmaStatus.RETIRED,
            recorded_at=stamp,
        )
        return self._dilemmas.hold(record, expected_revision=expected_revision)

    def anticipate(
        self, principal: PrincipalContext, *, expectation: str, about: str,
        basis_refs: tuple[str, ...] = (), audience_id: str,
        recorded_at: datetime | None = None,
    ) -> AnticipationRecord:
        _require_sparks(principal)
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = AnticipationRecord(
            anticipation_id=self._anticipations.new_anticipation_id(),
            revision=1,
            expectation=expectation,
            about=about,
            basis_refs=tuple(basis_refs),
            outcome_note=None,
            audience_id=audience_id,
            change_kind=AnticipationChangeKind.OPEN,
            status=AnticipationStatus.PENDING,
            recorded_at=stamp,
        )
        return self._anticipations.hold(record, expected_revision=None)

    def settle(
        self, principal: PrincipalContext, *, anticipation_id: str,
        expected_revision: int, outcome_note: str,
        recorded_at: datetime | None = None,
    ) -> AnticipationRecord:
        """Settle a pending anticipation as confirmed or surprised."""
        _require_sparks(principal)
        history = self._anticipations.history(anticipation_id)
        if not history:
            raise LookupError("unknown anticipation id")
        latest = history[-1]
        if latest.status is not AnticipationStatus.PENDING:
            raise ValueError("only pending anticipations can settle")
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        change_kind = _classify_outcome(latest, outcome_note)
        record = AnticipationRecord(
            anticipation_id=latest.anticipation_id,
            revision=expected_revision + 1,
            expectation=latest.expectation,
            about=latest.about,
            basis_refs=latest.basis_refs,
            outcome_note=outcome_note,
            audience_id=latest.audience_id,
            change_kind=change_kind,
            status=(
                AnticipationStatus.CONFIRMED
                if change_kind is AnticipationChangeKind.CONFIRM
                else AnticipationStatus.SURPRISED
            ),
            recorded_at=stamp,
        )
        return self._anticipations.hold(record, expected_revision=expected_revision)

    def withdraw_anticipation(
        self, principal: PrincipalContext, *, anticipation_id: str,
        expected_revision: int,
        recorded_at: datetime | None = None,
    ) -> AnticipationRecord:
        _require_sparks(principal)
        history = self._anticipations.history(anticipation_id)
        if not history:
            raise LookupError("unknown anticipation id")
        latest = history[-1]
        if latest.status is not AnticipationStatus.PENDING:
            raise ValueError("only pending anticipations can withdraw")
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = AnticipationRecord(
            anticipation_id=latest.anticipation_id,
            revision=expected_revision + 1,
            expectation=latest.expectation,
            about=latest.about,
            basis_refs=latest.basis_refs,
            outcome_note=None,
            audience_id=latest.audience_id,
            change_kind=AnticipationChangeKind.WITHDRAW,
            status=AnticipationStatus.WITHDRAWN,
            recorded_at=stamp,
        )
        return self._anticipations.hold(
            record, expected_revision=expected_revision
        )


def _classify_outcome(
    latest: AnticipationRecord, outcome_note: str,
) -> AnticipationChangeKind:
    """Outcomes carry the confirm change kind by default; surprise is explicit."""
    note = outcome_note.strip().lower()
    if note.startswith("not as expected") or note.startswith("surprise:"):
        return AnticipationChangeKind.SURPRISE
    return AnticipationChangeKind.CONFIRM
