"""Pure offline RUN1 tests: no daemon, model, real clock, or notification."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run.periodic import (
    OpportunityPolicy, PeriodicThoughtGate, PeriodicThoughtRunner,
)

START = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
REFS = ("event-1",)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE original_data (value TEXT)")
        db.execute("INSERT INTO original_data VALUES ('keep')")
    return path


def gate(state, **overrides):
    return PeriodicThoughtGate(state, OpportunityPolicy(enabled=True, **overrides))


def test_disabled_by_default_and_does_not_invoke_callback(state):
    scheduler = PeriodicThoughtGate(state, OpportunityPolicy())
    calls = []
    runner = PeriodicThoughtRunner(scheduler, lambda: calls.append(1) or "event-1")
    assert runner.tick(now=START, source_refs=REFS).status == "disabled"
    assert calls == []
    assert scheduler.history() == ()
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT value FROM original_data").fetchone() == ("keep",)


def test_existing_database_is_required_and_policy_values_are_bounded(tmp_path):
    with pytest.raises(FileNotFoundError, match="existing"):
        PeriodicThoughtGate(tmp_path / "missing.db", OpportunityPolicy(enabled=True))
    assert not (tmp_path / "missing.db").exists()
    for overrides in ({"interval_seconds": 0}, {"interval_seconds": 60},
                      {"max_attempts_per_utc_day": 0},
                      {"quiet_hours_utc": (12, 12)},
                      {"quiet_hours_utc": (24, 3)}):
        with pytest.raises(ValueError):
            OpportunityPolicy(**overrides)
    with pytest.raises(ValueError, match="aware"):
        gate_path = tmp_path / "other.db"
        with sqlite3.connect(gate_path):
            pass
        PeriodicThoughtGate(gate_path, OpportunityPolicy(enabled=True)).claim(
            now=datetime(2026, 9, 20), source_refs=REFS)


def test_no_sources_active_user_and_quiet_hours_never_claim(state):
    scheduler = gate(state, quiet_hours_utc=(23, 7))
    assert scheduler.claim(now=START, source_refs=()).status == "no_evidence"
    assert scheduler.claim(now=START, source_refs=REFS, user_active=True).status == "busy"
    assert scheduler.claim(now=START.replace(hour=23), source_refs=REFS).status == "quiet"
    assert scheduler.claim(now=START.replace(hour=2), source_refs=REFS).status == "quiet"
    assert scheduler.history() == ()


def test_one_per_interval_and_day_limit_survive_restart(state):
    first = gate(state, interval_seconds=1800, max_attempts_per_utc_day=2)
    a = first.claim(now=START, source_refs=REFS)
    assert a.status == "claimed"
    assert first.claim(now=START, source_refs=REFS).status == "not_due"
    # A changed interval policy cannot bypass the last-attempt cooldown.
    assert gate(state, interval_seconds=3600).claim(
        now=START + timedelta(seconds=1), source_refs=REFS).status == "not_due"
    assert first.claim(now=START + timedelta(minutes=29), source_refs=REFS).status == "not_due"
    b = first.claim(now=START + timedelta(minutes=30), source_refs=REFS)
    assert b.status == "claimed" and b.slot_id != a.slot_id
    assert gate(state, interval_seconds=1800, max_attempts_per_utc_day=2).claim(
        now=START + timedelta(minutes=60), source_refs=REFS).status == "quota"
    assert first.claim(now=START + timedelta(days=1), source_refs=REFS).status == "claimed"
    assert len(first.history()) == 3


def test_observed_event_is_recorded_only_after_callback_confirms_it(state):
    scheduler = gate(state)
    calls = []
    runner = PeriodicThoughtRunner(scheduler,
                                   lambda: calls.append("called") or "event-1")
    result = runner.tick(now=START, source_refs=REFS)
    assert result.status == "reflected" and result.event_id == "event-1"
    assert calls == ["called"]
    assert runner.tick(now=START, source_refs=REFS).status == "not_due"
    assert calls == ["called"]
    assert gate(state).history() == ((result.slot_id, "reflected", "event-1"),)
    assert gate(state).finish(result.slot_id, status="reflected", event_id="event-1") == result
    with pytest.raises(ValueError, match="cannot be rewritten"):
        scheduler.finish(result.slot_id, status="failed")


def test_no_event_is_not_misreported_as_a_thought(state):
    scheduler = gate(state)
    result = PeriodicThoughtRunner(scheduler, lambda: None).tick(
        now=START, source_refs=REFS)
    assert result.status == "no_event" and result.event_id is None
    assert scheduler.history()[0][1:] == ("no_event", None)


def test_callback_failure_and_unsupported_event_are_audited_not_swallowed(state):
    scheduler = gate(state)
    def broken():
        raise RuntimeError("model offline")
    with pytest.raises(RuntimeError, match="model offline"):
        PeriodicThoughtRunner(scheduler, broken).tick(now=START, source_refs=REFS)
    assert scheduler.history()[0][1:] == ("failed", None)
    with pytest.raises(ValueError, match="source event"):
        PeriodicThoughtRunner(scheduler, lambda: "invented-event").tick(
            now=START + timedelta(minutes=30), source_refs=REFS)
    assert scheduler.history()[-1][1:] == ("failed", None)


def test_unclaimed_event_rejected_and_input_not_logged(state):
    scheduler = gate(state)
    with pytest.raises(ValueError, match="never claimed"):
        scheduler.finish("unknown", status="reflected", event_id="event-1")
    with pytest.raises(ValueError, match="recorded event identifiers"):
        scheduler.claim(now=START, source_refs=("private user text!",))
    first = scheduler.claim(now=START, source_refs=REFS)
    with pytest.raises(ValueError, match="lacks recorded source"):
        scheduler.finish(first.slot_id, status="reflected", event_id="invented")
    assert scheduler.history()[0][1:] == ("claimed", None)
