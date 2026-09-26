"""Sparks-only observed-contact logic, no model, notification or DM."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.rel import Contact, ReunionKind, SingleUserPresence

T0 = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def tracker():
    return SingleUserPresence("owner-123")


def event(message="m1", time=T0, principal="owner-123"):
    return Contact(principal, message, time)


def test_no_evidence_never_implies_absence():
    status = tracker().reunion(T0 + HOUR, HOUR)
    assert status.kind is ReunionKind.NO_EVIDENCE and status.elapsed is None


def test_normal_interval():
    t = tracker()
    assert t.record(event())
    status = t.reunion(T0 + timedelta(minutes=59), HOUR)
    assert status.kind is ReunionKind.NORMAL
    assert status.elapsed == timedelta(minutes=59)


def test_equal_threshold_is_elapsed_gap_not_feeling():
    t = tracker()
    t.record(event())
    status = t.reunion(T0 + HOUR, HOUR)
    assert status.kind is ReunionKind.ELAPSED_GAP
    assert status.last_message_id == "m1"


def test_long_gap_records_observed_duration_only():
    t = tracker()
    t.record(event())
    assert t.reunion(T0 + timedelta(days=8), HOUR).elapsed == timedelta(days=8)


def test_duplicate_is_idempotent():
    t = tracker()
    assert t.record(event())
    assert not t.record(event())
    assert t.last_contact == event()


def test_older_out_of_order_event_never_rewinds_last_seen():
    t = tracker()
    t.record(event("new", T0 + HOUR))
    assert not t.record(event("old", T0))
    assert t.last_contact.message_id == "new"
    assert t.reunion(T0 + 2 * HOUR, HOUR).elapsed == HOUR


def test_newer_event_replaces_last_seen():
    t = tracker()
    t.record(event())
    assert t.record(event("new", T0 + HOUR))
    assert t.last_contact.message_id == "new"


def test_same_timestamp_does_not_displace_first_evidence():
    t = tracker()
    t.record(event("first"))
    assert not t.record(event("second"))
    assert t.last_contact.message_id == "first"


def test_different_person_is_rejected_and_not_recorded():
    t = tracker()
    with pytest.raises(PermissionError):
        t.record(event(principal="other"))
    assert t.last_contact is None


def test_clock_rollback_does_not_claim_absence():
    t = tracker()
    t.record(event())
    status = t.reunion(T0 - timedelta(seconds=1), HOUR)
    assert status.kind is ReunionKind.CLOCK_UNCERTAIN
    assert status.elapsed is None


def test_timezones_compare_same_instant():
    t = tracker()
    t.record(event(time=T0.astimezone(timezone(timedelta(hours=-5)))))
    assert t.reunion(T0 + HOUR, HOUR).elapsed == HOUR


@pytest.mark.parametrize("invalid", ["", "  ", None, 42])
def test_missing_principal_rejected(invalid):
    with pytest.raises(ValueError):
        SingleUserPresence(invalid)


@pytest.mark.parametrize("invalid", ["", "  ", None, 42])
def test_missing_contact_ids_rejected(invalid):
    with pytest.raises(ValueError):
        Contact("owner-123", invalid, T0)


@pytest.mark.parametrize("invalid", [datetime(2026, 9, 21), "2026-09-21", None])
def test_unverified_time_rejected(invalid):
    with pytest.raises(ValueError):
        event(time=invalid)


@pytest.mark.parametrize("gap", [timedelta(0), -HOUR, None, "one hour"])
def test_invalid_gap_rejected(gap):
    with pytest.raises(ValueError):
        tracker().reunion(T0, gap)


def test_invalid_event_type_rejected():
    with pytest.raises(TypeError):
        tracker().record("someone said hello")


def test_does_not_generate_message_or_mutate_user_contact():
    t = tracker()
    original = event()
    t.record(original)
    t.reunion(T0 + 2 * HOUR, HOUR)
    assert t.last_contact is original
