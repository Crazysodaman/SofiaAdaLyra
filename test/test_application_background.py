from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.application.background import BackgroundBudget


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


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
