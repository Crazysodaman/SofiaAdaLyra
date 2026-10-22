"""Read-only fulfillment aggregate over canonical LIFE records.

Fulfillment is a bounded factual summary of what Sofía's independent life
actually produced in a window: completed forge projects, kept artifacts,
recorded experiences, hobby time, and the state of durable interests. It
is derived data only — it grants no capability, asserts no authority,
and never feeds back into tests or contracts as hidden state.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

from .model import aware


@dataclass(frozen=True, slots=True)
class FulfillmentReport:
    """Bounded factual window summary; per-hobby counts sort by hobby name."""

    window_start: datetime
    window_end: datetime
    projects_completed: int
    artifacts_kept: int
    experiences_recorded: int
    hobby_engagements: int
    hobby_minutes: int
    engagements_by_hobby: tuple[tuple[str, int], ...] = field(default=())
    active_interests: int = 0
    retired_interests_window: tuple[tuple[str, str], ...] = field(default=())


class FulfillmentReader:
    """Aggregate canonical LIFE tables without mutating anything."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        # Read-only role: the reader creates no tables. LIFE stores and the
        # coordinator must have deployed the canonical schema first.
        self._guard = CanonicalSQLiteGuard(self.path)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(read_only=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def report(
        self, *, now: datetime, audience_id: str, window_days: int = 30,
    ) -> FulfillmentReport:
        aware(now, "now")
        if not isinstance(window_days, int) or not 1 <= window_days <= 730:
            raise ValueError("window_days must be an int in 1..730")
        if not isinstance(audience_id, str) or not audience_id.strip():
            raise ValueError("audience_id must be bounded text")
        window_start = (now - timedelta(days=window_days)).astimezone(timezone.utc)
        start = window_start.isoformat()
        end = now.astimezone(timezone.utc).isoformat()
        audience = audience_id.strip()
        with closing(self._connect()) as db:
            projects_completed = int(db.execute(
                """SELECT COUNT(DISTINCT e.project_id) FROM life_project_event e
                WHERE e.to_status='completed' AND e.occurred_at>=? AND e.occurred_at<=?""",
                (start, end),
            ).fetchone()[0])
            artifacts_kept = int(db.execute(
                """SELECT COUNT(*) FROM life_artifact_evaluation
                WHERE preserve_for_research=1 AND evaluated_at>=? AND evaluated_at<=?""",
                (start, end),
            ).fetchone()[0])
            experiences_recorded = int(db.execute(
                """SELECT COUNT(*) FROM life_experience
                WHERE audience_id=? AND recorded_at>=? AND recorded_at<=?""",
                (audience, start, end),
            ).fetchone()[0])
            hobby_rows = db.execute(
                """SELECT hobby_name, COUNT(*) AS count,
                COALESCE(SUM(duration_minutes),0) AS minutes
                FROM life_hobby_engagement
                WHERE audience_id=? AND engaged_at>=? AND engaged_at<=?
                GROUP BY hobby_name ORDER BY hobby_name""",
                (audience, start, end),
            ).fetchall()
            engagements_by_hobby = tuple(
                (row["hobby_name"], int(row["count"])) for row in hobby_rows
            )
            hobby_minutes = int(sum(row["minutes"] for row in hobby_rows))
            interest_rows = db.execute(
                """SELECT name,context,status,recorded_at FROM (
                    SELECT name,context,status,recorded_at,
                    RANK() OVER (PARTITION BY name,context ORDER BY revision DESC) latest
                    FROM life_interest_revision WHERE audience_id=?
                ) WHERE latest=1""",
                (audience,),
            ).fetchall()
            active_interests = int(sum(
                row["status"] == "active" for row in interest_rows
            ))
            # Retirement is an event: only retirements whose latest revision
            # landed inside the requested window belong in the window count.
            retired_interests = tuple(
                (row["name"], row["context"]) for row in interest_rows
                if row["status"] == "retired"
                and start <= row["recorded_at"] <= end
            )
        return FulfillmentReport(
            window_start=window_start,
            window_end=now.astimezone(timezone.utc),
            projects_completed=projects_completed,
            artifacts_kept=artifacts_kept,
            experiences_recorded=experiences_recorded,
            hobby_engagements=int(sum(item[1] for item in engagements_by_hobby)),
            hobby_minutes=hobby_minutes,
            engagements_by_hobby=engagements_by_hobby,
            active_interests=active_interests,
            retired_interests_window=retired_interests,
        )
