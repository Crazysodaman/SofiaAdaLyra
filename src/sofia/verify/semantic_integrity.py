from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from sofia.dev.release_store import ReleaseStateStore
from sofia.safe.audit import AuditChain
from sofia.state.plane import StatePlane
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class IntegritySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    code: str
    severity: IntegritySeverity
    detail: str


@dataclass(frozen=True, slots=True)
class SemanticIntegrityReport:
    checked_at: datetime
    findings: tuple[IntegrityFinding, ...]

    @property
    def accepted(self) -> bool:
        return not any(
            item.severity is IntegritySeverity.ERROR
            for item in self.findings
        )


class SemanticIntegrityVerifier:
    """Read-only semantic integrity checks across current production state."""

    def __init__(
        self,
        state_path: Path | str,
        *,
        state_plane: StatePlane,
    ) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self.state_plane = state_plane
        self._guard = CanonicalSQLiteGuard(self.path)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _table(db: sqlite3.Connection, name: str) -> bool:
        return db.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (name,),
        ).fetchone() is not None

    def verify(
        self,
        *,
        now: datetime | None = None,
    ) -> SemanticIntegrityReport:
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("verification time must be timezone-aware")
        findings: list[IntegrityFinding] = []

        with closing(self._connect()) as db, db:
            result = db.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                findings.append(
                    IntegrityFinding(
                        "sqlite.integrity",
                        IntegritySeverity.ERROR,
                        "SQLite integrity_check did not return ok",
                    )
                )

            self._memory_findings(db, findings)
            self._memory_correction_findings(db, findings)
            self._social_findings(db, findings)
            self._chatgpt_findings(db, findings)
            self._fleet_findings(db, findings)
            self._audit_findings(db, findings)

        self._release_findings(findings)
        return SemanticIntegrityReport(
            checked_at=moment.astimezone(timezone.utc),
            findings=tuple(findings),
        )

    def _memory_findings(
        self,
        db: sqlite3.Connection,
        findings: list[IntegrityFinding],
    ) -> None:
        if not self._table(db, "memory_candidate"):
            return
        if not self._table(db, "memory_candidate_source"):
            findings.append(
                IntegrityFinding(
                    "memory.sources.table_missing",
                    IntegritySeverity.ERROR,
                    "memory_candidate exists without memory_candidate_source",
                )
            )
            return

        promoted = db.execute(
            """
            SELECT candidate_id
            FROM memory_candidate
            WHERE status='promoted'
            """
        ).fetchall()
        for row in promoted:
            count = db.execute(
                """
                SELECT COUNT(*)
                FROM memory_candidate_source
                WHERE candidate_id=?
                """,
                (row["candidate_id"],),
            ).fetchone()[0]
            if count < 1:
                findings.append(
                    IntegrityFinding(
                        "memory.promoted_without_source",
                        IntegritySeverity.ERROR,
                        f"promoted candidate {row['candidate_id']} has no source",
                    )
                )

        sources = db.execute(
            """
            SELECT candidate_id, message_id, session_id, role, content
            FROM memory_candidate_source
            """
        ).fetchall()
        has_messages = self._table(db, "conversation_messages")
        has_sessions = self._table(db, "conversation_sessions")
        has_imports = self._table(db, "chatgpt_memory_import_item")

        for source in sources:
            session_id = source["session_id"]
            if session_id.startswith("chatgpt-import:"):
                digest = session_id.split(":", 1)[1]
                if not has_imports:
                    findings.append(
                        IntegrityFinding(
                            "memory.import_source_table_missing",
                            IntegritySeverity.ERROR,
                            f"candidate {source['candidate_id']} uses missing import evidence table",
                        )
                    )
                    continue
                original = db.execute(
                    """
                    SELECT content
                    FROM chatgpt_memory_import_item
                    WHERE source_digest=? AND source_id=?
                    """,
                    (digest, source["message_id"]),
                ).fetchone()
                if original is None:
                    findings.append(
                        IntegrityFinding(
                            "memory.import_source_missing",
                            IntegritySeverity.ERROR,
                            f"candidate {source['candidate_id']} references missing ChatGPT evidence",
                        )
                    )
                elif original["content"] != source["content"]:
                    findings.append(
                        IntegrityFinding(
                            "memory.import_source_changed",
                            IntegritySeverity.ERROR,
                            f"candidate {source['candidate_id']} ChatGPT evidence content differs",
                        )
                    )
                continue

            if not has_messages or not has_sessions:
                findings.append(
                    IntegrityFinding(
                        "memory.conversation_source_table_missing",
                        IntegritySeverity.ERROR,
                        "conversation-backed memory exists without conversation tables",
                    )
                )
                continue
            original = db.execute(
                """
                SELECT session_id, role, content
                FROM conversation_messages
                WHERE id=?
                """,
                (source["message_id"],),
            ).fetchone()
            if original is None:
                findings.append(
                    IntegrityFinding(
                        "memory.conversation_source_missing",
                        IntegritySeverity.ERROR,
                        f"candidate {source['candidate_id']} references missing conversation evidence",
                    )
                )
                continue
            if (
                original["session_id"] != source["session_id"]
                or original["role"] != source["role"]
                or original["content"] != source["content"]
            ):
                findings.append(
                    IntegrityFinding(
                        "memory.conversation_source_changed",
                        IntegritySeverity.ERROR,
                        f"candidate {source['candidate_id']} source no longer matches original",
                    )
                )

    def _memory_correction_findings(
        self, db: sqlite3.Connection, findings: list[IntegrityFinding],
    ) -> None:
        """Validate optional reviewed correction lineage without mutating state."""
        if not self._table(db, "memory_candidate_correction"):
            return
        if not self._table(db, "memory_candidate"):
            findings.append(IntegrityFinding(
                "memory.correction.orphan_table", IntegritySeverity.ERROR,
                "correction lineage exists without candidate authority",
            ))
            return
        rows = db.execute(
            "SELECT c.new_candidate_id,c.old_candidate_id,"
            "n.status AS new_status,o.status AS old_status,"
            "n.principal_id AS new_principal,o.principal_id AS old_principal,"
            "n.audience_id AS new_audience,o.audience_id AS old_audience "
            "FROM memory_candidate_correction c "
            "LEFT JOIN memory_candidate n ON n.candidate_id=c.new_candidate_id "
            "LEFT JOIN memory_candidate o ON o.candidate_id=c.old_candidate_id"
        ).fetchall()
        for row in rows:
            replacement, previous = row["new_candidate_id"], row["old_candidate_id"]
            if row["new_status"] is None or row["old_status"] is None:
                findings.append(IntegrityFinding(
                    "memory.correction.source_missing", IntegritySeverity.ERROR,
                    f"correction {replacement} → {previous} has a missing candidate",
                ))
                continue
            if (
                row["new_principal"] != row["old_principal"]
                or row["new_audience"] != row["old_audience"]
            ):
                findings.append(IntegrityFinding(
                    "memory.correction.cross_scope", IntegritySeverity.ERROR,
                    f"correction {replacement} → {previous} crosses owner/audience",
                ))
            if (
                row["new_status"] == "promoted"
                and row["old_status"] != "revoked"
            ):
                findings.append(IntegrityFinding(
                    "memory.correction.not_settled", IntegritySeverity.ERROR,
                    f"correction {replacement} promoted without revoking {previous}",
                ))
            elif (
                row["new_status"] == "proposed"
                and row["old_status"] == "revoked"
            ):
                findings.append(IntegrityFinding(
                    "memory.correction.interrupted", IntegritySeverity.WARNING,
                    f"correction {replacement} is pending but {previous} was revoked",
                ))

    def _social_findings(
        self,
        db: sqlite3.Connection,
        findings: list[IntegrityFinding],
    ) -> None:
        if not self._table(db, "social_session_principal"):
            return
        if not self._table(db, "conversation_sessions"):
            findings.append(
                IntegrityFinding(
                    "social.session_table_missing",
                    IntegritySeverity.ERROR,
                    "principal bindings exist without conversation_sessions",
                )
            )
            return
        rows = db.execute(
            """
            SELECT session_id
            FROM social_session_principal
            """
        ).fetchall()
        for row in rows:
            if db.execute(
                "SELECT 1 FROM conversation_sessions WHERE id=?",
                (row["session_id"],),
            ).fetchone() is None:
                findings.append(
                    IntegrityFinding(
                        "social.binding_orphaned",
                        IntegritySeverity.ERROR,
                        f"principal binding references missing session {row['session_id']}",
                    )
                )

    def _chatgpt_findings(
        self,
        db: sqlite3.Connection,
        findings: list[IntegrityFinding],
    ) -> None:
        if not self._table(db, "chatgpt_memory_candidate"):
            return
        if not self._table(db, "memory_candidate"):
            findings.append(
                IntegrityFinding(
                    "chatgpt.candidate_table_missing",
                    IntegritySeverity.ERROR,
                    "ChatGPT migration mapping exists without memory_candidate",
                )
            )
            return
        rows = db.execute(
            """
            SELECT source_digest, source_id, candidate_id, principal_id
            FROM chatgpt_memory_candidate
            """
        ).fetchall()
        for row in rows:
            candidate = db.execute(
                """
                SELECT principal_id
                FROM memory_candidate
                WHERE candidate_id=?
                """,
                (row["candidate_id"],),
            ).fetchone()
            if candidate is None:
                findings.append(
                    IntegrityFinding(
                        "chatgpt.candidate_missing",
                        IntegritySeverity.ERROR,
                        f"ChatGPT mapping references missing candidate {row['candidate_id']}",
                    )
                )
            elif candidate["principal_id"] != row["principal_id"]:
                findings.append(
                    IntegrityFinding(
                        "chatgpt.principal_mismatch",
                        IntegritySeverity.ERROR,
                        f"ChatGPT candidate {row['candidate_id']} principal scope differs",
                    )
                )


    def _fleet_findings(
        self,
        db: sqlite3.Connection,
        findings: list[IntegrityFinding],
    ) -> None:
        if not self._table(db, "remote_standing_grant"):
            return
        if not self._table(db, "distributed_node_identity"):
            active_count = db.execute(
                """
                SELECT COUNT(*)
                FROM remote_standing_grant
                WHERE revoked=0
                """
            ).fetchone()[0]
            if active_count:
                findings.append(
                    IntegrityFinding(
                        "fleet.enrollment_table_missing",
                        IntegritySeverity.ERROR,
                        "active Fleet grants exist without durable node identities",
                    )
                )
            return

        rows = db.execute(
            """
            SELECT g.grant_id, g.node_id, n.retired
            FROM remote_standing_grant AS g
            LEFT JOIN distributed_node_identity AS n
              ON n.node_id=g.node_id
            WHERE g.revoked=0
              AND (n.node_id IS NULL OR n.retired<>0)
            ORDER BY g.grant_id
            """
        ).fetchall()
        for row in rows:
            state = "missing" if row["retired"] is None else "retired"
            findings.append(
                IntegrityFinding(
                    "fleet.active_grant_invalid_node",
                    IntegritySeverity.ERROR,
                    (
                        f"active grant {row['grant_id']} references "
                        f"{state} node {row['node_id']}"
                    ),
                )
            )

    def _audit_findings(
        self,
        db: sqlite3.Connection,
        findings: list[IntegrityFinding],
    ) -> None:
        if not self._table(db, "safe_audit_event"):
            return
        valid, detail = AuditChain(self.path).verify()
        if not valid:
            findings.append(
                IntegrityFinding(
                    "audit.chain_invalid",
                    IntegritySeverity.ERROR,
                    detail or "tamper-evident audit chain verification failed",
                )
            )

    def _release_findings(
        self,
        findings: list[IntegrityFinding],
    ) -> None:
        store = ReleaseStateStore(self.state_plane)
        active = store.active()
        if active is None:
            return
        release_id = active.get("release_id")
        if not isinstance(release_id, str) or not release_id:
            findings.append(
                IntegrityFinding(
                    "release.active_invalid",
                    IntegritySeverity.ERROR,
                    "active release record lacks release_id",
                )
            )
            return
        manifest = store.candidate(release_id)
        if manifest is None:
            findings.append(
                IntegrityFinding(
                    "release.manifest_missing",
                    IntegritySeverity.ERROR,
                    f"active release {release_id} has no candidate manifest",
                )
            )
            return
        if manifest.manifest_sha256 != active.get("manifest_sha256"):
            findings.append(
                IntegrityFinding(
                    "release.manifest_digest_mismatch",
                    IntegritySeverity.ERROR,
                    f"active release {release_id} manifest digest differs",
                )
            )
        if not store.accepted(release_id):
            findings.append(
                IntegrityFinding(
                    "release.acceptance_missing",
                    IntegritySeverity.ERROR,
                    f"active release {release_id} lacks protected acceptance history",
                )
            )
        with closing(self._connect()) as db, db:
            if not self._table(db, "safe_audit_event"):
                findings.append(
                    IntegrityFinding(
                        "release.audit_missing",
                        IntegritySeverity.ERROR,
                        f"active release {release_id} has no tamper-evident audit table",
                    )
                )
                return
            rows = db.execute(
                """
                SELECT payload_json
                FROM safe_audit_event
                WHERE event_type='release.activation.completed'
                ORDER BY sequence DESC
                """
            ).fetchall()
        matched = False
        for row in rows:
            try:
                import json
                payload = json.loads(row["payload_json"])
            except (TypeError, ValueError):
                continue
            if (
                payload.get("release_id") == release_id
                and payload.get("manifest_sha256")
                == manifest.manifest_sha256
            ):
                matched = True
                break
        if not matched:
            findings.append(
                IntegrityFinding(
                    "release.audit_completion_missing",
                    IntegritySeverity.ERROR,
                    f"active release {release_id} lacks completed activation audit evidence",
                )
            )
