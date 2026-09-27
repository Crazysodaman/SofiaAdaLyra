from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import NAMESPACE_URL, UUID, uuid5

from sofia.memory.chatgpt_import_store import ChatGPTMemoryImportStore
from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage
from sofia.social.principals import SPARKS_PRINCIPAL_ID


class ChatGPTMemoryMigrationService:
    """
    Bridge exact ChatGPT import evidence into reviewed Sofía memory.

    Import creates deterministic PROPOSED candidates. Promotion is explicit and
    principal-scoped. Imported summaries never bypass the reviewed lifecycle.
    """

    def __init__(
        self,
        state_path: Path | str,
        *,
        imports: ChatGPTMemoryImportStore | None = None,
        candidates: DurableMemoryCandidateStore | None = None,
    ) -> None:
        self.path = Path(state_path)
        self.imports = imports or ChatGPTMemoryImportStore(self.path)
        self.candidates = candidates or DurableMemoryCandidateStore(self.path)
        self._owns_imports = imports is None
        self._owns_candidates = candidates is None
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chatgpt_memory_candidate (
                        source_digest TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        candidate_id TEXT NOT NULL UNIQUE,
                        principal_id TEXT NOT NULL,
                        proposed_at TEXT NOT NULL,
                        promoted_at TEXT,
                        reviewed_by TEXT,
                        PRIMARY KEY (source_digest, source_id)
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _candidate_id(
        source_digest: str,
        source_id: str,
    ) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"sofia:chatgpt-memory:{source_digest}:{source_id}",
        )

    def propose_batch(
        self,
        source_digest: str,
        *,
        principal_id: str = SPARKS_PRINCIPAL_ID,
    ) -> tuple[UUID, ...]:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        batch = self.imports.load_batch(source_digest)
        if batch is None:
            raise LookupError("ChatGPT import batch does not exist")

        proposed: list[UUID] = []
        session_id = f"chatgpt-import:{source_digest}"
        for position, item in enumerate(batch.items):
            candidate_id = self._candidate_id(
                source_digest,
                item.source_id,
            )
            created_at = item.source_created_at or batch.observed_at
            source = SourceMessage(
                message_id=item.source_id,
                session_id=session_id,
                role="imported_chatgpt_memory",
                content=item.content,
                created_at=created_at,
                position=position,
            )
            expected = MemoryCandidate(
                candidate_id=candidate_id,
                content=item.content,
                sources=(source,),
                created_at=created_at,
                principal_id=principal_id,
                audience_id=None,
            )

            existing = self.candidates.get(candidate_id)
            if existing is None:
                self.candidates.propose(expected)
            elif existing != expected:
                raise RuntimeError(
                    "deterministic ChatGPT candidate ID has conflicting content"
                )

            with closing(self._connect()) as db:
                with db:
                    row = db.execute(
                        """
                        SELECT candidate_id, principal_id
                        FROM chatgpt_memory_candidate
                        WHERE source_digest=? AND source_id=?
                        """,
                        (source_digest, item.source_id),
                    ).fetchone()
                    if row is None:
                        db.execute(
                            """
                            INSERT INTO chatgpt_memory_candidate (
                                source_digest,
                                source_id,
                                candidate_id,
                                principal_id,
                                proposed_at,
                                promoted_at,
                                reviewed_by
                            )
                            VALUES (?, ?, ?, ?, ?, NULL, NULL)
                            """,
                            (
                                source_digest,
                                item.source_id,
                                str(candidate_id),
                                principal_id,
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    elif (
                        row["candidate_id"] != str(candidate_id)
                        or row["principal_id"] != principal_id
                    ):
                        raise RuntimeError(
                            "ChatGPT import mapping conflicts with candidate"
                        )
            proposed.append(candidate_id)
        return tuple(proposed)

    def promote(
        self,
        candidate_id: UUID,
        *,
        approved_by: str,
        at: datetime,
    ) -> None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if approved_by != "Sparks":
            raise PermissionError(
                "ChatGPT memory promotion currently requires Sparks review"
            )
        if not isinstance(at, datetime):
            raise TypeError("at must be a datetime")
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be timezone-aware")

        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT principal_id, promoted_at, reviewed_by
                FROM chatgpt_memory_candidate
                WHERE candidate_id=?
                """,
                (str(candidate_id),),
            ).fetchone()
        if row is None:
            raise LookupError(
                "candidate is not linked to ChatGPT import evidence"
            )
        if row["principal_id"] != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "ChatGPT memory candidate belongs to another principal"
            )

        status = self.candidates.status(candidate_id)
        if status is CandidateStatus.PROPOSED:
            self.candidates.promote(candidate_id)
        elif status is not CandidateStatus.PROMOTED:
            raise ValueError(
                "only proposed ChatGPT candidates may be promoted"
            )

        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    UPDATE chatgpt_memory_candidate
                    SET promoted_at=COALESCE(promoted_at, ?),
                        reviewed_by=COALESCE(reviewed_by, ?)
                    WHERE candidate_id=?
                    """,
                    (
                        at.astimezone(timezone.utc).isoformat(),
                        approved_by,
                        str(candidate_id),
                    ),
                )

    def promote_batch(
        self,
        source_digest: str,
        *,
        approved_by: str,
        at: datetime,
    ) -> tuple[UUID, ...]:
        candidate_ids = self.propose_batch(source_digest)
        for candidate_id in candidate_ids:
            self.promote(
                candidate_id,
                approved_by=approved_by,
                at=at,
            )
        return candidate_ids

    def close(self) -> None:
        if self._owns_candidates:
            self.candidates.close()
        if self._owns_imports:
            self.imports.close()
