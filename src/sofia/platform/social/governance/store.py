"""Canonical SQLite persistence for voluntary Core governance.

Only one writer owns the canonical Platform state file.  Governance rows are
additive in that same file; there is no sidecar database.  Every mutation is an
immediate transaction and writes exact audit evidence.  Audit evidence is
recorded both in the existing SAFE ``safe_audit_event`` hash chain (via
``AuditChain``) and in the governance append-only evidence table.

Ballots are deliberately named.  The canonical writer can always map a ballot
to its Core; V1 does not claim cryptographic ballot secrecy.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping
from uuid import UUID, uuid4

from sofia.platform.safe.audit import AuditChain
from sofia.platform.social.governance.contracts import (
    Ballot,
    BallotChoice,
    CoordinatorStatus,
    CoordinatorTerm,
    DecisionProcedure,
    GovernanceConflict,
    GovernanceError,
    GovernanceGroup,
    GovernancePolicy,
    GroupLifecycle,
    GroupMember,
    MemberState,
    Nomination,
    Proposal,
    ProposalStatus,
    ProposalType,
    Resolution,
    ResolutionOutcome,
    TallyResult,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_SCHEMA = """
CREATE TABLE IF NOT EXISTS governance_group (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    room_ids_json TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    roster_epoch INTEGER NOT NULL CHECK(roster_epoch >= 1),
    lifecycle TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    founding_member_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS governance_member (
    group_id TEXT NOT NULL,
    core_id TEXT NOT NULL,
    state TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    joined_epoch INTEGER NOT NULL CHECK(joined_epoch >= 1),
    governance_opted_in INTEGER NOT NULL CHECK(governance_opted_in IN (0, 1)),
    consented_policy_digest TEXT,
    PRIMARY KEY (group_id, core_id),
    FOREIGN KEY (group_id) REFERENCES governance_group(group_id)
);

CREATE TABLE IF NOT EXISTS governance_proposal (
    proposal_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    proposer_core_id TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    procedure TEXT NOT NULL,
    electorate_json TEXT NOT NULL,
    roster_epoch INTEGER NOT NULL CHECK(roster_epoch >= 1),
    opens_at TEXT NOT NULL,
    closes_at TEXT NOT NULL,
    quorum INTEGER NOT NULL CHECK(quorum >= 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    candidate_core_ids_json TEXT NOT NULL,
    binding INTEGER NOT NULL CHECK(binding IN (0, 1)),
    coordinator_term_days INTEGER NOT NULL,
    FOREIGN KEY (group_id) REFERENCES governance_group(group_id)
);

CREATE INDEX IF NOT EXISTS governance_proposal_group
    ON governance_proposal(group_id, status, closes_at);

CREATE TABLE IF NOT EXISTS governance_nomination (
    nomination_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    candidate_core_id TEXT NOT NULL,
    nominated_by_core_id TEXT NOT NULL,
    accepted INTEGER CHECK(accepted IS NULL OR accepted IN (0, 1)),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(proposal_id, candidate_core_id),
    FOREIGN KEY (proposal_id) REFERENCES governance_proposal(proposal_id)
);

CREATE TABLE IF NOT EXISTS governance_ballot (
    ballot_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    core_id TEXT NOT NULL,
    choice TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    idempotency_key TEXT NOT NULL,
    cast_at TEXT NOT NULL,
    approvals_json TEXT NOT NULL,
    UNIQUE(proposal_id, core_id),
    UNIQUE(idempotency_key),
    FOREIGN KEY (proposal_id) REFERENCES governance_proposal(proposal_id)
);

CREATE TABLE IF NOT EXISTS governance_ballot_history (
    history_id TEXT PRIMARY KEY,
    ballot_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    core_id TEXT NOT NULL,
    choice TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    idempotency_key TEXT NOT NULL,
    cast_at TEXT NOT NULL,
    approvals_json TEXT NOT NULL,
    superseded_at TEXT,
    superseded_by TEXT,
    UNIQUE(proposal_id, core_id, revision),
    UNIQUE(idempotency_key),
    FOREIGN KEY (proposal_id) REFERENCES governance_proposal(proposal_id)
);

CREATE INDEX IF NOT EXISTS governance_ballot_history_proposal
    ON governance_ballot_history(proposal_id, core_id, revision);

CREATE TABLE IF NOT EXISTS governance_resolution (
    resolution_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    group_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    tally_json TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    coordinator_core_id TEXT,
    term_starts_at TEXT,
    term_expires_at TEXT,
    FOREIGN KEY (proposal_id) REFERENCES governance_proposal(proposal_id),
    FOREIGN KEY (group_id) REFERENCES governance_group(group_id)
);

CREATE TABLE IF NOT EXISTS governance_coordinator_term (
    term_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    core_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    UNIQUE(proposal_id),
    FOREIGN KEY (group_id) REFERENCES governance_group(group_id),
    FOREIGN KEY (proposal_id) REFERENCES governance_proposal(proposal_id)
);

CREATE INDEX IF NOT EXISTS governance_coordinator_active
    ON governance_coordinator_term(group_id, status, expires_at);

CREATE TABLE IF NOT EXISTS governance_audit_event (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    group_id TEXT,
    proposal_id TEXT,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    idempotency_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS governance_audit_group
    ON governance_audit_event(group_id, sequence);
"""

_GENESIS = "0" * 64


def _iso(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise GovernanceError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_json(value: str) -> object:
    return json.loads(value)


def _canonical_hash(payload: dict[str, object]) -> str:
    raw = _json(payload).encode("utf-8")
    return sha256(b"aegis.social.governance.audit.v1\x00" + raw).hexdigest()


class GovernanceStore:
    """The single canonical governance persistence writer."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        self._initialize()

    def _initialize(self) -> None:
        with self.transaction() as db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def reader(self):
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Audit evidence
    # ------------------------------------------------------------------
    def _append_audit(
        self,
        db: sqlite3.Connection,
        *,
        actor_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: dict[str, object],
        group_id: UUID | str | None = None,
        proposal_id: UUID | str | None = None,
        event_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise GovernanceError("actor_id must be nonempty")
        if not isinstance(event_type, str) or not event_type.strip():
            raise GovernanceError("event_type must be nonempty")
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not idempotency_key.strip()
        ):
            raise GovernanceError("idempotency_key must be nonempty text")
        stamp = occurred_at.astimezone(timezone.utc)
        identifier = event_id or f"gov-event:{uuid4()}"
        group_text = None if group_id is None else str(group_id)
        proposal_text = None if proposal_id is None else str(proposal_id)
        payload_json = _json(payload)

        # Reuse the existing canonical append-only SAFE chain atomically.
        self.audit.append_in_transaction(
            db,
            actor_id=actor_id,
            event_type=event_type,
            payload=payload,
            occurred_at=stamp,
            event_id=identifier,
        )

        row = db.execute(
            "SELECT event_hash FROM governance_audit_event "
            "ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = _GENESIS if row is None else row[0]
        event_hash = _canonical_hash(
            {
                "event_id": identifier,
                "occurred_at": _iso(stamp),
                "actor_id": actor_id,
                "event_type": event_type,
                "group_id": group_text,
                "proposal_id": proposal_text,
                "payload_json": payload_json,
                "previous_hash": previous,
            }
        )
        db.execute(
            """
            INSERT INTO governance_audit_event (
                event_id, occurred_at, actor_id, event_type, group_id,
                proposal_id, payload_json, previous_hash, event_hash,
                idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier, _iso(stamp), actor_id, event_type, group_text,
                proposal_text, payload_json, previous, event_hash,
                idempotency_key,
            ),
        )
        return event_hash

    def append_audit(
        self,
        *,
        actor_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: dict[str, object],
        group_id: UUID | str | None = None,
        proposal_id: UUID | str | None = None,
        event_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        with self.transaction() as db:
            return self._append_audit(
                db,
                actor_id=actor_id,
                event_type=event_type,
                occurred_at=occurred_at,
                payload=payload,
                group_id=group_id,
                proposal_id=proposal_id,
                event_id=event_id,
                idempotency_key=idempotency_key,
            )

    def lookup_idempotency(self, idempotency_key: str) -> dict[str, object] | None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise GovernanceError("idempotency_key must be nonempty text")
        with self.reader() as db:
            row = db.execute(
                "SELECT event_type, payload_json FROM governance_audit_event "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "event_type": row["event_type"],
            "payload": _load_json(row["payload_json"]),
        }

    def audit_events(self, group_id: UUID | str) -> tuple[dict[str, object], ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_audit_event WHERE group_id=? "
                "ORDER BY sequence ASC",
                (str(group_id),),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def verify_audit(self) -> tuple[bool, str | None]:
        with self.reader() as db:
            previous = _GENESIS
            rows = db.execute(
                "SELECT * FROM governance_audit_event ORDER BY sequence ASC"
            )
            for row in rows:
                if row["previous_hash"] != previous:
                    return False, f"governance audit previous-hash mismatch at {row['event_id']}"
                expected = _canonical_hash(
                    {
                        "event_id": row["event_id"],
                        "occurred_at": row["occurred_at"],
                        "actor_id": row["actor_id"],
                        "event_type": row["event_type"],
                        "group_id": row["group_id"],
                        "proposal_id": row["proposal_id"],
                        "payload_json": row["payload_json"],
                        "previous_hash": row["previous_hash"],
                    }
                )
                if row["event_hash"] != expected:
                    return False, f"governance audit hash mismatch at {row['event_id']}"
                previous = row["event_hash"]
            ok, reason = self.audit.verify()
            if not ok:
                return False, reason
        return True, None

    # ------------------------------------------------------------------
    # Groups and membership
    # ------------------------------------------------------------------
    @staticmethod
    def _write_group(db: sqlite3.Connection, group: GovernanceGroup) -> None:
        db.execute(
            """
            INSERT INTO governance_group (
                group_id, name, purpose, room_ids_json, revision, roster_epoch,
                lifecycle, policy_json, policy_digest,
                founding_member_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(group.group_id), group.name, group.purpose,
                _json(list(group.room_ids)), group.revision,
                group.roster_epoch, group.lifecycle.value,
                _json(group.policy.to_payload()), group.policy_digest,
                _json([str(item) for item in group.founding_member_ids]),
                _iso(group.created_at), _iso(group.updated_at),
            ),
        )
        for member in group.members:
            db.execute(
                """
                INSERT INTO governance_member (
                    group_id, core_id, state, joined_at, joined_epoch,
                    governance_opted_in, consented_policy_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(group.group_id), str(member.core_id), member.state.value,
                    _iso(member.joined_at), member.joined_epoch,
                    1 if member.governance_opted_in else 0,
                    member.consented_policy_digest,
                ),
            )

    def save_group(
        self,
        group: GovernanceGroup,
        *,
        actor_id: str,
        occurred_at: datetime,
        expected_revision: int | None = None,
        event_type: str = "governance.group.saved",
        idempotency_key: str | None = None,
        extra_payload: Mapping[str, object] | None = None,
    ) -> GovernanceGroup:
        if not isinstance(group, GovernanceGroup):
            raise TypeError("group must be GovernanceGroup")
        try:
            with self.transaction() as db:
                row = db.execute(
                    "SELECT revision FROM governance_group WHERE group_id=?",
                    (str(group.group_id),),
                ).fetchone()
                if row is None:
                    if expected_revision not in (None, 1) or group.revision != 1:
                        raise GovernanceConflict("new group must begin at revision 1")
                    self._write_group(db, group)
                else:
                    old_revision = int(row["revision"])
                    if (
                        expected_revision is not None
                        and old_revision != expected_revision
                    ):
                        raise GovernanceConflict("group revision changed concurrently")
                    if group.revision != old_revision + 1:
                        raise GovernanceConflict("group update must advance revision by one")
                    db.execute(
                        """
                        UPDATE governance_group SET
                            name=?, purpose=?, room_ids_json=?, revision=?,
                            roster_epoch=?, lifecycle=?, policy_json=?,
                            policy_digest=?, founding_member_ids_json=?,
                            created_at=?, updated_at=?
                        WHERE group_id=?
                        """,
                        (
                            group.name, group.purpose, _json(list(group.room_ids)),
                            group.revision, group.roster_epoch, group.lifecycle.value,
                            _json(group.policy.to_payload()), group.policy_digest,
                            _json([str(item) for item in group.founding_member_ids]),
                            _iso(group.created_at), _iso(group.updated_at),
                            str(group.group_id),
                        ),
                    )
                    db.execute(
                        "DELETE FROM governance_member WHERE group_id=?",
                        (str(group.group_id),),
                    )
                    for member in group.members:
                        db.execute(
                            """
                            INSERT INTO governance_member (
                                group_id, core_id, state, joined_at, joined_epoch,
                                governance_opted_in, consented_policy_digest
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(group.group_id), str(member.core_id),
                                member.state.value, _iso(member.joined_at),
                                member.joined_epoch,
                                1 if member.governance_opted_in else 0,
                                member.consented_policy_digest,
                            ),
                        )
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    payload={
                        "group_id": str(group.group_id),
                        "revision": group.revision,
                        "roster_epoch": group.roster_epoch,
                        "lifecycle": group.lifecycle.value,
                        "policy_digest": group.policy_digest,
                        "eligible_member_ids": [
                            str(item) for item in group.eligible_member_ids()
                        ],
                        **({} if extra_payload is None else dict(extra_payload)),
                    },
                    group_id=group.group_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict("governance idempotency key was already used") from exc
        return group

    @staticmethod
    def _group_from_rows(
        row: sqlite3.Row, member_rows: Iterable[sqlite3.Row]
    ) -> GovernanceGroup:
        policy_data = _load_json(row["policy_json"])
        policy = GovernancePolicy(
            procedure=DecisionProcedure(policy_data["procedure"]),
            quorum_numerator=int(policy_data["quorum_numerator"]),
            quorum_denominator=int(policy_data["quorum_denominator"]),
            minimum_leadership_electorate=int(
                policy_data["minimum_leadership_electorate"]
            ),
            allow_coordinator=bool(policy_data["allow_coordinator"]),
            coordinator_term_days=int(policy_data["coordinator_term_days"]),
            require_founding_unanimity=bool(
                policy_data["require_founding_unanimity"]
            ),
        )
        members = tuple(
            GroupMember(
                core_id=UUID(item["core_id"]),
                state=MemberState(item["state"]),
                joined_at=_dt(item["joined_at"]),
                joined_epoch=int(item["joined_epoch"]),
                governance_opted_in=bool(item["governance_opted_in"]),
                consented_policy_digest=item["consented_policy_digest"],
            )
            for item in member_rows
        )
        return GovernanceGroup(
            group_id=UUID(row["group_id"]),
            name=row["name"],
            purpose=row["purpose"],
            room_ids=tuple(_load_json(row["room_ids_json"])),
            revision=int(row["revision"]),
            roster_epoch=int(row["roster_epoch"]),
            lifecycle=GroupLifecycle(row["lifecycle"]),
            policy=policy,
            members=members,
            founding_member_ids=tuple(
                UUID(item) for item in _load_json(row["founding_member_ids_json"])
            ),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def load_group(self, group_id: UUID | str) -> GovernanceGroup | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_group WHERE group_id=?",
                (str(group_id),),
            ).fetchone()
            if row is None:
                return None
            members = db.execute(
                "SELECT * FROM governance_member WHERE group_id=? "
                "ORDER BY core_id ASC",
                (str(group_id),),
            ).fetchall()
        return self._group_from_rows(row, members)

    def list_groups(self) -> tuple[GovernanceGroup, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT group_id FROM governance_group ORDER BY created_at, group_id"
            ).fetchall()
        groups = tuple(self.load_group(row["group_id"]) for row in rows)
        return tuple(item for item in groups if item is not None)

    # ------------------------------------------------------------------
    # Proposals and nominations
    # ------------------------------------------------------------------
    def save_proposal(
        self,
        proposal: Proposal,
        *,
        actor_id: str,
        occurred_at: datetime,
        expected_revision: int | None = None,
        event_type: str = "governance.proposal.saved",
        idempotency_key: str | None = None,
    ) -> Proposal:
        if not isinstance(proposal, Proposal):
            raise TypeError("proposal must be Proposal")
        values = (
            str(proposal.group_id),
            str(proposal.proposer_core_id), proposal.proposal_type.value,
            proposal.title, proposal.text, proposal.policy_digest,
            proposal.procedure.value,
            _json([str(item) for item in proposal.electorate]),
            proposal.roster_epoch, _iso(proposal.opens_at),
            _iso(proposal.closes_at), proposal.quorum, proposal.status.value,
            _iso(proposal.created_at), proposal.revision,
            _json([str(item) for item in proposal.candidate_core_ids]),
            1 if proposal.binding else 0, proposal.coordinator_term_days,
        )
        try:
            with self.transaction() as db:
                row = db.execute(
                    "SELECT revision FROM governance_proposal WHERE proposal_id=?",
                    (str(proposal.proposal_id),),
                ).fetchone()
                if row is None:
                    if expected_revision not in (None, 1) or proposal.revision != 1:
                        raise GovernanceConflict("new proposal must begin at revision 1")
                    db.execute(
                        """
                        INSERT INTO governance_proposal (
                            proposal_id, group_id, proposer_core_id,
                            proposal_type, title, text, policy_digest, procedure,
                            electorate_json, roster_epoch, opens_at, closes_at,
                            quorum, status, created_at, revision,
                            candidate_core_ids_json, binding,
                            coordinator_term_days
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (str(proposal.proposal_id), *values),
                    )
                else:
                    old_revision = int(row["revision"])
                    if (
                        expected_revision is not None
                        and old_revision != expected_revision
                    ):
                        raise GovernanceConflict("proposal revision changed concurrently")
                    if proposal.revision != old_revision + 1:
                        raise GovernanceConflict(
                            "proposal update must advance revision by one"
                        )
                    db.execute(
                        """
                        UPDATE governance_proposal SET
                            group_id=?, proposer_core_id=?, proposal_type=?,
                            title=?, text=?, policy_digest=?, procedure=?,
                            electorate_json=?, roster_epoch=?, opens_at=?,
                            closes_at=?, quorum=?, status=?, created_at=?,
                            revision=?, candidate_core_ids_json=?, binding=?,
                            coordinator_term_days=?
                        WHERE proposal_id=?
                        """,
                        (*values, str(proposal.proposal_id)),
                    )
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    payload={
                        "proposal_id": str(proposal.proposal_id),
                        "group_id": str(proposal.group_id),
                        "revision": proposal.revision,
                        "status": proposal.status.value,
                        "policy_digest": proposal.policy_digest,
                    },
                    group_id=proposal.group_id,
                    proposal_id=proposal.proposal_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict("governance idempotency key was already used") from exc
        return proposal

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> Proposal:
        return Proposal(
            proposal_id=UUID(row["proposal_id"]),
            group_id=UUID(row["group_id"]),
            proposer_core_id=UUID(row["proposer_core_id"]),
            proposal_type=ProposalType(row["proposal_type"]),
            title=row["title"],
            text=row["text"],
            policy_digest=row["policy_digest"],
            procedure=DecisionProcedure(row["procedure"]),
            electorate=tuple(UUID(item) for item in _load_json(row["electorate_json"])),
            roster_epoch=int(row["roster_epoch"]),
            opens_at=_dt(row["opens_at"]),
            closes_at=_dt(row["closes_at"]),
            quorum=int(row["quorum"]),
            status=ProposalStatus(row["status"]),
            created_at=_dt(row["created_at"]),
            revision=int(row["revision"]),
            candidate_core_ids=tuple(
                UUID(item) for item in _load_json(row["candidate_core_ids_json"])
            ),
            binding=bool(row["binding"]),
            coordinator_term_days=int(row["coordinator_term_days"]),
        )

    def load_proposal(
        self, group_id: UUID | str, proposal_id: UUID | str
    ) -> Proposal | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_proposal "
                "WHERE group_id=? AND proposal_id=?",
                (str(group_id), str(proposal_id)),
            ).fetchone()
        return None if row is None else self._proposal_from_row(row)

    def list_proposals(self, group_id: UUID | str) -> tuple[Proposal, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_proposal WHERE group_id=? "
                "ORDER BY created_at ASC, proposal_id ASC",
                (str(group_id),),
            ).fetchall()
        return tuple(self._proposal_from_row(row) for row in rows)

    def open_proposals(self) -> tuple[Proposal, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_proposal WHERE status=? "
                "ORDER BY closes_at ASC, proposal_id ASC",
                (ProposalStatus.OPEN.value,),
            ).fetchall()
        return tuple(self._proposal_from_row(row) for row in rows)

    def save_nomination(
        self,
        nomination: Nomination,
        *,
        actor_id: str,
        occurred_at: datetime,
        idempotency_key: str | None = None,
    ) -> Nomination:
        if not isinstance(nomination, Nomination):
            raise TypeError("nomination must be Nomination")
        try:
            with self.transaction() as db:
                row = db.execute(
                    "SELECT accepted, resolved_at FROM governance_nomination "
                    "WHERE nomination_id=?",
                    (str(nomination.nomination_id),),
                ).fetchone()
                if row is None:
                    db.execute(
                        """
                        INSERT INTO governance_nomination (
                            nomination_id, proposal_id, candidate_core_id,
                            nominated_by_core_id, accepted, created_at, resolved_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(nomination.nomination_id),
                            str(nomination.proposal_id),
                            str(nomination.candidate_core_id),
                            str(nomination.nominated_by_core_id),
                            None if nomination.accepted is None else int(nomination.accepted),
                            _iso(nomination.created_at),
                            None if nomination.resolved_at is None else _iso(nomination.resolved_at),
                        ),
                    )
                else:
                    if row["accepted"] is not None and nomination.accepted is not None:
                        if bool(row["accepted"]) != nomination.accepted:
                            raise GovernanceConflict(
                                "a candidate acceptance cannot be reversed"
                            )
                    if row["accepted"] is not None and nomination.accepted is None:
                        raise GovernanceConflict("nomination is already resolved")
                    db.execute(
                        "UPDATE governance_nomination SET accepted=?, resolved_at=? "
                        "WHERE nomination_id=?",
                        (
                            None if nomination.accepted is None else int(nomination.accepted),
                            None if nomination.resolved_at is None else _iso(nomination.resolved_at),
                            str(nomination.nomination_id),
                        ),
                    )
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type="governance.nomination.updated",
                    occurred_at=occurred_at,
                    payload={
                        "nomination_id": str(nomination.nomination_id),
                        "proposal_id": str(nomination.proposal_id),
                        "candidate_core_id": str(nomination.candidate_core_id),
                        "accepted": nomination.accepted,
                    },
                    proposal_id=nomination.proposal_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict("governance idempotency key was already used") from exc
        return nomination

    @staticmethod
    def _nomination_from_row(row: sqlite3.Row) -> Nomination:
        return Nomination(
            nomination_id=UUID(row["nomination_id"]),
            proposal_id=UUID(row["proposal_id"]),
            candidate_core_id=UUID(row["candidate_core_id"]),
            nominated_by_core_id=UUID(row["nominated_by_core_id"]),
            accepted=None if row["accepted"] is None else bool(row["accepted"]),
            created_at=_dt(row["created_at"]),
            resolved_at=(
                None if row["resolved_at"] is None else _dt(row["resolved_at"])
            ),
        )

    def nominations(self, proposal_id: UUID | str) -> tuple[Nomination, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_nomination WHERE proposal_id=? "
                "ORDER BY candidate_core_id ASC",
                (str(proposal_id),),
            ).fetchall()
        return tuple(self._nomination_from_row(row) for row in rows)

    # ------------------------------------------------------------------
    # Ballots and immutable history
    # ------------------------------------------------------------------
    @staticmethod
    def _ballot_from_row(row: sqlite3.Row) -> Ballot:
        return Ballot(
            ballot_id=UUID(row["ballot_id"]),
            proposal_id=UUID(row["proposal_id"]),
            core_id=UUID(row["core_id"]),
            choice=BallotChoice(row["choice"]),
            revision=int(row["revision"]),
            idempotency_key=row["idempotency_key"],
            cast_at=_dt(row["cast_at"]),
            approvals=tuple(UUID(item) for item in _load_json(row["approvals_json"])),
        )

    def current_ballot(
        self, group_id: UUID | str, proposal_id: UUID | str, core_id: UUID
    ) -> Ballot | None:
        with self.reader() as db:
            row = db.execute(
                """
                SELECT b.* FROM governance_ballot AS b
                JOIN governance_proposal AS p ON p.proposal_id=b.proposal_id
                WHERE p.group_id=? AND b.proposal_id=? AND b.core_id=?
                """,
                (str(group_id), str(proposal_id), str(core_id)),
            ).fetchone()
        return None if row is None else self._ballot_from_row(row)

    def save_ballot(
        self,
        group_id: UUID | str,
        ballot: Ballot,
        *,
        actor_id: str,
        occurred_at: datetime,
        expected_revision: int | None,
        idempotency_key: str,
    ) -> Ballot:
        if not isinstance(ballot, Ballot):
            raise TypeError("ballot must be Ballot")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise GovernanceError("idempotency_key must be nonempty text")
        if ballot.idempotency_key != idempotency_key:
            raise GovernanceError("ballot and store idempotency keys must match")
        try:
            with self.transaction() as db:
                proposal_row = db.execute(
                    "SELECT group_id FROM governance_proposal WHERE proposal_id=?",
                    (str(ballot.proposal_id),),
                ).fetchone()
                if proposal_row is None:
                    raise LookupError("proposal does not exist")
                if proposal_row["group_id"] != str(group_id):
                    raise GovernanceDenied("ballot proposal is outside the group scope")

                current = db.execute(
                    "SELECT * FROM governance_ballot WHERE proposal_id=? AND core_id=?",
                    (str(ballot.proposal_id), str(ballot.core_id)),
                ).fetchone()
                if current is None:
                    if expected_revision not in (None, 0) or ballot.revision != 1:
                        raise GovernanceConflict("first ballot must begin at revision 1")
                    db.execute(
                        """
                        INSERT INTO governance_ballot (
                            ballot_id, proposal_id, core_id, choice, revision,
                            idempotency_key, cast_at, approvals_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(ballot.ballot_id), str(ballot.proposal_id),
                            str(ballot.core_id), ballot.choice.value,
                            ballot.revision, ballot.idempotency_key,
                            _iso(ballot.cast_at),
                            _json([str(item) for item in ballot.approvals]),
                        ),
                    )
                else:
                    if current["idempotency_key"] == idempotency_key:
                        existing = self._ballot_from_row(current)
                        if (
                            existing.choice is not ballot.choice
                            or existing.revision != ballot.revision
                            or existing.approvals != ballot.approvals
                            or existing.core_id != ballot.core_id
                        ):
                            raise GovernanceConflict(
                                "idempotency key was reused for a different ballot"
                            )
                        return existing
                    old_revision = int(current["revision"])
                    if (
                        expected_revision is None
                        or expected_revision != old_revision
                    ):
                        raise GovernanceConflict("ballot revision changed concurrently")
                    if ballot.revision != old_revision + 1:
                        raise GovernanceConflict(
                            "ballot update must advance revision by one"
                        )
                    db.execute(
                        "UPDATE governance_ballot_history SET superseded_at=?, "
                        "superseded_by=? WHERE proposal_id=? AND core_id=? "
                        "AND revision=?",
                        (
                            _iso(occurred_at),
                            f"{ballot.ballot_id}:{ballot.revision}",
                            str(ballot.proposal_id), str(ballot.core_id),
                            old_revision,
                        ),
                    )
                    db.execute(
                        """
                        UPDATE governance_ballot SET
                            ballot_id=?, choice=?, revision=?, idempotency_key=?,
                            cast_at=?, approvals_json=?
                        WHERE proposal_id=? AND core_id=?
                        """,
                        (
                            str(ballot.ballot_id), ballot.choice.value,
                            ballot.revision, ballot.idempotency_key,
                            _iso(ballot.cast_at),
                            _json([str(item) for item in ballot.approvals]),
                            str(ballot.proposal_id), str(ballot.core_id),
                        ),
                    )
                db.execute(
                    """
                    INSERT INTO governance_ballot_history (
                        history_id, ballot_id, proposal_id, core_id, choice,
                        revision, idempotency_key, cast_at, approvals_json,
                        superseded_at, superseded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        f"{ballot.ballot_id}:{ballot.revision}",
                        str(ballot.ballot_id), str(ballot.proposal_id),
                        str(ballot.core_id), ballot.choice.value, ballot.revision,
                        ballot.idempotency_key, _iso(ballot.cast_at),
                        _json([str(item) for item in ballot.approvals]),
                    ),
                )
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type="governance.ballot.cast",
                    occurred_at=occurred_at,
                    payload={
                        "ballot_id": str(ballot.ballot_id),
                        "proposal_id": str(ballot.proposal_id),
                        "core_id": str(ballot.core_id),
                        "choice": ballot.choice.value,
                        "revision": ballot.revision,
                        "approvals": [str(item) for item in ballot.approvals],
                        "idempotency_key": idempotency_key,
                    },
                    group_id=group_id,
                    proposal_id=ballot.proposal_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict(
                "duplicate, replayed or conflicting ballot evidence"
            ) from exc
        return ballot

    def ballots(self, group_id: UUID | str, proposal_id: UUID | str) -> tuple[Ballot, ...]:
        with self.reader() as db:
            rows = db.execute(
                """
                SELECT b.* FROM governance_ballot AS b
                JOIN governance_proposal AS p ON p.proposal_id=b.proposal_id
                WHERE p.group_id=? AND b.proposal_id=?
                ORDER BY b.core_id ASC
                """,
                (str(group_id), str(proposal_id)),
            ).fetchall()
        return tuple(self._ballot_from_row(row) for row in rows)

    def ballot_history(
        self, group_id: UUID | str, proposal_id: UUID | str
    ) -> tuple[dict[str, object], ...]:
        with self.reader() as db:
            rows = db.execute(
                """
                SELECT h.* FROM governance_ballot_history AS h
                JOIN governance_proposal AS p ON p.proposal_id=h.proposal_id
                WHERE p.group_id=? AND h.proposal_id=?
                ORDER BY h.core_id ASC, h.revision ASC
                """,
                (str(group_id), str(proposal_id)),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    # ------------------------------------------------------------------
    # Resolution finalization and coordinator terms
    # ------------------------------------------------------------------
    @staticmethod
    def _tally_from_payload(payload: dict[str, object]) -> TallyResult:
        return TallyResult(
            outcome=ResolutionOutcome(payload["outcome"]),
            yes=int(payload["yes"]),
            no=int(payload["no"]),
            abstain=int(payload["abstain"]),
            submitted=int(payload["submitted"]),
            eligible_count=int(payload["eligible_count"]),
            quorum=int(payload["quorum"]),
            binding=bool(payload["binding"]),
            reason=payload["reason"],
            coordinator_core_id=(
                None
                if payload["coordinator_core_id"] is None
                else UUID(payload["coordinator_core_id"])
            ),
            candidate_totals=tuple(
                (UUID(candidate), int(total))
                for candidate, total in payload["candidate_totals"]
            ),
        )

    @staticmethod
    def _tally_payload(tally: TallyResult) -> dict[str, object]:
        return tally.to_payload()

    @staticmethod
    def _resolution_from_row(row: sqlite3.Row) -> Resolution:
        tally = GovernanceStore._tally_from_payload(_load_json(row["tally_json"]))
        return Resolution(
            resolution_id=UUID(row["resolution_id"]),
            proposal_id=UUID(row["proposal_id"]),
            group_id=UUID(row["group_id"]),
            outcome=ResolutionOutcome(row["outcome"]),
            tally=tally,
            policy_digest=row["policy_digest"],
            resolved_at=_dt(row["resolved_at"]),
            evidence_refs=tuple(_load_json(row["evidence_refs_json"])),
            coordinator_core_id=(
                None if row["coordinator_core_id"] is None
                else UUID(row["coordinator_core_id"])
            ),
            term_starts_at=(
                None if row["term_starts_at"] is None else _dt(row["term_starts_at"])
            ),
            term_expires_at=(
                None if row["term_expires_at"] is None else _dt(row["term_expires_at"])
            ),
        )

    def load_resolution(
        self, group_id: UUID | str, proposal_id: UUID | str
    ) -> Resolution | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_resolution "
                "WHERE group_id=? AND proposal_id=?",
                (str(group_id), str(proposal_id)),
            ).fetchone()
        return None if row is None else self._resolution_from_row(row)

    def resolution_for_proposal(self, proposal_id: UUID | str) -> Resolution | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_resolution WHERE proposal_id=?",
                (str(proposal_id),),
            ).fetchone()
        return None if row is None else self._resolution_from_row(row)

    @staticmethod
    def _write_term(db: sqlite3.Connection, term: CoordinatorTerm) -> None:
        db.execute(
            """
            INSERT INTO governance_coordinator_term (
                term_id, group_id, core_id, proposal_id, starts_at, expires_at,
                status, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(term.term_id), str(term.group_id), str(term.core_id),
                str(term.proposal_id), _iso(term.starts_at),
                _iso(term.expires_at), term.status.value, term.revision,
            ),
        )

    def finalize_proposal(
        self,
        *,
        proposal: Proposal,
        resolution: Resolution,
        actor_id: str,
        occurred_at: datetime,
        term: CoordinatorTerm | None = None,
        superseded_terms: tuple[CoordinatorTerm, ...] = (),
        group_update: GovernanceGroup | None = None,
        idempotency_key: str | None = None,
    ) -> Resolution:
        if proposal.status is not ProposalStatus.RESOLVED:
            raise GovernanceError("finalized proposal must be RESOLVED")
        if not isinstance(resolution, Resolution):
            raise TypeError("resolution must be Resolution")
        try:
            with self.transaction() as db:
                existing = db.execute(
                    "SELECT * FROM governance_resolution WHERE proposal_id=?",
                    (str(proposal.proposal_id),),
                ).fetchone()
                if existing is not None:
                    return self._resolution_from_row(existing)
                proposal_row = db.execute(
                    "SELECT revision FROM governance_proposal WHERE proposal_id=?",
                    (str(proposal.proposal_id),),
                ).fetchone()
                if proposal_row is None:
                    raise LookupError("proposal does not exist")
                if proposal.revision != int(proposal_row["revision"]) + 1:
                    raise GovernanceConflict("proposal revision is not current")
                db.execute(
                    "UPDATE governance_proposal SET status=?, revision=? "
                    "WHERE proposal_id=?",
                    (
                        proposal.status.value, proposal.revision,
                        str(proposal.proposal_id),
                    ),
                )
                if group_update is not None:
                    group_row = db.execute(
                        "SELECT revision FROM governance_group WHERE group_id=?",
                        (str(group_update.group_id),),
                    ).fetchone()
                    if group_row is None:
                        raise LookupError("group does not exist")
                    if group_update.revision != int(group_row["revision"]) + 1:
                        raise GovernanceConflict("group revision is not current")
                    db.execute(
                        """
                        UPDATE governance_group SET
                            name=?, purpose=?, room_ids_json=?, revision=?,
                            roster_epoch=?, lifecycle=?, policy_json=?,
                            policy_digest=?, founding_member_ids_json=?,
                            created_at=?, updated_at=?
                        WHERE group_id=?
                        """,
                        (
                            group_update.name, group_update.purpose,
                            _json(list(group_update.room_ids)),
                            group_update.revision, group_update.roster_epoch,
                            group_update.lifecycle.value,
                            _json(group_update.policy.to_payload()),
                            group_update.policy_digest,
                            _json([
                                str(item) for item in group_update.founding_member_ids
                            ]),
                            _iso(group_update.created_at),
                            _iso(group_update.updated_at),
                            str(group_update.group_id),
                        ),
                    )
                    db.execute(
                        "DELETE FROM governance_member WHERE group_id=?",
                        (str(group_update.group_id),),
                    )
                    for member in group_update.members:
                        db.execute(
                            """
                            INSERT INTO governance_member (
                                group_id, core_id, state, joined_at, joined_epoch,
                                governance_opted_in, consented_policy_digest
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(group_update.group_id), str(member.core_id),
                                member.state.value, _iso(member.joined_at),
                                member.joined_epoch,
                                1 if member.governance_opted_in else 0,
                                member.consented_policy_digest,
                            ),
                        )
                db.execute(
                    """
                    INSERT INTO governance_resolution (
                        resolution_id, proposal_id, group_id, outcome,
                        tally_json, policy_digest, resolved_at,
                        evidence_refs_json, coordinator_core_id, term_starts_at,
                        term_expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(resolution.resolution_id), str(resolution.proposal_id),
                        str(resolution.group_id), resolution.outcome.value,
                        _json(self._tally_payload(resolution.tally)),
                        resolution.policy_digest, _iso(resolution.resolved_at),
                        _json(list(resolution.evidence_refs)),
                        None if resolution.coordinator_core_id is None
                        else str(resolution.coordinator_core_id),
                        None if resolution.term_starts_at is None
                        else _iso(resolution.term_starts_at),
                        None if resolution.term_expires_at is None
                        else _iso(resolution.term_expires_at),
                    ),
                )
                for superseded in superseded_terms:
                    row = db.execute(
                        "SELECT revision FROM governance_coordinator_term "
                        "WHERE term_id=?",
                        (str(superseded.term_id),),
                    ).fetchone()
                    if row is None:
                        raise LookupError("superseded coordinator term does not exist")
                    if superseded.revision != int(row["revision"]) + 1:
                        raise GovernanceConflict("coordinator term revision is not current")
                    db.execute(
                        "UPDATE governance_coordinator_term SET status=?, revision=? "
                        "WHERE term_id=?",
                        (
                            superseded.status.value, superseded.revision,
                            str(superseded.term_id),
                        ),
                    )
                if term is not None:
                    self._write_term(db, term)
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type="governance.proposal.resolved",
                    occurred_at=occurred_at,
                    payload={
                        "proposal_id": str(proposal.proposal_id),
                        "resolution_id": str(resolution.resolution_id),
                        "group_id": str(resolution.group_id),
                        "outcome": resolution.outcome.value,
                        "coordinator_core_id": (
                            None if resolution.coordinator_core_id is None
                            else str(resolution.coordinator_core_id)
                        ),
                        "term_id": None if term is None else str(term.term_id),
                    },
                    group_id=resolution.group_id,
                    proposal_id=proposal.proposal_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict("resolution or idempotency already exists") from exc
        return resolution

    @staticmethod
    def _term_from_row(row: sqlite3.Row) -> CoordinatorTerm:
        return CoordinatorTerm(
            term_id=UUID(row["term_id"]),
            group_id=UUID(row["group_id"]),
            core_id=UUID(row["core_id"]),
            proposal_id=UUID(row["proposal_id"]),
            starts_at=_dt(row["starts_at"]),
            expires_at=_dt(row["expires_at"]),
            status=CoordinatorStatus(row["status"]),
            revision=int(row["revision"]),
        )

    def load_term(self, term_id: UUID | str) -> CoordinatorTerm | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_coordinator_term WHERE term_id=?",
                (str(term_id),),
            ).fetchone()
        return None if row is None else self._term_from_row(row)

    def active_term(self, group_id: UUID | str) -> CoordinatorTerm | None:
        with self.reader() as db:
            row = db.execute(
                "SELECT * FROM governance_coordinator_term "
                "WHERE group_id=? AND status=? "
                "ORDER BY starts_at DESC, term_id DESC LIMIT 1",
                (str(group_id), CoordinatorStatus.ACTIVE.value),
            ).fetchone()
        return None if row is None else self._term_from_row(row)

    def terms(self, group_id: UUID | str) -> tuple[CoordinatorTerm, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_coordinator_term WHERE group_id=? "
                "ORDER BY starts_at ASC, term_id ASC",
                (str(group_id),),
            ).fetchall()
        return tuple(self._term_from_row(row) for row in rows)

    def active_terms(self) -> tuple[CoordinatorTerm, ...]:
        with self.reader() as db:
            rows = db.execute(
                "SELECT * FROM governance_coordinator_term WHERE status=? "
                "ORDER BY expires_at ASC, term_id ASC",
                (CoordinatorStatus.ACTIVE.value,),
            ).fetchall()
        return tuple(self._term_from_row(row) for row in rows)

    def save_term(
        self,
        term: CoordinatorTerm,
        *,
        actor_id: str,
        occurred_at: datetime,
        expected_revision: int | None = None,
        event_type: str = "governance.coordinator.updated",
        idempotency_key: str | None = None,
    ) -> CoordinatorTerm:
        if not isinstance(term, CoordinatorTerm):
            raise TypeError("term must be CoordinatorTerm")
        try:
            with self.transaction() as db:
                row = db.execute(
                    "SELECT revision FROM governance_coordinator_term WHERE term_id=?",
                    (str(term.term_id),),
                ).fetchone()
                if row is None:
                    if expected_revision not in (None, 1) or term.revision != 1:
                        raise GovernanceConflict("new term must begin at revision 1")
                    self._write_term(db, term)
                else:
                    old_revision = int(row["revision"])
                    if (
                        expected_revision is not None
                        and expected_revision != old_revision
                    ):
                        raise GovernanceConflict("term revision changed concurrently")
                    if term.revision != old_revision + 1:
                        raise GovernanceConflict("term update must advance revision by one")
                    db.execute(
                        "UPDATE governance_coordinator_term SET status=?, revision=? "
                        "WHERE term_id=?",
                        (term.status.value, term.revision, str(term.term_id)),
                    )
                self._append_audit(
                    db,
                    actor_id=actor_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    payload={
                        "term_id": str(term.term_id),
                        "group_id": str(term.group_id),
                        "core_id": str(term.core_id),
                        "status": term.status.value,
                        "revision": term.revision,
                    },
                    group_id=term.group_id,
                    proposal_id=term.proposal_id,
                    idempotency_key=idempotency_key,
                )
        except sqlite3.IntegrityError as exc:
            raise GovernanceConflict("governance idempotency key was already used") from exc
        return term


__all__ = ["GovernanceStore"]
