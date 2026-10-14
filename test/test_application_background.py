from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

from sofia.application.background import (
    ApplicationBackgroundCoordinator,
    BackgroundBudget,
)


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def test_empty_task_readiness_does_not_consume_background_budget(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    from types import SimpleNamespace
    coordinator = ApplicationBackgroundCoordinator.__new__(ApplicationBackgroundCoordinator)
    coordinator.service = SimpleNamespace(ready_for_idle_reflection=lambda **kwargs: True)
    coordinator.idle_seconds = 1
    coordinator.reflection_enabled = False
    coordinator._tasks = {"wardrobe_review": lambda now: pytest.fail("Empty queue cannot run")}
    coordinator._task_ready = {"wardrobe_review": lambda: False}
    coordinator._task_last_run = {}
    coordinator._task_intervals = {"wardrobe_review": 30}
    coordinator._task_cursor = 0
    coordinator._act_delivery = None
    coordinator.budget = BackgroundBudget(tmp_path / "sofia.db")
    assert coordinator.run_once(now=NOW) == "background_idle"
    with sqlite3.connect(coordinator.budget.path) as db:
        assert db.execute("SELECT COUNT(*) FROM application_background_claims").fetchone()[0] == 0


def test_abandoned_background_claim_recovers_after_lease_timeout(tmp_path):
    state = tmp_path / "state.db"
    state.touch()
    first = BackgroundBudget(
        state,
        claim_timeout=timedelta(minutes=30),
    )
    first_claim = first.claim("fleet_discovery", now=NOW)
    assert first_claim is not None

    restarted = BackgroundBudget(
        state,
        claim_timeout=timedelta(minutes=30),
    )
    assert restarted.claim(
        "act_delivery",
        now=NOW + timedelta(minutes=29),
    ) is None

    second_claim = restarted.claim(
        "act_delivery",
        now=NOW + timedelta(minutes=31),
    )
    assert second_claim is not None
    assert second_claim != first_claim

    with sqlite3.connect(state) as db:
        rows = db.execute(
            """
            SELECT claim_id,status,error_type
            FROM application_background_claims
            ORDER BY claimed_at,claim_id
            """
        ).fetchall()

    assert rows[0] == (
        first_claim,
        "failed",
        "AbandonedClaim",
    )
    assert rows[1] == (
        second_claim,
        "working",
        None,
    )


def test_background_budget_rejects_invalid_claim_timeout(tmp_path):
    state = tmp_path / "state.db"
    state.touch()

    with pytest.raises(ValueError, match="claim_timeout"):
        BackgroundBudget(
            state,
            claim_timeout=timedelta(0),
        )



def test_background_recovery_does_not_ignore_newer_active_claim(tmp_path):
    state = tmp_path / "state.db"
    state.touch()
    budget = BackgroundBudget(
        state,
        claim_timeout=timedelta(minutes=30),
    )

    with sqlite3.connect(state) as db:
        db.execute(
            """
            INSERT INTO application_background_claims (
                claim_id, task_kind, claimed_at, day_utc,
                status, finished_at, error_type
            )
            VALUES (?, ?, ?, ?, 'working', NULL, NULL)
            """,
            (
                "stale",
                "old-task",
                (NOW - timedelta(hours=1)).isoformat(),
                NOW.date().isoformat(),
            ),
        )
        db.execute(
            """
            INSERT INTO application_background_claims (
                claim_id, task_kind, claimed_at, day_utc,
                status, finished_at, error_type
            )
            VALUES (?, ?, ?, ?, 'working', NULL, NULL)
            """,
            (
                "active",
                "current-task",
                (NOW - timedelta(minutes=5)).isoformat(),
                NOW.date().isoformat(),
            ),
        )

    assert budget.claim("new-task", now=NOW) is None

    with sqlite3.connect(state) as db:
        rows = dict(
            db.execute(
                """
                SELECT claim_id,status
                FROM application_background_claims
                """
            ).fetchall()
        )

    assert rows == {
        "stale": "working",
        "active": "working",
    }



def test_heartbeat_failure_is_diagnostic_not_scheduler_failure():
    coordinator = object.__new__(ApplicationBackgroundCoordinator)
    coordinator.last_heartbeat_error = None

    def fail_heartbeat(now, healthy):
        raise OSError("heartbeat unavailable")

    coordinator._heartbeat = fail_heartbeat

    coordinator._publish_heartbeat(
        now=NOW,
        healthy=True,
    )

    assert coordinator.last_heartbeat_error == "OSError"

    coordinator._heartbeat = None
    coordinator._publish_heartbeat(
        now=NOW,
        healthy=False,
    )
    assert coordinator.last_heartbeat_error is None


def test_operator_pause_prevents_all_optional_background_dispatch(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    """Central scheduler must not wake reflection, LIFE, ACT or Fleet on PAUSE."""
    from types import SimpleNamespace

    from sofia.safe.operator_stop import OperatorStopStore

    state = tmp_path / "sofia.db"
    coordinator = ApplicationBackgroundCoordinator.__new__(
        ApplicationBackgroundCoordinator
    )
    coordinator.budget = BackgroundBudget(state)
    coordinator.idle_seconds = 1
    coordinator.service = SimpleNamespace(
        ready_for_idle_reflection=lambda **kwargs: pytest.fail(
            "PAUSE must precede even idle reflection readiness"
        ),
    )
    coordinator._tasks = {
        "independent_life": lambda now: pytest.fail("LIFE ran while paused"),
        "fleet_discovery": lambda now: pytest.fail("Fleet ran while paused"),
    }
    coordinator._act_delivery = lambda now: pytest.fail("ACT ran while paused")

    OperatorStopStore(state).set(
        active=True,
        updated_by="Sparks",
        reason="emergency operator pause",
        at=NOW,
    )

    assert coordinator.run_once(now=NOW + timedelta(minutes=1)) == "operator_stopped"
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM application_background_claims"
        ).fetchone()[0] == 0


def _coordinator_with_stop_race(tmp_path):
    """Real canonical SQLite budget, synthetic readiness and effect callbacks."""
    from types import SimpleNamespace

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    coordinator = ApplicationBackgroundCoordinator.__new__(
        ApplicationBackgroundCoordinator
    )
    coordinator.budget = BackgroundBudget(state)
    coordinator.idle_seconds = 1
    coordinator.service = SimpleNamespace(
        ready_for_idle_reflection=lambda **kwargs: True,
    )
    coordinator.reflection_enabled = False
    coordinator._tasks = {}
    coordinator._task_ready = {}
    coordinator._task_last_run = {}
    coordinator._task_intervals = {}
    coordinator._task_cursor = 0
    coordinator._act_delivery = None
    coordinator._act_ready = None
    coordinator._act_last_run = None
    coordinator._act_interval_seconds = 30
    return coordinator, state


def _assert_no_live_claims(state):
    with sqlite3.connect(state) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM application_background_claims "
            "WHERE status='working'"
        ).fetchone()[0]
    assert count == 0


def test_operator_pause_between_act_readiness_and_dispatch_fails_closed(tmp_path):
    """CA-1907: the start-of-tick STOP check must not be a stale token."""
    from sofia.safe.operator_stop import OperatorStopStore

    coordinator, state = _coordinator_with_stop_race(tmp_path)
    stop = OperatorStopStore(state)

    def ready_then_pause():
        stop.set(
            active=True, updated_by="Sparks",
            reason="owner stopped ACT during readiness", at=NOW,
        )
        return True

    coordinator._act_ready = ready_then_pause
    coordinator._act_delivery = lambda now: pytest.fail(
        "ACT delivery must not dispatch after a newly observed STOP"
    )

    assert coordinator.run_once(now=NOW + timedelta(seconds=1)) == "operator_stopped"
    assert stop.current().active
    _assert_no_live_claims(state)


def test_operator_pause_between_life_readiness_and_dispatch_fails_closed(tmp_path):
    """Optional LIFE/Fleet tasks recheck STOP after budget admission."""
    from sofia.safe.operator_stop import OperatorStopStore

    coordinator, state = _coordinator_with_stop_race(tmp_path)
    stop = OperatorStopStore(state)

    def ready_then_pause():
        stop.set(
            active=True, updated_by="Sparks",
            reason="owner stopped LIFE while scheduler checked readiness", at=NOW,
        )
        return True

    coordinator._tasks = {
        "independent_life": lambda now: pytest.fail(
            "LIFE must not dispatch after a newly observed STOP"
        ),
    }
    coordinator._task_ready = {"independent_life": ready_then_pause}
    coordinator._task_intervals = {"independent_life": 0}

    assert coordinator.run_once(now=NOW + timedelta(seconds=1)) == "operator_stopped"
    assert stop.current().active
    _assert_no_live_claims(state)


def test_operator_pause_after_reflection_opportunity_claim_fails_closed(tmp_path):
    """The pending reflection claim is settled without invoking the LLM."""
    from types import SimpleNamespace
    from sofia.safe.operator_stop import OperatorStopStore

    coordinator, state = _coordinator_with_stop_race(tmp_path)
    stop = OperatorStopStore(state)
    statuses = []

    class PausingPeriodic:
        def claim(self, **kwargs):
            stop.set(
                active=True, updated_by="Sparks",
                reason="owner stopped reflection during opportunity claim",
                at=NOW,
            )
            return SimpleNamespace(status="claimed", slot_id="pending-reflection")

        def finish(self, slot_id, *, status, **kwargs):
            statuses.append((slot_id, status))

    coordinator.reflection_enabled = True
    coordinator._reflection_wake_gate = None
    coordinator._source_refs = lambda now: ("observed-event",)
    coordinator.periodic = PausingPeriodic()
    coordinator.idle = SimpleNamespace(
        run_once=lambda **kwargs: pytest.fail("LLM reflection must not run")
    )

    assert coordinator.run_once(now=NOW + timedelta(seconds=1)) == "operator_stopped"
    assert statuses == [("pending-reflection", "no_event")]
    assert stop.current().active
    _assert_no_live_claims(state)
