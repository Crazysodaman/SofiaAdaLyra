from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.application.background import (
    ApplicationBackgroundCoordinator,
    BackgroundBudget,
)


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def test_empty_task_readiness_does_not_consume_background_budget(tmp_path):
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
