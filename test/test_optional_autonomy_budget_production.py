"""Deferred one-RUN application optional resource budget contracts. No tests run."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sqlite3
import pytest
from sofia.application.background import BackgroundBudget
from sofia.application.optional_budget import (
    OptionalAutonomyBudget,OptionalBudgetLimits,reserve_profile,
)
from sofia.safe.permissions import PermissionLevel,capability_permission_policy
pytestmark=pytest.mark.pkg_run
T=datetime(2026,10,11,12,tzinfo=timezone.utc)

def test_global_background_claim_spends_atomic_reservations_without_double_counting(tmp_path):
    path=tmp_path/"sofia.db"
    budget=BackgroundBudget(path)
    actual=OptionalAutonomyBudget(path)
    settings,revision=actual.limits()
    assert settings.tokens>0
    claim=budget.claim("reflection",now=T)
    assert claim is not None
    resource=reserve_profile("reflection")
    report=actual.report(now=T)
    assert report["reserved"]["tokens"]==resource.tokens
    assert report["reserved"]["gpu_ms"]==resource.gpu_ms
    assert report["unfinished"]==1
    assert report["can_preempt_foreground"] is False
    assert "NOT measured" in report["note"]
    assert budget.claim("neuro_refresh",now=T+timedelta(seconds=1)) is None
    budget.finish(claim,now=T+timedelta(seconds=2))
    assert actual.report(now=T)["unfinished"]==0
    with pytest.raises(RuntimeError):
        budget.finish(claim,now=T+timedelta(seconds=3))


def test_owner_budget_limit_denies_optional_model_wakeup_but_not_foreground(tmp_path):
    path=tmp_path/"sofia.db"
    optional=OptionalAutonomyBudget(path)
    _,rev=optional.limits()
    optional.update_owner_limits(
        OptionalBudgetLimits(tokens=0,cpu_ms=300_000,gpu_ms=0,
                             storage_bytes=1_000_000,occupied_latency_ms=100_000),
        expected_revision=rev,
    )
    background=BackgroundBudget(path)
    assert background.claim("reflection",now=T) is None
    # Deterministic NEURO still obeys one-flight and current CPU/storage credits.
    claim=background.claim("neuro_refresh",now=T)
    assert claim is not None
    budget=optional.report(now=T)
    assert budget["reserved"]["tokens"]==0
    assert budget["attempts"]==1
    background.finish(claim,now=T+timedelta(seconds=1))


def test_quota_accumulates_across_two_coordinators_and_is_day_scoped(tmp_path):
    path=tmp_path/"sofia.db"
    optional=OptionalAutonomyBudget(path)
    _,rev=optional.limits()
    quoted=reserve_profile("reflection")
    optional.update_owner_limits(
        OptionalBudgetLimits(
            tokens=quoted.tokens,
            cpu_ms=quoted.cpu_ms,
            gpu_ms=quoted.gpu_ms,
            storage_bytes=quoted.storage_bytes,
            occupied_latency_ms=quoted.occupied_latency_ms,
        ),expected_revision=rev,
    )
    first=BackgroundBudget(path)
    second=BackgroundBudget(path)
    c1=first.claim("reflection",now=T)
    assert c1
    first.finish(c1,now=T+timedelta(minutes=1))
    assert second.claim("reflection",now=T+timedelta(minutes=2)) is None
    next_day=second.claim("reflection",now=T+timedelta(days=1))
    assert next_day
    second.finish(next_day,now=T+timedelta(days=1,seconds=2))
    today=optional.report(now=T)
    tomorrow=optional.report(now=T+timedelta(days=1))
    assert today["attempts"]==1
    assert tomorrow["attempts"]==1


def test_stale_claim_recovery_fails_claim_reservation_not_recharge_same_work(tmp_path):
    path=tmp_path/"sofia.db"
    budget=BackgroundBudget(path,claim_timeout=timedelta(minutes=3))
    claim=budget.claim("reflection",now=T)
    assert claim is not None
    # Detect abandoned RUN single-flight in same SQLite commit.
    second=budget.claim("neuro_refresh",now=T+timedelta(minutes=4))
    assert second is not None
    with sqlite3.connect(path) as db:
        row=db.execute(
            "SELECT status FROM application_optional_budget_claim WHERE claim_id=?",
            (claim,),
        ).fetchone()
    assert row==("failed",)
    budget.finish(second,now=T+timedelta(minutes=5))
    report=budget.optional_resources.report(now=T)
    assert report["reserved"]["tokens"]==reserve_profile("reflection").tokens
    assert report["attempts"]==2


def test_owner_cannot_update_resource_caps_from_stale_settings_revision(tmp_path):
    store=OptionalAutonomyBudget(tmp_path/"sofia.db")
    _,revision=store.limits()
    store.update_owner_limits(OptionalBudgetLimits(tokens=12_000),expected_revision=revision)
    with pytest.raises(PermissionError,match="changed"):
        store.update_owner_limits(OptionalBudgetLimits(tokens=0),expected_revision=revision)
    assert store.limits()[0].tokens==12_000
    with pytest.raises(ValueError,match="limit"):
        OptionalBudgetLimits(tokens=-1)
    with pytest.raises(ValueError,match="resource limit"):
        OptionalBudgetLimits(gpu_ms=True)


def test_unclassified_optional_tasks_are_never_cost_free():
    profile=reserve_profile("new_unreviewed_optional_worker")
    assert profile.tokens>0
    assert profile.gpu_ms>0
    assert profile.cpu_ms>0
    assert reserve_profile("presence_refresh").tokens==0
    assert reserve_profile("neuro_refresh").gpu_ms==0
    assert capability_permission_policy("ops.autonomy.budget").level is PermissionLevel.OBSERVE_READ
