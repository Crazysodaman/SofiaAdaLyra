"""Offline evidence-based absence tests; no messages are sent."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.relationships.absence import LastContact, appraise_absence

NOW = datetime(2026, 9, 21, 18, tzinfo=timezone.utc)


def contact(*, actor="sparks", when=None, source="message-1"):
    return LastContact(actor, when or NOW - timedelta(days=2), source)


def appraisal(c=None, **kwargs):
    options = dict(authenticated_actor_id="sparks", now=NOW, contact=c)
    options.update(kwargs)
    return appraise_absence(**options)


def test_absence_is_unknown_without_contact():
    a = appraisal()
    assert not a.known and a.elapsed is None and not a.optional_reunion_cue


def test_observed_gap_can_support_reunion_cue():
    a = appraisal(contact())
    assert a.known and a.elapsed == timedelta(days=2)
    assert a.last_event_id == "message-1" and a.optional_reunion_cue


def test_never_assume_other_persons_contact():
    a = appraisal(contact(actor="someone-else"))
    assert not a.known and a.last_event_id is None and not a.outreach_permitted


def test_recent_contact_does_not_trigger_reunion():
    a = appraisal(contact(when=NOW - timedelta(hours=1)))
    assert a.known and not a.optional_reunion_cue


def test_future_contact_is_unknown():
    a = appraisal(contact(when=NOW + timedelta(seconds=1)))
    assert not a.known and a.elapsed is None


def test_outreach_disabled_by_default():
    assert not appraisal(contact()).outreach_permitted


def test_opt_in_still_respects_quiet_or_busy():
    assert not appraisal(contact(), outreach_opt_in=True).outreach_permitted
    assert not appraisal(contact(), outreach_opt_in=True, busy_or_quiet=True).outreach_permitted


def test_outreach_is_only_candidate_when_opted_in_and_not_quiet():
    assert appraisal(contact(), outreach_opt_in=True, busy_or_quiet=False).outreach_permitted


def test_no_outreach_for_short_gap_even_if_opted_in():
    a = appraisal(contact(when=NOW - timedelta(minutes=10)), outreach_opt_in=True, busy_or_quiet=False)
    assert not a.outreach_permitted


def test_configurable_threshold():
    a = appraisal(contact(when=NOW - timedelta(hours=2)), reunion_after=timedelta(hours=1))
    assert a.optional_reunion_cue


@pytest.mark.parametrize("bad", ["", " ", None, 1])
def test_invalid_actor(bad):
    with pytest.raises(ValueError):
        appraisal(contact(), authenticated_actor_id=bad)


@pytest.mark.parametrize("bad", [None, "now", datetime(2026, 9, 21)])
def test_invalid_now(bad):
    with pytest.raises(ValueError):
        appraisal(contact(), now=bad)


@pytest.mark.parametrize("bad", [timedelta(0), timedelta(seconds=-1), 5, None])
def test_invalid_threshold(bad):
    with pytest.raises(ValueError):
        appraisal(contact(), reunion_after=bad)


@pytest.mark.parametrize("name,value", [("outreach_opt_in", 1), ("busy_or_quiet", None)])
def test_invalid_flags(name, value):
    with pytest.raises(TypeError):
        appraisal(contact(), **{name: value})


def test_missing_evidence_cannot_allow_outreach():
    assert not appraisal(outreach_opt_in=True, busy_or_quiet=False).outreach_permitted


def test_contact_requires_real_source_and_zoned_time():
    with pytest.raises(ValueError):
        contact(source=" ")
    with pytest.raises(ValueError):
        contact(when=datetime(2026, 9, 20))


def test_non_contact_value_fails_closed():
    assert not appraisal("self-reported offline feelings").known
