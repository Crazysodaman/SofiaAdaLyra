from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from sofia.dev.release_store import ReleaseStateStore
from sofia.state.plane import StatePlane


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

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
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

        with self._connect() as db:
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
            self._social_findings(db, findings)
            self._chatgpt_findings(db, findings)

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
