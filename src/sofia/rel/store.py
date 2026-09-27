from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.rel.model import RelationshipContact
from sofia.social.model import PrincipalContext


class RelationshipStore:
    """Principal-bound relationship continuity backed by saved evidence."""

    def __init__(self,state_path:Path|str)->None:
        self.path=Path(state_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path,timeout=10) as db:
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

    def observe(
        self,
        *,
        principal:PrincipalContext,
        evidence_ref:str,
        occurred_at:datetime,
    )->RelationshipContact:
        if not isinstance(principal,PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        contact=RelationshipContact(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            display_name=principal.display_name,
            evidence_ref=evidence_ref,
            occurred_at=occurred_at,
        )
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            row=db.execute(
                "SELECT occurred_at FROM rel_contact WHERE principal_id=?",
                (principal.principal_id,),
            ).fetchone()
            if row is not None:
                previous=datetime.fromisoformat(row[0])
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

    def get(self,principal_id:str)->RelationshipContact|None:
        if not isinstance(principal_id,str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        with sqlite3.connect(self.path,timeout=10) as db:
            row=db.execute("""
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
