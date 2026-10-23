"""Bounded module-need proposals: evaluate, propose, defer or drop.

Sofía's initiative in her own capability development stays inside Core
ownership: she can record a genuine capability need, check the
alternatives her current modules and observations actually offer, and
record a typed proposal — or conclude that no module is needed and
abandon the idea without pretending a capability appeared. A proposal is
a REQUEST for authorization, never a grant; the Platform independently
decides installation, execution, resource use and verification.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import re
import sqlite3
from uuid import uuid4

from sofia.modules.self_model import CapabilitySelfModel, Grounding
from sofia.social.model import PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_PROPOSAL_ID = re.compile(r"^moduleproposal:[0-9a-f-]{36}$")
_NEED_ID = re.compile(r"^[a-z0-9][a-z0-9_.:@/-]{0,159}$")


class NeedOrigin(str, Enum):
    """Why Sofía concluded a capability would genuinely help."""

    GOAL = "goal"
    INTEREST = "interest"
    REPEATED_TASK = "repeated_task"
    BROKEN_MODULE = "broken_module"
    MAINTENANCE = "maintenance"
    CURIOSITY = "curiosity"


class ProposalAction(str, Enum):
    INSTALL = "install"
    IMPROVE = "improve"
    DEVELOP = "develop"
    REPLACE = "replace"
    MAINTAIN = "maintain"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    DEFERRED = "deferred"
    ABANDONED = "abandoned"
    NO_MODULE_NEEDED = "no_module_needed"
    SUPERSEDED = "superseded"


class ProposalError(RuntimeError):
    """Race or stale revision in a module proposal write."""


def _aware(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("proposal timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ModuleNeed:
    """A bounded, personally motivated capability need."""

    need_id: str
    origin: NeedOrigin
    subject: str
    motivation: str
    evidence_refs: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.need_id, str) or _NEED_ID.fullmatch(
            self.need_id
        ) is None:
            raise ValueError("need_id must be a bounded canonical id")
        if not isinstance(self.origin, NeedOrigin):
            raise TypeError("origin must be a NeedOrigin")
        if not isinstance(self.subject, str) or not (
            self.subject.strip()
        ) or len(self.subject.strip()) > 160:
            raise ValueError("subject must be bounded nonempty text")
        if (
            not isinstance(self.motivation, str)
            or not self.motivation.strip()
            or len(self.motivation.strip()) > 600
        ):
            raise ValueError("motivation must be bounded nonempty text")
        if type(self.evidence_refs) is not tuple or any(
            not isinstance(ref, str) or _NEED_ID.fullmatch(ref) is None
            for ref in self.evidence_refs
        ):
            raise ValueError("evidence_refs must be bounded canonical ids")
        if not self.evidence_refs:
            raise ValueError("a need without registered evidence is a claim")
        if _aware(self.created_at) != self.created_at:
            raise ValueError("created_at must be exact UTC")


@dataclass(frozen=True, slots=True)
class NeedEvaluation:
    """Outcome of the bounded installed-first comparison."""

    installed_alternatives: tuple[str, ...]
    candidate_matches: tuple[str, ...]
    unavailable_matches: tuple[str, ...]
    evidence_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleProposalRecord:
    """Sofía's typed proposal; authorization belongs to the Platform."""

    proposal_id: str
    revision: int
    need_id: str
    target_module: str
    action: ProposalAction
    status: ProposalStatus
    motivation: str
    alternatives: tuple[str, ...]
    benefits: str
    risks: str
    permissions_needed: tuple[str, ...]
    resource_notes: str
    outcome_refs: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or _PROPOSAL_ID.fullmatch(
            self.proposal_id
        ) is None:
            raise ValueError("proposal_id must be a canonical uuid id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("proposal revision must be a positive int")
        if not isinstance(self.need_id, str) or _NEED_ID.fullmatch(
            self.need_id
        ) is None:
            raise ValueError("need_id must be a bounded canonical id")
        if not isinstance(self.target_module, str) or not self.target_module.strip() or len(
            self.target_module.strip()
        ) > 120:
            raise ValueError("target_module must be bounded nonempty text")
        if not isinstance(self.action, ProposalAction):
            raise TypeError("action must be a ProposalAction")
        if not isinstance(self.status, ProposalStatus):
            raise TypeError("status must be a ProposalStatus")
        for label in ("motivation", "benefits", "risks", "resource_notes"):
            value = getattr(self, label)
            if not isinstance(value, str):
                raise TypeError(f"{label} must be text")
        if not self.motivation.strip() or len(self.motivation.strip()) > 600:
            raise ValueError("motivation must be bounded nonempty text")
        for label in ("benefits", "risks", "resource_notes"):
            value = getattr(self, label).strip()
            if len(value) > 500:
                raise ValueError(f"{label} must be bounded (<=500)")
        if type(self.permissions_needed) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.permissions_needed
        ):
            raise TypeError("permissions_needed must be a tuple of names")
        if type(self.alternatives) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.alternatives
        ):
            raise TypeError("alternatives must be a tuple of names")
        if type(self.outcome_refs) is not tuple or any(
            not isinstance(ref, str) or _NEED_ID.fullmatch(ref) is None
            for ref in self.outcome_refs
        ):
            raise ValueError("outcome_refs must be bounded canonical ids")
        if self.revision == 1 and self.status is not ProposalStatus.PROPOSED:
            raise ValueError("proposal origin is always recorded proposed")
        if _aware(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC")


class ModuleProposalStore:
    """Canonical persistence for Sofía's own capability proposals."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS modules_proposal_revision (
                    proposal_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    need_id TEXT NOT NULL,
                    target_module TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN (
                        'install','improve','develop','replace','maintain')),
                    status TEXT NOT NULL CHECK(status IN (
                        'proposed','deferred','abandoned',
                        'no_module_needed','superseded')),
                    motivation TEXT NOT NULL,
                    alternatives TEXT NOT NULL,
                    benefits TEXT NOT NULL,
                    risks TEXT NOT NULL,
                    permissions_needed TEXT NOT NULL,
                    resource_notes TEXT NOT NULL,
                    outcome_refs TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(proposal_id,revision)
                );
                CREATE TABLE IF NOT EXISTS modules_proposal_current (
                    proposal_id TEXT PRIMARY KEY,
                    need_id TEXT NOT NULL,
                    target_module TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(need_id,target_module,revision)
                );
                CREATE INDEX IF NOT EXISTS modules_proposal_need
                    ON modules_proposal_current(need_id);
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: ModuleProposalRecord) -> tuple:
        return (
            record.proposal_id,
            record.revision,
            record.need_id,
            record.target_module,
            record.action.value,
            record.status.value,
            record.motivation,
            json.dumps(list(record.alternatives)),
            record.benefits,
            record.risks,
            json.dumps(list(record.permissions_needed)),
            record.resource_notes,
            json.dumps(list(record.outcome_refs)),
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> ModuleProposalRecord:
        return ModuleProposalRecord(
            proposal_id=row["proposal_id"],
            revision=int(row["revision"]),
            need_id=row["need_id"],
            target_module=row["target_module"],
            action=ProposalAction(row["action"]),
            status=ProposalStatus(row["status"]),
            motivation=row["motivation"],
            alternatives=tuple(json.loads(row["alternatives"])),
            benefits=row["benefits"],
            risks=row["risks"],
            permissions_needed=tuple(
                json.loads(row["permissions_needed"])
            ),
            resource_notes=row["resource_notes"],
            outcome_refs=tuple(json.loads(row["outcome_refs"])),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def persist(
        self, record: ModuleProposalRecord, *, expected_revision: int | None,
    ) -> ModuleProposalRecord:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT proposal_id,revision FROM modules_proposal_current
                WHERE need_id=? AND target_module=?""",
                (record.need_id, record.target_module),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ProposalError(
                        "a proposal already exists for this need and target;"
                        " revise it instead"
                    )
                if record.revision != 1:
                    raise ProposalError(
                        "creating a proposal requires revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise ProposalError(
                        "revision changed or proposal is absent; reload first"
                    )
                if row["proposal_id"] != record.proposal_id:
                    raise ProposalError(
                        "proposal identity changed; reload before revising"
                    )
            db.execute(
                """INSERT INTO modules_proposal_revision VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                self._encode(record),
            )
            if row is None:
                db.execute(
                    """INSERT INTO modules_proposal_current
                    (proposal_id,need_id,target_module,revision)
                    VALUES(?,?,?,?)""",
                    (record.proposal_id, record.need_id,
                     record.target_module, record.revision),
                )
            else:
                db.execute(
                    """UPDATE modules_proposal_current SET revision=?
                    WHERE proposal_id=?""",
                    (record.revision, record.proposal_id),
                )
        return record

    def current(
        self, *, need_id: str, target_module: str,
    ) -> ModuleProposalRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM modules_proposal_current c
                JOIN modules_proposal_revision r
                ON r.proposal_id=c.proposal_id AND r.revision=c.revision
                WHERE c.need_id=? AND c.target_module=?""",
                (need_id, target_module),
            ).fetchone()
        return None if row is None else self._decode(row)

    def open_proposals(self, *, limit: int = 16) -> tuple:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM modules_proposal_current c
                JOIN modules_proposal_revision r
                ON r.proposal_id=c.proposal_id AND r.revision=c.revision
                WHERE r.status IN ('proposed','deferred')
                ORDER BY r.recorded_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_proposal_id(self) -> str:
        return f"moduleproposal:{uuid4()}"


class ModuleProposalService:
    """Owner-session-gated writer for Sofía's capability proposals."""

    def __init__(
        self,
        store: ModuleProposalStore,
        self_model: CapabilitySelfModel,
    ) -> None:
        if not isinstance(self_model, CapabilitySelfModel):
            raise TypeError(
                "proposals evaluate against a CapabilitySelfModel"
            )
        self._store = store
        self._self_model = self_model

    @property
    def store(self) -> ModuleProposalStore:
        return self._store

    @property
    def self_model(self) -> CapabilitySelfModel:
        return self._self_model

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "module proposal writes require the authenticated owner"
            )

    def evaluate_need(
        self, need: ModuleNeed, *, capability_terms: tuple[str, ...],
    ) -> NeedEvaluation:
        """Installed-first comparison using observed rows only."""
        if not isinstance(need, ModuleNeed):
            raise TypeError("need must be a ModuleNeed")
        if not capability_terms or any(
            not isinstance(term, str) or not term.strip()
            for term in capability_terms
        ):
            raise ValueError("capability terms must be nonempty")
        wanted = [term.strip().lower() for term in capability_terms]
        installed_alternatives: list[str] = []
        candidate_matches: list[str] = []
        unavailable_matches: list[str] = []
        evidence_lines: list[str] = [
            f"need:{need.need_id} origin={need.origin.value}",
        ]
        for row in self._self_model.project(
            now=need.created_at
        ):
            capabilities = [
                item.lower() for item in row.capabilities
            ]
            matches = [
                capability
                for capability in capabilities
                if any(
                    term in capability for term in wanted
                )
            ]
            if not matches:
                continue
            if row.installed is Grounding.YES:
                if row.available is Grounding.YES:
                    installed_alternatives.append(row.module_id)
                else:
                    unavailable_matches.append(row.module_id)
            elif row.discovered is Grounding.YES:
                candidate_matches.append(row.module_id)
            evidence_lines.append(
                f"{row.module_id} matched" + "/".join(matches)
                + (
                    "; unavailable"
                    if row.available is Grounding.NO
                    else ""
                )
            )
        return NeedEvaluation(
            installed_alternatives=tuple(sorted(installed_alternatives)),
            candidate_matches=tuple(sorted(candidate_matches)),
            unavailable_matches=tuple(sorted(unavailable_matches)),
            evidence_lines=tuple(evidence_lines),
        )

    def propose(
        self,
        principal: PrincipalContext,
        *,
        need: ModuleNeed,
        target_module: str,
        action: ProposalAction,
        evaluation: NeedEvaluation,
        benefits: str,
        risks: str,
        permissions_needed: tuple[str, ...] = (),
        resource_notes: str = "",
        recorded_at: datetime | None = None,
    ) -> ModuleProposalRecord:
        self._require_sparks(principal)
        if action is ProposalAction.INSTALL and (
            evaluation.installed_alternatives
        ):
            raise ValueError(
                "an installed verified alternative usually dispenses with"
                " a new installation"
            )
        stamp = _aware(recorded_at) if recorded_at is not None else _aware(
            datetime.now(timezone.utc)
        )
        record = ModuleProposalRecord(
            proposal_id=self._store.new_proposal_id(),
            revision=1,
            need_id=need.need_id,
            target_module=target_module,
            action=action,
            status=ProposalStatus.PROPOSED,
            motivation=need.motivation,
            alternatives=(
                evaluation.installed_alternatives
                + evaluation.unavailable_matches
            ),
            benefits=benefits,
            risks=risks,
            permissions_needed=tuple(permissions_needed),
            resource_notes=resource_notes,
            outcome_refs=(),
            recorded_at=stamp,
        )
        return self._store.persist(record, expected_revision=None)

    def resolve(
        self,
        principal: PrincipalContext,
        *,
        need_id: str,
        target_module: str,
        expected_revision: int,
        status: ProposalStatus,
        note: str,
        outcome_refs: tuple[str, ...] = (),
        recorded_at: datetime | None = None,
    ) -> ModuleProposalRecord:
        self._require_sparks(principal)
        if status is ProposalStatus.PROPOSED:
            raise ValueError("resolution must move past the proposed state")
        if status not in (
            ProposalStatus.DEFERRED,
            ProposalStatus.ABANDONED,
            ProposalStatus.NO_MODULE_NEEDED,
            ProposalStatus.SUPERSEDED,
        ):
            raise ValueError(
                "resolved statuses are deferred, abandoned, no-module-needed"
                " or superseded; Platform results arrive as observations"
            )
        if type(outcome_refs) is not tuple or any(
            not isinstance(ref, str) or _NEED_ID.fullmatch(ref) is None
            for ref in outcome_refs
        ):
            raise ValueError("outcome_refs must be bounded canonical ids")
        current = self._store.current(
            need_id=need_id, target_module=target_module,
        )
        if current is None:
            raise LookupError("unknown proposal for this need and target")
        if current.revision != expected_revision:
            raise ProposalError("revision changed; reload before resolving")
        if not note.strip() or len(note.strip()) > 500:
            raise ValueError("resolution note must be bounded nonempty text")
        stamp = _aware(recorded_at) if recorded_at is not None else _aware(
            datetime.now(timezone.utc)
        )
        record = ModuleProposalRecord(
            proposal_id=current.proposal_id,
            revision=expected_revision + 1,
            need_id=current.need_id,
            target_module=current.target_module,
            action=current.action,
            status=status,
            motivation=current.motivation,
            alternatives=current.alternatives,
            benefits=current.benefits,
            risks=current.risks,
            permissions_needed=current.permissions_needed,
            resource_notes=current.resource_notes,
            outcome_refs=tuple(outcome_refs),
            recorded_at=stamp,
        )
        return self._store.persist(
            record, expected_revision=expected_revision,
        )
