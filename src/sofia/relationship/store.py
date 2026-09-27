"""Principal-scoped relationship contact evidence."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.relationship.model import RelationshipContext
from sofia.social.principal import AuthenticatedPrincipal


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class RelationshipStore:
    """Record observed authenticated contact, not inferred affection/obligation."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS relationship_contacts (
                        principal_id TEXT PRIMARY KEY,
                        first_contact_at TEXT NOT NULL,
                        last_contact_at TEXT NOT NULL,
                        contact_count INTEGER NOT NULL CHECK(contact_count>=1)
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def observe_contact(
        self,
        principal: AuthenticatedPrincipal,
        *,
        occurred_at: datetime,
    ) -> RelationshipContext:
        if not isinstance(principal, AuthenticatedPrincipal):
            raise TypeError("AuthenticatedPrincipal required")
        moment = _utc(occurred_at)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT first_contact_at, last_contact_at, contact_count "
                    "FROM relationship_contacts WHERE principal_id=?",
                    (principal.principal_id,),
                ).fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO relationship_contacts "
                        "(principal_id, first_contact_at, last_contact_at, "
                        "contact_count) VALUES (?, ?, ?, 1)",
                        (
                            principal.principal_id,
                            moment.isoformat(),
                            moment.isoformat(),
                        ),
                    )
                    first = last = moment
                    count = 1
                else:
                    first = datetime.fromisoformat(row[0]).astimezone(timezone.utc)
                    last = datetime.fromisoformat(row[1]).astimezone(timezone.utc)
                    count = int(row[2])
                    if moment < last:
                        raise ValueError(
                            "contact clock moved backward; refusing to rewrite relationship timeline"
                        )
                    if moment > last:
                        count += 1
                        last = moment
                        db.execute(
                            "UPDATE relationship_contacts SET "
                            "last_contact_at=?, contact_count=? "
                            "WHERE principal_id=?",
                            (
                                last.isoformat(),
                                count,
                                principal.principal_id,
                            ),
                        )
        return RelationshipContext(
            principal_id=principal.principal_id,
            first_contact_at=first,
            last_contact_at=last,
            contact_count=count,
            observed_at=moment,
        )

    def context(
        self,
        principal: AuthenticatedPrincipal,
        *,
        now: datetime,
    ) -> RelationshipContext | None:
        if not isinstance(principal, AuthenticatedPrincipal):
            raise TypeError("AuthenticatedPrincipal required")
        moment = _utc(now)
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT first_contact_at, last_contact_at, contact_count "
                "FROM relationship_contacts WHERE principal_id=?",
                (principal.principal_id,),
            ).fetchone()
        if row is None:
            return None
        return RelationshipContext(
            principal_id=principal.principal_id,
            first_contact_at=datetime.fromisoformat(row[0]).astimezone(timezone.utc),
            last_contact_at=datetime.fromisoformat(row[1]).astimezone(timezone.utc),
            contact_count=int(row[2]),
            observed_at=moment,
        )
