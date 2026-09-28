from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.social.model import AudienceKind, PrincipalContext


class SocialSessionStore:
    """Durable binding between one conversation session and one principal/audience."""

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS social_session_principal (
                    session_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    audience_kind TEXT NOT NULL,
                    display_name TEXT,
                    bound_at TEXT NOT NULL
                )
                """
            )

    def bind(
        self,
        *,
        session_id: str,
        principal: PrincipalContext,
    ) -> PrincipalContext:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty")
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT principal_id, audience_id, audience_kind, display_name
                FROM social_session_principal
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            expected = (
                principal.principal_id,
                principal.audience_id,
                principal.audience_kind.value,
                principal.display_name,
            )
            if row is not None:
                actual = (
                    row["principal_id"],
                    row["audience_id"],
                    row["audience_kind"],
                    row["display_name"],
                )
                if actual != expected:
                    connection.rollback()
                    raise PermissionError(
                        "conversation session is already bound to another "
                        "principal or audience"
                    )
                connection.rollback()
                return principal

            connection.execute(
                """
                INSERT INTO social_session_principal (
                    session_id,
                    principal_id,
                    audience_id,
                    audience_kind,
                    display_name,
                    bound_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    principal.principal_id,
                    principal.audience_id,
                    principal.audience_kind.value,
                    principal.display_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
        return principal

    def get(self, session_id: str) -> PrincipalContext | None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty")
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                """
                SELECT principal_id, audience_id, audience_kind, display_name
                FROM social_session_principal
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return PrincipalContext(
            principal_id=row["principal_id"],
            audience_id=row["audience_id"],
            audience_kind=AudienceKind(row["audience_kind"]),
            display_name=row["display_name"],
        )
