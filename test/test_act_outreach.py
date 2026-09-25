from datetime import datetime, timedelta, timezone
import pytest

from sofia.act import Candidate, Decision, History, Policy, evaluate

T0 = datetime(2026, 9, 25, 14, tzinfo=timezone.utc)


def candidate(**changes):
    values = dict(
        candidate_id="idea-1",
        recipient_id="sparks",
        evidence_ids=("journal-9",),
        created_at=T0 - timedelta(hours=1),
        expires_at=T0 + timedelta(hours=2),
    )
    values.update(changes)
    return Candidate(**values)


def policy(**changes):
    values = dict(recipient_id="sparks", enabled=True)
    values.update(changes)
    return Policy(**values)


def decision(c=None, p=None, h=None, now=T0, **kwargs):
    return evaluate(c or candidate(), p or policy(), h or History(), now, **kwargs)


def test_disabled_default():
    assert decision(p=Policy("sparks")) is Decision.DISABLED


def test_candidate_only_eligible_for_authorization_not_sent():
    assert decision() is Decision.ELIGIBLE_FOR_AUTHORIZATION


@pytest.mark.parametrize(
    "change,expected",
    [
        (dict(stop=True), Decision.STOPPED),
        (dict(mute=True), Decision.MUTED),
        (dict(enabled=False), Decision.DISABLED),
        (dict(recipient_id="other"), Decision.WRONG_RECIPIENT),
    ],
)
def test_policy_denials(change, expected):
    assert decision(p=policy(**change)) is expected


def test_busy_denial():
    assert decision(busy=True) is Decision.BUSY


def test_duplicate_acknowledged_delivery():
    assert decision(h=History(frozenset({"idea-1"}))) is Decision.ALREADY_DELIVERED


def test_expired_and_future_candidate_fail_closed():
    assert decision(now=T0 + timedelta(hours=2)) is Decision.STALE
    assert decision(now=T0 - timedelta(hours=2)) is Decision.CLOCK_UNCERTAIN


@pytest.mark.parametrize("hour", [22, 23, 0, 7])
def test_overnight_quiet(hour):
    c = candidate(
        created_at=T0 - timedelta(days=1),
        expires_at=T0 + timedelta(days=1),
    )
    assert decision(c=c, now=T0.replace(hour=hour)) is Decision.QUIET_HOURS


@pytest.mark.parametrize("hour", [8, 14, 21])
def test_outside_quiet(hour):
    c = candidate(
        created_at=T0 - timedelta(days=1),
        expires_at=T0 + timedelta(days=1),
    )
    assert decision(c=c, now=T0.replace(hour=hour)) is Decision.ELIGIBLE_FOR_AUTHORIZATION


def test_equal_quiet_hours_is_full_day_quiet():
    assert decision(p=policy(quiet_start_utc=8, quiet_end_utc=8)) is Decision.QUIET_HOURS


def test_cooldown_and_daily_limit_use_acknowledged_delivery_only():
    assert decision(h=History(last_delivered_at=T0 - timedelta(hours=1))) is Decision.TOO_SOON
    assert decision(h=History(last_delivered_at=T0 - timedelta(hours=6))) is Decision.ELIGIBLE_FOR_AUTHORIZATION
    assert decision(
        h=History(delivered_day_utc="2026-09-25", delivered_today=1)
    ) is Decision.DAILY_LIMIT


@pytest.mark.parametrize(
    "bad",
    [
        dict(evidence_ids=()),
        dict(evidence_ids=("bad evidence text",)),
        dict(evidence_ids=("a", "a")),
        dict(recipient_id=""),
        dict(candidate_id=""),
        dict(expires_at=T0 - timedelta(hours=2)),
        dict(created_at=datetime(2026, 9, 25)),
    ],
)
def test_invalid_candidate_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        candidate(**bad)


@pytest.mark.parametrize(
    "bad",
    [
        dict(max_daily=0),
        dict(max_daily=True),
        dict(min_interval=-timedelta(seconds=1)),
        dict(quiet_start_utc=24),
        dict(quiet_end_utc=-1),
        dict(stop="no"),
        dict(recipient_id=""),
    ],
)
def test_invalid_policy_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        policy(**bad)


def test_naive_now_and_non_boolean_busy_rejected():
    with pytest.raises(ValueError):
        decision(now=datetime(2026, 9, 25))
    with pytest.raises(TypeError):
        decision(busy="false")
