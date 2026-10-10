"""Durable cross-modal expression decisions and independent output receipts."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.cognition.matrix import EmbodiedExpressionPlan
from sofia.personality.influence import ContinuityInfluence
from sofia.social.model import PrincipalContext
from sofia.voice.prosody_matrix import VoiceProsodyMatrix, VoiceProsodyProfile


@dataclass(frozen=True, slots=True)
class ExpressionDecision:
    decision_id: str
    message_id: str
    session_id: str
    principal_id: str
    audience_id: str
    intent: str
    text_sha256: str
    emotion_labels: tuple[str, ...]
    emotion_evidence_refs: tuple[str, ...]
    prosody: VoiceProsodyProfile
    gesture: str | None
    pose: str | None
    intensity: str
    presentation_revision: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExpressionReceipt:
    receipt_id: str
    decision_id: str
    output: str
    status: str
    acknowledged: bool
    backend: str
    detail: str
    occurred_at: datetime


class ExpressionRuntime:
    """One typed decision per settled reply; outputs acknowledge separately."""

    _OUTPUTS = frozenset({"text", "voice", "avatar"})
    _STATUSES = frozenset({
        "persisted", "queued", "spoken", "rendered", "failed", "rejected",
        "cancelled", "unavailable",
    })

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS expression_decision (
                    decision_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    text_sha256 TEXT NOT NULL,
                    emotion_labels_json TEXT NOT NULL,
                    emotion_evidence_refs_json TEXT NOT NULL,
                    prosody_json TEXT NOT NULL,
                    gesture TEXT,
                    pose TEXT,
                    intensity TEXT NOT NULL,
                    presentation_revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS expression_decision_scope
                    ON expression_decision(principal_id,audience_id,created_at DESC);
                CREATE TABLE IF NOT EXISTS expression_output_receipt (
                    receipt_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    output TEXT NOT NULL,
                    status TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL,
                    backend TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(decision_id) REFERENCES expression_decision(decision_id)
                );
                CREATE INDEX IF NOT EXISTS expression_receipt_decision
                    ON expression_output_receipt(decision_id,occurred_at);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _decode(row: sqlite3.Row) -> ExpressionDecision:
        prosody = json.loads(row["prosody_json"])
        prosody["tone_tags"] = tuple(prosody.get("tone_tags", ()))
        prosody["ambient_context"] = tuple(prosody.get("ambient_context", ()))
        return ExpressionDecision(
            decision_id=row["decision_id"], message_id=row["message_id"],
            session_id=row["session_id"], principal_id=row["principal_id"],
            audience_id=row["audience_id"], intent=row["intent"],
            text_sha256=row["text_sha256"],
            emotion_labels=tuple(json.loads(row["emotion_labels_json"])),
            emotion_evidence_refs=tuple(json.loads(row["emotion_evidence_refs_json"])),
            prosody=VoiceProsodyProfile(**prosody),
            gesture=row["gesture"], pose=row["pose"], intensity=row["intensity"],
            presentation_revision=int(row["presentation_revision"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def decide(
        self, *, message_id: str, session_id: str, principal: PrincipalContext,
        intent: str, text: str, state, influence: ContinuityInfluence,
        plan: EmbodiedExpressionPlan | None, presentation_revision: int,
        created_at: datetime,
    ) -> ExpressionDecision:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if not text.strip():
            raise ValueError("settled response text required")
        profile = VoiceProsodyMatrix().plan(influence).profile
        active = tuple(item.name for item in state.active)
        evidence = tuple(dict.fromkeys(
            ref for item in state.active for ref in item.evidence_refs
        ))
        decision = ExpressionDecision(
            decision_id=f"expression:{message_id}", message_id=message_id,
            session_id=session_id, principal_id=principal.principal_id,
            audience_id=principal.audience_id, intent=intent or "conversation",
            text_sha256=sha256(text.encode("utf-8")).hexdigest(),
            emotion_labels=active, emotion_evidence_refs=evidence,
            prosody=profile, gesture=None if plan is None else plan.primary,
            pose=None if plan is None else plan.pose,
            intensity="subtle" if plan is None else plan.intensity,
            presentation_revision=presentation_revision,
            created_at=self._aware(created_at),
        )
        encoded_profile = asdict(profile)
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT OR IGNORE INTO expression_decision VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision.decision_id, decision.message_id, decision.session_id,
                    decision.principal_id, decision.audience_id, decision.intent,
                    decision.text_sha256, json.dumps(decision.emotion_labels),
                    json.dumps(decision.emotion_evidence_refs),
                    json.dumps(encoded_profile, sort_keys=True), decision.gesture,
                    decision.pose, decision.intensity,
                    decision.presentation_revision, decision.created_at.isoformat(),
                ),
            )
            row = db.execute(
                "SELECT * FROM expression_decision WHERE message_id=?",
                (message_id,),
            ).fetchone()
        existing = self._decode(row)
        if existing != decision:
            raise ValueError("message already has a different expression decision")
        self.receipt(
            decision_id=decision.decision_id, output="text", status="persisted",
            acknowledged=True, backend="canonical-conversation-store",
            detail="settled assistant message persisted", occurred_at=created_at,
            dedupe_key="text",
        )
        return decision

    def get_for_message(self, message_id: str) -> ExpressionDecision | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM expression_decision WHERE message_id=?", (message_id,)
            ).fetchone()
        return None if row is None else self._decode(row)

    def latest(self, principal: PrincipalContext) -> ExpressionDecision | None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM expression_decision
                WHERE principal_id=? AND audience_id=?
                ORDER BY created_at DESC,decision_id DESC LIMIT 1""",
                (principal.principal_id, principal.audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def receipt(
        self, *, decision_id: str, output: str, status: str,
        acknowledged: bool, backend: str, detail: str, occurred_at: datetime,
        dedupe_key: str | None = None,
    ) -> ExpressionReceipt:
        if output not in self._OUTPUTS or status not in self._STATUSES:
            raise ValueError("unsupported expression output receipt")
        if type(acknowledged) is not bool:
            raise TypeError("acknowledged must be bool")
        if acknowledged != (status in {"persisted", "spoken", "rendered"}):
            raise ValueError("only completed outputs may be acknowledged")
        moment = self._aware(occurred_at)
        key = dedupe_key or str(uuid4())
        receipt_id = f"expression-receipt:{sha256((decision_id + ':' + output + ':' + key).encode()).hexdigest()}"
        value = ExpressionReceipt(
            receipt_id, decision_id, output, status, acknowledged,
            backend.strip() or "unknown", detail.strip()[:500], moment,
        )
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO expression_output_receipt VALUES(?,?,?,?,?,?,?,?)",
                (
                    value.receipt_id, value.decision_id, value.output, value.status,
                    int(value.acknowledged), value.backend, value.detail,
                    value.occurred_at.isoformat(),
                ),
            )
        return value

    def receipts(self, decision_id: str) -> tuple[ExpressionReceipt, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM expression_output_receipt WHERE decision_id=? ORDER BY occurred_at,receipt_id",
                (decision_id,),
            ).fetchall()
        return tuple(ExpressionReceipt(
            row["receipt_id"], row["decision_id"], row["output"], row["status"],
            bool(row["acknowledged"]), row["backend"], row["detail"],
            datetime.fromisoformat(row["occurred_at"]),
        ) for row in rows)
