"""Opt-in, audience-scoped NEURO associations over MEM-approved candidate IDs.

Only memory candidate UUIDs/hashed sparse feature units and exact provenance
receipts persist. Never persist raw query text here. The memory store remains
the sole authority for promotion, corrections, privacy and audience access.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import re
from uuid import UUID

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.neuro.connectome.associative import SparseAssociativeMemory
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_ALGORITHM = SparseAssociativeMemory.ALGORITHM_VERSION
_TOKENS = re.compile(r"[A-Za-z0-9À-ÿ']+")
_RECEIPT = re.compile(r"^[A-Za-z0-9_.:/-]{1,120}$")


def _units(text: str) -> tuple[int, ...]:
    if not isinstance(text, str):
        raise TypeError("association query must be text")
    if len(text) > 500:
        raise ValueError("association query must be at most 500 characters")
    # Feature tokens are hashed before persistence and never exported as prose.
    tokens = sorted({
        token.casefold() for token in _TOKENS.findall(text)
        if len(token) > 1
    })[:64]
    if not tokens:
        return ()
    features = tuple(
        "word:" + sha256(token.encode("utf-8")).hexdigest()[:24]
        for token in tokens
    )
    return SparseAssociativeMemory()._expand(features)


class ReviewedAssociationStore:
    """One canonical SQLite owner; no alternate memory database or authority."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS neuro_association_weight (
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    feature_unit INTEGER NOT NULL,
                    weight REAL NOT NULL CHECK(weight BETWEEN -1 AND 1),
                    algorithm TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    PRIMARY KEY(principal_id,audience_id,candidate_id,feature_unit)
                );
                CREATE TABLE IF NOT EXISTS neuro_association_event (
                    approval_ref TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    feature_units_json TEXT NOT NULL,
                    amount REAL NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('reinforce','revert')),
                    occurred_at TEXT NOT NULL,
                    algorithm TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS neuro_association_scope_idx
                    ON neuro_association_weight(principal_id,audience_id,candidate_id);
                CREATE TRIGGER IF NOT EXISTS neuro_association_revoke_cleanup
                AFTER UPDATE OF status ON memory_candidate
                WHEN NEW.status != 'promoted'
                BEGIN
                    DELETE FROM neuro_association_weight WHERE candidate_id=NEW.candidate_id;
                    DELETE FROM neuro_association_event WHERE candidate_id=NEW.candidate_id;
                END;
                CREATE TRIGGER IF NOT EXISTS neuro_association_delete_cleanup
                AFTER DELETE ON memory_candidate
                BEGIN
                    DELETE FROM neuro_association_weight WHERE candidate_id=OLD.candidate_id;
                    DELETE FROM neuro_association_event WHERE candidate_id=OLD.candidate_id;
                END;
            """)

    def _connect(self):
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _scope(principal_id: str, audience_id: str) -> tuple[str, str]:
        for name, value in (("principal", principal_id), ("audience", audience_id)):
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"bounded {name} identity required")
        return principal_id, audience_id

    @staticmethod
    def _moment(value: datetime) -> str:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("association time must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()

    def _opted_in(self) -> bool:
        return RuntimeUserSettingsStore(self.path).load().neuro_association_enabled

    def reinforce_reviewed(
        self, *, principal_id: str, audience_id: str,
        candidate_id: UUID, query: str, approval_ref: str,
        amount: float, at: datetime,
    ) -> None:
        """Apply one explicitly reviewed, bounded teaching receipt.

        Not exposed as an LLM tool. Every write checks the current promoted
        candidate AND its exact principal/audience within BEGIN IMMEDIATE.
        """
        principal_id, audience_id = self._scope(principal_id, audience_id)
        if not self._opted_in():
            raise PermissionError("opt-in NEURO association learning is disabled")
        if not isinstance(candidate_id, UUID):
            raise TypeError("reviewed candidate UUID required")
        if (
            not isinstance(approval_ref, str)
            or not _RECEIPT.fullmatch(approval_ref)
            or not approval_ref.startswith("operator-ui:")
        ):
            raise ValueError("one explicit owner UI review receipt required")
        if (
            type(amount) not in {int, float} or not math.isfinite(amount)
            or not -0.1 <= amount <= 0.1 or amount == 0
        ):
            raise ValueError("reviewed reinforcement must be nonzero in -0.1..0.1")
        moment = self._moment(at)
        units = _units(query)
        if not units:
            raise ValueError("reviewed association needs eligible query terms")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            candidate = db.execute(
                "SELECT status,principal_id,audience_id FROM memory_candidate "
                "WHERE candidate_id=?", (str(candidate_id),),
            ).fetchone()
            if (
                candidate is None or candidate[0] != "promoted"
                or candidate[1] != principal_id
                or candidate[2] not in (None, audience_id)
            ):
                raise PermissionError("memory is not promoted for this audience")
            reviewed_events = db.execute(
                "SELECT COUNT(*) FROM neuro_association_event "
                "WHERE principal_id=? AND audience_id=? AND candidate_id=?",
                (principal_id, audience_id, str(candidate_id)),
            ).fetchone()[0]
            if reviewed_events >= 64:
                raise PermissionError(
                    "per-memory reinforcement budget exhausted; reset/review required"
                )
            for unit in units:
                db.execute(
                    "INSERT INTO neuro_association_weight "
                    "(principal_id,audience_id,candidate_id,feature_unit,weight,"
                    "algorithm,changed_at) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(principal_id,audience_id,candidate_id,feature_unit) "
                    "DO UPDATE SET weight=min(1,max(-1,weight+excluded.weight)),"
                    "algorithm=excluded.algorithm,changed_at=excluded.changed_at",
                    (
                        principal_id, audience_id, str(candidate_id), unit,
                        float(amount), _ALGORITHM, moment,
                    ),
                )
            db.execute(
                "INSERT INTO neuro_association_event "
                "(approval_ref,principal_id,audience_id,candidate_id,"
                "feature_units_json,amount,action,occurred_at,algorithm)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    approval_ref, principal_id, audience_id, str(candidate_id),
                    json.dumps(units), float(amount), "reinforce", moment, _ALGORITHM,
                ),
            )
            db.commit()

    def scores(
        self, *, principal_id: str, audience_id: str, query: str,
        eligible_ids: tuple[UUID, ...],
    ) -> dict[UUID, float]:
        """Rerank only caller-supplied lexical/MEM-eligible candidates.

        Joining current MEM status prevents resurrecting revoked/corrected
        content even if an external SQLite writer bypassed cleanup triggers.
        """
        principal_id, audience_id = self._scope(principal_id, audience_id)
        if not self._opted_in() or not eligible_ids:
            return {}
        if (
            not isinstance(eligible_ids, tuple) or len(eligible_ids) > 64
            or any(not isinstance(cid, UUID) for cid in eligible_ids)
        ):
            raise ValueError("bounded MEM-eligible UUID tuple required")
        units = _units(query)
        if not units:
            return {}
        placeholders = ",".join("?" for _ in eligible_ids)
        unit_marks = ",".join("?" for _ in units)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT w.candidate_id, SUM(MAX(w.weight,0.0)) FROM "
                "neuro_association_weight w "
                "JOIN memory_candidate m ON m.candidate_id=w.candidate_id "
                "WHERE w.principal_id=? AND w.audience_id=? "
                "AND w.algorithm=? AND m.status='promoted' "
                "AND m.principal_id=? AND "
                "(m.audience_id IS NULL OR m.audience_id=?) "
                f"AND w.candidate_id IN ({placeholders}) "
                f"AND w.feature_unit IN ({unit_marks}) "
                "GROUP BY w.candidate_id",
                (
                    principal_id, audience_id, _ALGORITHM,
                    principal_id, audience_id,
                    *[str(cid) for cid in eligible_ids], *units,
                ),
            ).fetchall()
        allowed = set(eligible_ids)
        return {
            uuid: min(1.0, max(0.0, float(value) / len(units)))
            for raw, value in rows
            if (uuid := UUID(raw)) in allowed
        }

    def reset_scope(self, *, principal_id: str, audience_id: str) -> int:
        """Owner-only caller operation. Remove learned weights and receipts."""
        principal_id, audience_id = self._scope(principal_id, audience_id)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "DELETE FROM neuro_association_weight "
                "WHERE principal_id=? AND audience_id=?",
                (principal_id, audience_id),
            ).rowcount
            db.execute(
                "DELETE FROM neuro_association_event "
                "WHERE principal_id=? AND audience_id=?",
                (principal_id, audience_id),
            )
            db.commit()
        return count

    def decay_scope(
        self, *, principal_id: str, audience_id: str,
        rate: float = 0.01, at: datetime,
    ) -> int:
        """Explicit bounded decay, not a hidden self-evolving training loop."""
        principal_id, audience_id = self._scope(principal_id, audience_id)
        moment = self._moment(at)
        if not self._opted_in():
            return 0
        if type(rate) not in {int, float} or not math.isfinite(rate) or not 0 <= rate <= 0.1:
            raise ValueError("decay rate must be in 0..0.1")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE neuro_association_weight SET weight=weight*(1-?),"
                "changed_at=? WHERE principal_id=? AND audience_id=?",
                (float(rate), moment, principal_id, audience_id),
            )
            db.execute(
                "DELETE FROM neuro_association_weight WHERE "
                "principal_id=? AND audience_id=? AND abs(weight)<0.001",
                (principal_id, audience_id),
            )
            db.commit()
        return result.rowcount
