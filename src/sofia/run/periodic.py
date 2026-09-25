"""Durable, opt-in periodic opportunities while Sofía is actually running.

A wake is an opportunity, not proof of a thought or autonomous action. This
module starts no thread and sends no message. The host explicitly calls tick.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


def _utc(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("an aware time is required")
    return now.astimezone(timezone.utc)


@dataclass(frozen=True)
class OpportunityPolicy:
    enabled: bool = False
    interval_seconds: int = 1800
    max_attempts_per_utc_day: int = 8
    quiet_hours_utc: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean")
        if type(self.interval_seconds) is not int or not 300 <= self.interval_seconds <= 86400:
            raise ValueError("interval_seconds must be between 300 and 86400")
        if type(self.max_attempts_per_utc_day) is not int or not 1 <= self.max_attempts_per_utc_day <= 48:
            raise ValueError("max_attempts_per_utc_day must be between 1 and 48")
        if self.quiet_hours_utc is not None:
            hours = self.quiet_hours_utc
            if (
                not isinstance(hours, tuple)
                or len(hours) != 2
                or any(type(hour) is not int or not 0 <= hour < 24 for hour in hours)
            ):
                raise ValueError("quiet_hours_utc requires two UTC hours in 0..23")

    def is_quiet(self, now: datetime) -> bool:
        if self.quiet_hours_utc is None:
            return False
        start, end = self.quiet_hours_utc
        hour = _utc(now).hour
        if start == end:
            return True
        return (start <= hour < end) if start < end else (hour >= start or hour < end)


@dataclass(frozen=True)
class OpportunityResult:
    status: str
    slot_id: str | None = None
    event_id: str | None = None


class PeriodicThoughtGate:
    """Atomically reserve one bounded evidence-backed opportunity per slot."""

    def __init__(self, state_path: str | Path, policy: OpportunityPolicy) -> None:
        if not isinstance(policy, OpportunityPolicy):
            raise TypeError("explicit OpportunityPolicy required")
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("state database path required")
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing Sofía state database required")
        self.policy = policy
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_thought_opportunities (
                        slot_id TEXT PRIMARY KEY,
                        attempted_at TEXT NOT NULL,
                        day_utc TEXT NOT NULL,
                        source_refs_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN
                            ('claimed','reflected','no_event','failed')),
                        result_event_id TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def claim(
        self,
        *,
        now: datetime,
        source_refs: tuple[str, ...],
        user_active: bool = False,
    ) -> OpportunityResult:
        current = _utc(now)
        if not isinstance(user_active, bool):
            raise TypeError("user_active must be an observed boolean")
        if (
            not isinstance(source_refs, tuple)
            or len(source_refs) > 16
            or any(not isinstance(ref, str) or _REF.fullmatch(ref) is None for ref in source_refs)
        ):
            raise ValueError("supply at most 16 bounded recorded event identifiers")
        if len(set(source_refs)) != len(source_refs):
            raise ValueError("source event identifiers must be distinct")
        if not self.policy.enabled:
            return OpportunityResult("disabled")
        if user_active:
            return OpportunityResult("busy")
        if not source_refs:
            return OpportunityResult("no_evidence")
        if self.policy.is_quiet(current):
            return OpportunityResult("quiet")

        slot_id = (
            f"{self.policy.interval_seconds}:"
            f"{int(current.timestamp()) // self.policy.interval_seconds}"
        )
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    "SELECT status FROM run_thought_opportunities WHERE slot_id=?",
                    (slot_id,),
                ).fetchone()
                if existing is not None:
                    return OpportunityResult("not_due")

                last = db.execute(
                    "SELECT attempted_at FROM run_thought_opportunities "
                    "ORDER BY attempted_at DESC LIMIT 1"
                ).fetchone()
                if last is not None:
                    last_time = datetime.fromisoformat(last[0]).astimezone(timezone.utc)
                    elapsed = current - last_time
                    if elapsed < timedelta(0):
                        return OpportunityResult("clock_uncertain")
                    if elapsed < timedelta(seconds=self.policy.interval_seconds):
                        return OpportunityResult("not_due")

                count = db.execute(
                    "SELECT COUNT(*) FROM run_thought_opportunities WHERE day_utc=?",
                    (current.date().isoformat(),),
                ).fetchone()[0]
                if count >= self.policy.max_attempts_per_utc_day:
                    return OpportunityResult("quota")

                db.execute(
                    """
                    INSERT INTO run_thought_opportunities
                    (slot_id, attempted_at, day_utc, source_refs_json, status, result_event_id)
                    VALUES (?, ?, ?, ?, 'claimed', NULL)
                    """,
                    (
                        slot_id,
                        current.isoformat(),
                        current.date().isoformat(),
                        json.dumps(source_refs),
                    ),
                )
        return OpportunityResult("claimed", slot_id=slot_id)

    def finish(
        self,
        slot_id: str,
        *,
        status: str,
        event_id: str | None = None,
    ) -> OpportunityResult:
        if not isinstance(slot_id, str) or not slot_id:
            raise ValueError("previously claimed slot ID required")
        if status not in ("reflected", "no_event", "failed"):
            raise ValueError("completed attempt status required")
        if (status == "reflected") != (event_id is not None):
            raise ValueError("only a verified reflection may name its event ID")

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT source_refs_json, status, result_event_id
                    FROM run_thought_opportunities WHERE slot_id=?
                    """,
                    (slot_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("opportunity was never claimed")
                if event_id is not None and event_id not in json.loads(row[0]):
                    raise ValueError("reflection result lacks recorded source evidence")
                if row[1] != "claimed":
                    if (row[1], row[2]) != (status, event_id):
                        raise ValueError("finished opportunity cannot be rewritten")
                    return OpportunityResult(status, slot_id, event_id)
                db.execute(
                    """
                    UPDATE run_thought_opportunities
                    SET status=?, result_event_id=? WHERE slot_id=?
                    """,
                    (status, event_id, slot_id),
                )
        return OpportunityResult(status, slot_id, event_id)

    def history(self) -> tuple[tuple[str, str, str | None], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT slot_id, status, result_event_id
                    FROM run_thought_opportunities
                    ORDER BY attempted_at, slot_id
                    """
                )
            )


class PeriodicThoughtRunner:
    """Explicit host-invoked tick around an existing reflection operation."""

    def __init__(
        self,
        gate: PeriodicThoughtGate,
        reflect_one: Callable[[], str | None],
    ) -> None:
        if not isinstance(gate, PeriodicThoughtGate) or not callable(reflect_one):
            raise TypeError("gate and callable reflection operation required")
        self.gate = gate
        self.reflect_one = reflect_one

    def tick(
        self,
        *,
        now: datetime,
        source_refs: tuple[str, ...],
        user_active: bool = False,
    ) -> OpportunityResult:
        claimed = self.gate.claim(
            now=now,
            source_refs=source_refs,
            user_active=user_active,
        )
        if claimed.status != "claimed":
            return claimed
        try:
            event_id = self.reflect_one()
            if event_id is None:
                return self.gate.finish(claimed.slot_id, status="no_event")
            if not isinstance(event_id, str) or event_id not in source_refs:
                raise ValueError(
                    "reflection callback did not confirm a supplied source event"
                )
            return self.gate.finish(
                claimed.slot_id,
                status="reflected",
                event_id=event_id,
            )
        except Exception:
            self.gate.finish(claimed.slot_id, status="failed")
            raise
