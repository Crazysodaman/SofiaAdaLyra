from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.rel.model import RelationshipContact
from sofia.social.model import PrincipalContext
from sofia.state.json_repository import JsonStateRepository
from sofia.state.namespaces import REL_CONTACT_OBSERVATION
from sofia.state.plane import StatePlane, StatePlaneConflictError


class RelationshipStore:
    """Principal-bound latest contact plus append-only contact evidence."""

    def __init__(
        self,
        state_path: Path | str,
        *,
        state_plane: StatePlane | None = None,
    ) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._history = (
            JsonStateRepository(state_plane, REL_CONTACT_OBSERVATION)
            if state_plane is not None
            else None
        )
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS rel_contact (
                    principal_id TEXT PRIMARY KEY,
                    audience_id TEXT NOT NULL,
                    display_name TEXT,
                    evidence_ref TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _history_value(
        *,
        principal: PrincipalContext,
        evidence_ref: str,
        occurred_at: datetime,
    ) -> dict:
        return {
            "principal_id": principal.principal_id,
            "audience_id": principal.audience_id,
            "audience_kind": principal.audience_kind.value,
            "display_name": principal.display_name,
            "evidence_ref": evidence_ref,
            "occurred_at": occurred_at.isoformat(),
        }

    def _append_history(
        self,
        *,
        principal: PrincipalContext,
        evidence_ref: str,
        occurred_at: datetime,
    ) -> None:
        if self._history is None:
            return
        value = self._history_value(
            principal=principal,
            evidence_ref=evidence_ref,
            occurred_at=occurred_at,
        )
        try:
            self._history.create(
                evidence_ref,
                value,
                principal_id=principal.principal_id,
                updated_at=occurred_at,
                source=evidence_ref,
            )
        except StatePlaneConflictError:
            existing = self._history.get(
                evidence_ref,
                principal_id=principal.principal_id,
            )
            if existing is None or existing[0] != value:
                raise ValueError(
                    "relationship observation ID already belongs to different evidence"
                )

    def observe(
        self,
        *,
        principal: PrincipalContext,
        evidence_ref: str,
        occurred_at: datetime,
    ) -> RelationshipContact:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        contact = RelationshipContact(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            display_name=principal.display_name,
            evidence_ref=evidence_ref,
            occurred_at=occurred_at,
        )

        # Preserve append-only evidence before updating the latest-contact cache.
        self._append_history(
            principal=principal,
            evidence_ref=contact.evidence_ref,
            occurred_at=contact.occurred_at,
        )

        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            row = db.execute(
                "SELECT occurred_at FROM rel_contact WHERE principal_id=?",
                (principal.principal_id,),
            ).fetchone()
            if row is not None:
                previous = datetime.fromisoformat(row[0])
                if occurred_at < previous:
                    raise ValueError("relationship contact clock moved backward")
            db.execute("""
                INSERT INTO rel_contact(
                    principal_id,audience_id,display_name,evidence_ref,occurred_at
                )
                VALUES(?,?,?,?,?)
                ON CONFLICT(principal_id) DO UPDATE SET
                    audience_id=excluded.audience_id,
                    display_name=excluded.display_name,
                    evidence_ref=excluded.evidence_ref,
                    occurred_at=excluded.occurred_at
            """,(
                contact.principal_id,
                contact.audience_id,
                contact.display_name,
                contact.evidence_ref,
                contact.occurred_at.isoformat(),
            ))
        return contact

    def get(self, principal_id: str) -> RelationshipContact | None:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            row = db.execute("""
                SELECT principal_id,audience_id,display_name,evidence_ref,occurred_at
                FROM rel_contact WHERE principal_id=?
            """,(principal_id,)).fetchone()
        if row is None:
            return None
        return RelationshipContact(
            principal_id=row[0],
            audience_id=row[1],
            display_name=row[2],
            evidence_ref=row[3],
            occurred_at=datetime.fromisoformat(row[4]),
        )

    def history(
        self,
        principal_id: str,
    ) -> tuple[RelationshipContact, ...]:
        """Return append-only observed contacts for one authenticated principal."""
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        if self._history is None:
            latest = self.get(principal_id)
            return () if latest is None else (latest,)
        result: list[RelationshipContact] = []
        for value, _record in self._history.list(
            principal_id=principal_id,
        ):
            result.append(RelationshipContact(
                principal_id=value["principal_id"],
                audience_id=value["audience_id"],
                display_name=value.get("display_name"),
                evidence_ref=value["evidence_ref"],
                occurred_at=datetime.fromisoformat(value["occurred_at"]),
            ))
        return tuple(sorted(
            result,
            key=lambda item: (item.occurred_at, item.evidence_ref),
        ))
