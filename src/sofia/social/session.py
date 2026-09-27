"""Durable exact binding between a conversation session and its audience."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from sofia.social.principal import (
    Audience,
    AudienceScope,
    AuthenticatedPrincipal,
    PrincipalKind,
)


@dataclass(frozen=True, slots=True)
class SocialSessionBinding:
    session_id: str
    principal: AuthenticatedPrincipal
    audience: Audience
    bound_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id required")
        if not isinstance(self.principal, AuthenticatedPrincipal):
            raise TypeError("principal must be AuthenticatedPrincipal")
        if not isinstance(self.audience, Audience):
            raise TypeError("audience must be Audience")
        if (
            self.audience.member_principal_ids
            and self.principal.principal_id
            not in self.audience.member_principal_ids
        ):
            raise ValueError("principal must belong to audience")
        if self.bound_at.tzinfo is None or self.bound_at.utcoffset() is None:
            raise ValueError("bound_at must be timezone-aware")


class SocialSessionBindingStore:
    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS social_session_bindings (
                        session_id TEXT PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        principal_kind TEXT NOT NULL,
                        principal_source TEXT NOT NULL,
                        principal_display_name TEXT,
                        audience_id TEXT NOT NULL,
                        audience_scope TEXT NOT NULL,
                        audience_members_json TEXT NOT NULL,
                        bound_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _from_row(row: tuple) -> SocialSessionBinding:
        principal = AuthenticatedPrincipal(
            principal_id=row[1],
            kind=PrincipalKind(row[2]),
            source=row[3],
            display_name=row[4],
        )
        audience = Audience(
            audience_id=row[5],
            scope=AudienceScope(row[6]),
            member_principal_ids=tuple(json.loads(row[7])),
        )
        return SocialSessionBinding(
            session_id=row[0],
            principal=principal,
            audience=audience,
            bound_at=datetime.fromisoformat(row[8]).astimezone(timezone.utc),
        )

    def get(self, session_id: str) -> SocialSessionBinding | None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT session_id, principal_id, principal_kind, "
                "principal_source, principal_display_name, audience_id, "
                "audience_scope, audience_members_json, bound_at "
                "FROM social_session_bindings WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def bind(
        self,
        session_id: str,
        *,
        principal: AuthenticatedPrincipal,
        audience: Audience,
        at: datetime,
    ) -> SocialSessionBinding:
        desired = SocialSessionBinding(
            session_id=session_id,
            principal=principal,
            audience=audience,
            bound_at=at.astimezone(timezone.utc),
        )
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT session_id, principal_id, principal_kind, "
                    "principal_source, principal_display_name, audience_id, "
                    "audience_scope, audience_members_json, bound_at "
                    "FROM social_session_bindings WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                if row is not None:
                    current = self._from_row(row)
                    if (
                        current.principal.principal_id
                        != principal.principal_id
                        or current.audience.audience_id
                        != audience.audience_id
                    ):
                        raise PermissionError(
                            "conversation session is already bound to a "
                            "different principal or audience"
                        )
                    return current
                db.execute(
                    "INSERT INTO social_session_bindings "
                    "(session_id, principal_id, principal_kind, "
                    "principal_source, principal_display_name, audience_id, "
                    "audience_scope, audience_members_json, bound_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        principal.principal_id,
                        principal.kind.value,
                        principal.source,
                        principal.display_name,
                        audience.audience_id,
                        audience.scope.value,
                        json.dumps(
                            list(audience.member_principal_ids),
                            separators=(",", ":"),
                        ),
                        desired.bound_at.isoformat(),
                    ),
                )
        return desired
