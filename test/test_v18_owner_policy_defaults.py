"""Owner-selected V18 default limits, no live settings or hosts touched."""
from datetime import timedelta

from sofia.config.user_settings import OutreachSettings
from sofia.application.optional_budget import OptionalBudgetLimits


def test_owner_selected_outreach_defaults_remain_bounded_and_quiet():
    settings = OutreachSettings()
    policy = settings.policy("person:sparks")
    assert settings.timezone_name == "America/Chicago"
    assert (policy.quiet_start_local, policy.quiet_end_local) == (22, 8)
    assert (policy.max_daily, policy.social_max_daily) == (15, 15)
    assert (policy.min_interval, policy.social_min_interval) == (
        timedelta(minutes=30), timedelta(minutes=30)
    )
    # Operational/critical alerts retain their separately classified policy.
    assert policy.operational_max_daily == 8
    assert policy.operational_min_interval == timedelta(minutes=30)


def test_explicit_existing_outreach_values_are_not_replaced_by_defaults():
    previous = OutreachSettings(
        min_interval_minutes=360, max_daily=1,
        social_min_interval_minutes=360, social_max_daily=1,
    )
    policy = previous.policy("person:sparks")
    assert policy.max_daily == policy.social_max_daily == 1
    assert policy.min_interval == policy.social_min_interval == timedelta(hours=6)


def test_owner_selected_daily_optional_inference_budget_is_estimated_only():
    limits = OptionalBudgetLimits()
    assert limits.tokens == 200_000
    assert limits.gpu_ms == 3_600_000
    # Other historically independent bounds were not authorized to change.
    assert limits.cpu_ms == 10_800_000
    assert limits.storage_bytes == 536_870_912
    assert limits.occupied_latency_ms == 7_200_000
