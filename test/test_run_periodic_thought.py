"""Offline RUN periodic tests: no daemon, model, real clock, or notification."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run import (
    OpportunityPolicy,
    PeriodicThoughtGate,
    PeriodicThoughtRunner,
)

START = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
REFS = ("event-1",)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE original_data (value TEXT)")
        db.execute("INSERT INTO original_data VALUES ('keep')")
    return path


def gate(state, **overrides):
    return PeriodicThoughtGate(
        state,
        OpportunityPolicy(enabled=True, **overrides),
    )


def test_disabled_by_default_and_does_not_invoke_callback(state):
    scheduler = PeriodicThoughtGate(state, OpportunityPolicy())
    calls = []
    runner = PeriodicThoughtRunner(
        scheduler,
        lambda: calls.append(1) or "event-1",
    )
    assert runner.tick(now=START, source_refs=REFS).status == "disabled"
    assert calls == []
    assert scheduler.history() == ()
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT value FROM original_data").fetchone() == ("keep",)


def test_existing_database_and_bounded_policy_required(tmp_path):
    with pytest.raises(FileNotFoundError):
        PeriodicThoughtGate(
            tmp_path / "missing.db",
            OpportunityPolicy(enabled=True),
        )
    for overrides in (
        {"interval_seconds": 60},
        {"interval_seconds": 86401},
        {"max_attempts_per_utc_day": 0},
        {"quiet_hours_utc": (24, 3)},
    ):
        with pytest.raises(ValueError):
            OpportunityPolicy(**overrides)


def test_no_sources_active_user_and_quiet_hours_never_claim(state):
    scheduler = gate(state, quiet_hours_utc=(23, 7))
    assert scheduler.claim(now=START, source_refs=()).status == "no_evidence"
    assert scheduler.claim(
        now=START, source_refs=REFS, user_active=True
    ).status == "busy"
    assert scheduler.claim(
        now=START.replace(hour=23), source_refs=REFS
    ).status == "quiet"
    assert scheduler.claim(
        now=START.replace(hour=2), source_refs=REFS
    ).status == "quiet"
    assert scheduler.history() == ()


def test_equal_quiet_hours_is_explicit_full_day_quiet(state):
    scheduler = gate(state, quiet_hours_utc=(8, 8))
    assert scheduler.claim(now=START, source_refs=REFS).status == "quiet"


def test_duplicate_or_unbounded_source_ids_rejected(state):
    scheduler = gate(state)
    with pytest.raises(ValueError, match="distinct"):
        scheduler.claim(
            now=START,
            source_refs=("event-1", "event-1"),
        )
    with pytest.raises(ValueError, match="recorded event"):
        scheduler.claim(
            now=START,
            source_refs=("private user text!",),
        )


def test_one_per_interval_and_day_limit_survive_restart(state):
    first = gate(
        state,
        interval_seconds=1800,
        max_attempts_per_utc_day=2,
    )
    a = first.claim(now=START, source_refs=REFS)
    assert a.status == "claimed"
    assert first.claim(now=START, source_refs=REFS).status == "not_due"
    assert first.claim(
        now=START + timedelta(minutes=29),
        source_refs=REFS,
    ).status == "not_due"

    b = first.claim(
        now=START + timedelta(minutes=30),
        source_refs=REFS,
    )
    assert b.status == "claimed"
    assert b.slot_id != a.slot_id

    restarted = gate(
        state,
        interval_seconds=1800,
        max_attempts_per_utc_day=2,
    )
    assert restarted.claim(
        now=START + timedelta(minutes=60),
        source_refs=REFS,
    ).status == "quota"
    assert restarted.claim(
        now=START + timedelta(days=1),
        source_refs=REFS,
    ).status == "claimed"


def test_clock_rollback_is_not_treated_as_due(state):
    scheduler = gate(state)
    scheduler.claim(now=START, source_refs=REFS)
    assert scheduler.claim(
        now=START - timedelta(minutes=30),
        source_refs=REFS,
    ).status == "clock_uncertain"


def test_observed_event_recorded_only_after_callback_confirms_it(state):
    scheduler = gate(state)
    calls = []
    runner = PeriodicThoughtRunner(
        scheduler,
        lambda: calls.append("called") or "event-1",
    )
    result = runner.tick(now=START, source_refs=REFS)
    assert result.status == "reflected"
    assert result.event_id == "event-1"
    assert calls == ["called"]
    assert scheduler.history() == (
        (result.slot_id, "reflected", "event-1"),
    )


def test_no_event_is_not_misreported_as_thought(state):
    scheduler = gate(state)
    result = PeriodicThoughtRunner(
        scheduler,
        lambda: None,
    ).tick(now=START, source_refs=REFS)
    assert result.status == "no_event"
    assert result.event_id is None


def test_callback_failure_and_invented_event_are_audited(state):
    scheduler = gate(state)

    def broken():
        raise RuntimeError("model offline")

    with pytest.raises(RuntimeError, match="model offline"):
        PeriodicThoughtRunner(
            scheduler, broken
        ).tick(now=START, source_refs=REFS)
    assert scheduler.history()[0][1:] == ("failed", None)

    with pytest.raises(ValueError, match="source event"):
        PeriodicThoughtRunner(
            scheduler,
            lambda: "invented-event",
        ).tick(
            now=START + timedelta(minutes=30),
            source_refs=REFS,
        )
    assert scheduler.history()[-1][1:] == ("failed", None)


def test_finished_attempt_is_idempotent_but_not_rewritable(state):
    scheduler = gate(state)
    result = PeriodicThoughtRunner(
        scheduler,
        lambda: "event-1",
    ).tick(now=START, source_refs=REFS)
    assert scheduler.finish(
        result.slot_id,
        status="reflected",
        event_id="event-1",
    ) == result
    with pytest.raises(ValueError, match="cannot be rewritten"):
        scheduler.finish(result.slot_id, status="failed")


def test_naive_time_rejected(state):
    with pytest.raises(ValueError, match="aware"):
        gate(state).claim(
            now=datetime(2026, 9, 25),
            source_refs=REFS,
        )
