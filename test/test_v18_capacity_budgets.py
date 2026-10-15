from __future__ import annotations

import pytest

from sofia.ops.capacity import (
    DEFAULT_BUDGETS,
    CapacityBudget,
    CapacityError,
    Level,
    Reading,
    assess_capacity,
)


def test_levels_are_inclusive_lower_bounds_on_used():
    budget = CapacityBudget("disk_bytes", warn_at=10, degrade_at=20, stop_at=30)
    assert budget.level_for(9) is Level.NORMAL
    assert budget.level_for(10) is Level.WARN
    assert budget.level_for(19) is Level.WARN
    assert budget.level_for(20) is Level.DEGRADED
    assert budget.level_for(29) is Level.DEGRADED
    assert budget.level_for(30) is Level.STOP
    assert budget.level_for(1000) is Level.STOP


def test_overall_level_is_the_worst_observed_resource():
    assessment = assess_capacity(
        [CapacityBudget("a", 10, 20, 30), CapacityBudget("b", 10, 20, 30)],
        [Reading("a", 5), Reading("b", 21)],
    )
    assert assessment.overall is Level.DEGRADED
    assert assessment.verdict_for("a").level is Level.NORMAL
    assert assessment.verdict_for("b").level is Level.DEGRADED
    assert any("b=21" in alert for alert in assessment.alerts)


def test_stop_level_is_reported_so_runtime_can_shed_load_before_writes():
    assessment = assess_capacity(
        [CapacityBudget("archive_bytes", 10, 20, 30)],
        [Reading("archive_bytes", 30)],
    )
    assert assessment.overall is Level.STOP
    assert any("stop" in alert for alert in assessment.alerts)


def test_unbudgeted_resource_fails_closed_to_warn_not_silently_ignored():
    assessment = assess_capacity(
        [CapacityBudget("known", 10, 20, 30)],
        [Reading("known", 1), Reading("surprising", 1)],
    )
    verdict = assessment.verdict_for("surprising")
    assert verdict is not None
    assert verdict.budgeted is False
    assert verdict.level is Level.WARN
    assert verdict.trigger is not None


def test_budget_thresholds_must_be_ordered_and_positive():
    with pytest.raises(CapacityError):
        CapacityBudget("x", warn_at=20, degrade_at=10, stop_at=30)
    with pytest.raises(CapacityError):
        CapacityBudget("x", warn_at=0, degrade_at=10, stop_at=30)
    with pytest.raises(CapacityError):
        CapacityBudget("Bad Name", 1, 2, 3)


def test_readings_must_be_well_formed_and_unique():
    with pytest.raises(CapacityError):
        Reading("bad name", 1)
    with pytest.raises(CapacityError):
        Reading("x", -1)
    with pytest.raises(CapacityError):
        assess_capacity(
            [CapacityBudget("x", 10, 20, 30)],
            [Reading("x", 1), Reading("x", 2)],
        )
    with pytest.raises(CapacityError):
        assess_capacity([CapacityBudget("x", 10, 20, 30)], [])


def test_declared_default_budgets_are_well_formed_and_usable():
    assert DEFAULT_BUDGETS
    readings = [Reading(b.resource, 0) for b in DEFAULT_BUDGETS]
    assessment = assess_capacity(DEFAULT_BUDGETS, readings)
    assert assessment.overall is Level.NORMAL
    assert len(assessment.verdicts) == len(DEFAULT_BUDGETS)
