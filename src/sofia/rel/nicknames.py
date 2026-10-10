"""Scoped nickname proposals and recipient-controlled lifecycle."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.social.model import PrincipalContext


class NicknameStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    RETIRED = "retired"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class NicknameProposal:
    proposal_id: str
    proposer_id: str
    recipient_principal_id: str
    target_id: str
    nickname: str
    contexts: tuple[str, ...]
    audience_id: str
    evidence_ref: str
    status: NicknameStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class NicknameEvent:
    event_id: str
    proposal_id: str
    from_status: NicknameStatus | None
    to_status: NicknameStatus
    actor_principal_id: str
    evidence_ref: str
    occurred_at: datetime


class NicknameRegistry:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS rel_nickname_proposal (
                    proposal_id TEXT PRIMARY KEY, proposer_id TEXT NOT NULL,
                    recipient_principal_id TEXT NOT NULL, target_id TEXT NOT NULL,
                    nickname TEXT NOT NULL, normalized_nickname TEXT NOT NULL,
                    contexts_json TEXT NOT NULL, audience_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(recipient_principal_id,target_id,normalized_nickname,audience_id)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS rel_nickname_event (
                    event_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL,
                    from_status TEXT, to_status TEXT NOT NULL,
                    actor_principal_id TEXT NOT NULL, evidence_ref TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(proposal_id) REFERENCES rel_nickname_proposal(proposal_id)
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _decode(row) -> NicknameProposal:
        return NicknameProposal(
            row["proposal_id"], row["proposer_id"],
            row["recipient_principal_id"], row["target_id"], row["nickname"],
            tuple(json.loads(row["contexts_json"])), row["audience_id"],
            row["evidence_ref"], NicknameStatus(row["status"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    def propose(
        self, *, proposer_id: str, recipient: PrincipalContext, target_id: str,
        nickname: str, contexts: tuple[str, ...], evidence_ref: str,
        now: datetime,
    ) -> NicknameProposal:
        if not isinstance(recipient, PrincipalContext):
            raise TypeError("authenticated recipient required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("nickname timestamp must be timezone-aware")
        for value, label, maximum in (
            (proposer_id, "proposer_id", 160), (target_id, "target_id", 160),
            (nickname, "nickname", 80), (evidence_ref, "evidence_ref", 300),
        ):
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
                raise ValueError(f"{label} must be bounded text")
        if not contexts or len(contexts) > 16 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 80
            for item in contexts
        ):
            raise ValueError("nickname contexts must be a bounded nonempty tuple")
        normalized = " ".join(nickname.casefold().split())
        moment = now.astimezone(timezone.utc)
        proposal = NicknameProposal(
            f"nickname:{uuid4()}", proposer_id, recipient.principal_id,
            target_id, nickname.strip(), tuple(dict.fromkeys(contexts)),
            recipient.audience_id, evidence_ref, NicknameStatus.PROPOSED,
            moment, moment,
        )
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    "INSERT INTO rel_nickname_proposal VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (proposal.proposal_id, proposal.proposer_id,
                     proposal.recipient_principal_id, proposal.target_id,
                     proposal.nickname, normalized,
                     json.dumps(proposal.contexts), proposal.audience_id,
                     proposal.evidence_ref, proposal.status.value,
                     moment.isoformat(), moment.isoformat()),
                )
                db.execute(
                    "INSERT INTO rel_nickname_event VALUES(?,?,?,?,?,?,?)",
                    (f"nickname-event:{uuid4()}", proposal.proposal_id, None,
                     proposal.status.value, proposer_id, evidence_ref,
                     moment.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("nickname was already proposed in this relationship scope") from exc
        return proposal

    def respond(
        self, proposal_id: str, *, recipient: PrincipalContext,
        accept: bool, evidence_ref: str, now: datetime,
    ) -> NicknameProposal:
        if not isinstance(recipient, PrincipalContext):
            raise TypeError("authenticated recipient required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("nickname timestamp must be timezone-aware")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip() or len(evidence_ref) > 300:
            raise ValueError("evidence_ref must be bounded text")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM rel_nickname_proposal WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError("nickname proposal not found")
            if (row["recipient_principal_id"], row["audience_id"]) != (
                recipient.principal_id, recipient.audience_id,
            ):
                raise PermissionError("nickname proposal belongs to another recipient scope")
            if row["status"] != NicknameStatus.PROPOSED.value:
                raise RuntimeError("nickname proposal is no longer awaiting feedback")
            status = NicknameStatus.ACCEPTED if accept else NicknameStatus.DECLINED
            db.execute(
                "UPDATE rel_nickname_proposal SET status=?,updated_at=? WHERE proposal_id=?",
                (status.value, now.astimezone(timezone.utc).isoformat(), proposal_id),
            )
            db.execute(
                "INSERT INTO rel_nickname_event VALUES(?,?,?,?,?,?,?)",
                (f"nickname-event:{uuid4()}", proposal_id,
                 NicknameStatus.PROPOSED.value, status.value,
                 recipient.principal_id, evidence_ref,
                 now.astimezone(timezone.utc).isoformat()),
            )
            updated = db.execute(
                "SELECT * FROM rel_nickname_proposal WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
        return self._decode(updated)

    def retire(
        self, proposal_id: str, *, recipient: PrincipalContext,
        revoke: bool, evidence_ref: str, now: datetime,
    ) -> NicknameProposal:
        if not isinstance(recipient, PrincipalContext):
            raise TypeError("authenticated recipient required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("nickname timestamp must be timezone-aware")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip() or len(evidence_ref) > 300:
            raise ValueError("evidence_ref must be bounded text")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM rel_nickname_proposal WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None:
                raise KeyError("nickname proposal not found")
            if (row["recipient_principal_id"], row["audience_id"]) != (
                recipient.principal_id, recipient.audience_id,
            ):
                raise PermissionError("nickname belongs to another recipient scope")
            if row["status"] != NicknameStatus.ACCEPTED.value:
                raise RuntimeError("only an accepted nickname can be retired or revoked")
            status = NicknameStatus.REVOKED if revoke else NicknameStatus.RETIRED
            db.execute(
                "UPDATE rel_nickname_proposal SET status=?,updated_at=? WHERE proposal_id=?",
                (status.value, now.astimezone(timezone.utc).isoformat(), proposal_id),
            )
            db.execute(
                "INSERT INTO rel_nickname_event VALUES(?,?,?,?,?,?,?)",
                (f"nickname-event:{uuid4()}", proposal_id,
                 NicknameStatus.ACCEPTED.value, status.value,
                 recipient.principal_id, evidence_ref,
                 now.astimezone(timezone.utc).isoformat()),
            )
            updated = db.execute("SELECT * FROM rel_nickname_proposal WHERE proposal_id=?", (proposal_id,)).fetchone()
        return self._decode(updated)

    def active_for(
        self, *, recipient: PrincipalContext, target_id: str, context: str,
    ) -> tuple[NicknameProposal, ...]:
        if not isinstance(recipient, PrincipalContext):
            raise TypeError("authenticated recipient required")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM rel_nickname_proposal WHERE recipient_principal_id=?
                AND audience_id=? AND target_id=? AND status='accepted' ORDER BY updated_at DESC""",
                (recipient.principal_id, recipient.audience_id, target_id),
            ).fetchall()
        return tuple(
            self._decode(row) for row in rows
            if context in json.loads(row["contexts_json"])
        )

    def history(
        self, proposal_id: str, *, recipient: PrincipalContext,
    ) -> tuple[NicknameEvent, ...]:
        if not isinstance(recipient, PrincipalContext):
            raise TypeError("authenticated recipient required")
        with closing(self._connect()) as db:
            owner = db.execute(
                "SELECT recipient_principal_id,audience_id FROM rel_nickname_proposal WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if owner is None:
                raise KeyError("nickname proposal not found")
            if tuple(owner) != (recipient.principal_id, recipient.audience_id):
                raise PermissionError("nickname belongs to another recipient scope")
            rows = db.execute(
                "SELECT * FROM rel_nickname_event WHERE proposal_id=? ORDER BY occurred_at,rowid",
                (proposal_id,),
            ).fetchall()
        return tuple(
            NicknameEvent(
                row["event_id"], row["proposal_id"],
                None if row["from_status"] is None else NicknameStatus(row["from_status"]),
                NicknameStatus(row["to_status"]), row["actor_principal_id"],
                row["evidence_ref"], datetime.fromisoformat(row["occurred_at"]),
            )
            for row in rows
        )
