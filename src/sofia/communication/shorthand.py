"""Owner-taught shorthand interpretation records (Sofia Core B05).

Expansion of the owner's typed shorthand is interpretation evidence, never a
command source. Every entry must be taught by the authenticated owner with a
canonical provenance ref; rows are append-only CAS-guarded revisions scoped
to one owner principal and audience, so a mapping learned in one private
channel can never silently rewrite another audience's readings. Withdrawn
entries are recorded, not deleted, keeping the learning history auditable.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_TOKEN = re.compile(r"^[a-z][a-z0-9'-]{1,39}$")
_EXPANSION = re.compile(r"\S.{0,78}")


class ShorthandStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class ShorthandConcurrencyError(RuntimeError):
    """A taught shorthand revision raced with another authoritative write."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("shorthand timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ShorthandRecord:
    """One append-only owner-taught shorthand revision."""

    token: str
    principal_id: str
    audience_id: str
    expansion: str
    note: str | None
    evidence_ref: str
    status: ShorthandStatus
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or _TOKEN.fullmatch(self.token) is None:
            raise ValueError(
                "token must be lowercase letters/digits starting with a letter"
            )
        for name in ("principal_id", "audience_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ValueError(f"{name} must be bounded nonempty text")
        if not isinstance(self.expansion, str) or _EXPANSION.fullmatch(
            self.expansion
        ) is None:
            raise ValueError("expansion must be bounded nonempty text")
        if self.note is not None and (
            not isinstance(self.note, str)
            or not self.note.strip()
            or len(self.note.strip()) > 200
        ):
            raise ValueError("note must be None or bounded nonempty text")
        if (
            not isinstance(self.evidence_ref, str)
            or not self.evidence_ref.strip()
            or len(self.evidence_ref) > 300
        ):
            raise ValueError("shorthand evidence_ref is required")
        if not isinstance(self.status, ShorthandStatus):
            raise TypeError("status must be ShorthandStatus")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("shorthand revision must be a positive integer")
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


@dataclass(frozen=True, slots=True)
class ShorthandMatch:
    """One whole-word token reading found inside current message text."""

    token: str
    expansion: str
    confidence_note: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not _TOKEN.fullmatch(self.token):
            raise ValueError("match token must be a canonical token")
        if not isinstance(self.expansion, str) or not self.expansion.strip():
            raise ValueError("match expansion must be nonempty text")
        if self.confidence_note is not None and not isinstance(
            self.confidence_note, str,
        ):
            raise TypeError("confidence_note must be None or a string")


class ShorthandStore:
    """Canonical append-only persistence for owner-taught shorthand."""

    MAX_MATCHES = 12

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS owner_shorthand_revision (
                    token TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    expansion TEXT NOT NULL,
                    note TEXT,
                    evidence_ref TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
                    revision INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(token,principal_id,audience_id,revision)
                );
                CREATE INDEX IF NOT EXISTS owner_shorthand_current
                    ON owner_shorthand_revision(principal_id,audience_id,token);
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _record(row: sqlite3.Row) -> ShorthandRecord:
        return ShorthandRecord(
            token=row["token"], principal_id=row["principal_id"],
            audience_id=row["audience_id"], expansion=row["expansion"],
            note=row["note"], evidence_ref=row["evidence_ref"],
            status=ShorthandStatus(row["status"]),
            revision=int(row["revision"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self, value: ShorthandRecord, *, expected_revision: int | None,
    ) -> ShorthandRecord:
        """CAS-append one taught shorthand revision under one scope."""
        stamp = _utc(value.recorded_at)
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT revision,status FROM owner_shorthand_revision
                WHERE token=? AND principal_id=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (value.token, value.principal_id, value.audience_id),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ShorthandConcurrencyError(
                        "shorthand already exists; reload and revise with "
                        f"expected_revision={int(row['revision'])}"
                    )
                if value.revision != 1 or value.status is not ShorthandStatus.ACTIVE:
                    raise ShorthandConcurrencyError(
                        "creating a mapping requires active revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise ShorthandConcurrencyError(
                        "revision changed or shorthand is absent; "
                        "reload before revising"
                    )
                if value.revision != expected_revision + 1:
                    raise ShorthandConcurrencyError(
                        "next revision must follow the expected revision"
                    )
            db.execute(
                """INSERT INTO owner_shorthand_revision VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    value.token, value.principal_id, value.audience_id,
                    value.expansion, value.note, value.evidence_ref,
                    value.status.value, value.revision,
                    stamp.isoformat(),
                ),
            )
        return value

    def current(
        self, token: str, *, principal_id: str, audience_id: str,
    ) -> ShorthandRecord | None:
        if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
            raise ValueError("token must be a canonical token")
        return self._latest(token, principal_id, audience_id)

    def _latest(
        self, token: str, principal_id: str, audience_id: str,
    ) -> ShorthandRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT * FROM owner_shorthand_revision
                WHERE token=? AND principal_id=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (token, principal_id, audience_id),
            ).fetchone()
        return None if row is None else self._record(row)

    def history(
        self, token: str, *, principal_id: str, audience_id: str,
    ) -> tuple[ShorthandRecord, ...]:
        if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
            raise ValueError("token must be a canonical token")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT * FROM owner_shorthand_revision
                WHERE token=? AND principal_id=? AND audience_id=?
                ORDER BY revision ASC""",
                (token, principal_id, audience_id),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def interpretations(
        self,
        tokens: tuple[str, ...],
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[ShorthandMatch, ...]:
        """Deterministic whole-word readings for one owner scope.

        Only ACTIVE mappings are returned, in input order, capped at
        MAX_MATCHES; unknown tokens produce nothing rather than a guess.
        """
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be bounded nonempty text")
        if not isinstance(audience_id, str) or not audience_id.strip():
            raise ValueError("audience_id must be bounded nonempty text")
        seen: list[str] = []
        for token in tokens:
            if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
                raise ValueError("interpretation tokens must be canonical tokens")
            if token not in seen:
                seen.append(token)
        matches: list[ShorthandMatch] = []
        for token in seen:
            record = self._latest(token, principal_id, audience_id)
            if (
                record is None
                or record.status is not ShorthandStatus.ACTIVE
            ):
                continue
            matches.append(ShorthandMatch(
                token=record.token,
                expansion=record.expansion,
                confidence_note=record.note,
            ))
            if len(matches) >= self.MAX_MATCHES:
                break
        return tuple(matches)

    def taught(
        self, *, principal_id: str, audience_id: str, limit: int = 32,
    ) -> tuple[ShorthandRecord, ...]:
        """Current ACTIVE mappings inside one scope, newest-first."""
        if not isinstance(limit, int) or not 1 <= limit <= 256:
            raise ValueError("limit must be an int in 1..256")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT * FROM owner_shorthand_revision
                WHERE principal_id=? AND audience_id=?
                GROUP BY token
                HAVING MAX(revision)""",
                (principal_id, audience_id),
            ).fetchall()
        records = [
            self._record(row) for row in rows
            if row["status"] == ShorthandStatus.ACTIVE.value
        ]
        records.sort(key=lambda item: (-item.revision, item.token))
        return tuple(records[:limit])
