"""Offline verification contract. This test run does not establish live readiness."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.verify import Evidence, Requirement, Result, Tier, assess_gate

SHA = "a" * 40
T0 = datetime(2026, 9, 21, tzinfo=timezone.utc)


def evidence(**changes):
    base = dict(evidence_id="e1", package="PKG-UI", check="render", source_sha=SHA,
                tier=Tier.OFFLINE, result=Result.PASSED, observed_at=T0,
                environment="local pytest", source_reference="test run log")
    base.update(changes)
    return Evidence(**base)


def gate(requirement, *records, sha=SHA, package="PKG-UI"):
    return assess_gate(package, sha, (requirement,), tuple(records))


def test_exact_revision_offline_pass():
    assert gate(Requirement("render", Tier.OFFLINE), evidence()).ready


def test_other_package_does_not_satisfy_gate():
    assert gate(Requirement("render", Tier.OFFLINE), evidence(package="PKG-AVATAR")).missing == ("render",)


def test_other_commit_does_not_satisfy_gate():
    assert gate(Requirement("render", Tier.OFFLINE), evidence(), sha="b" * 40).missing == ("render",)


def test_fixture_cannot_pass_real_live_gate():
    requirement = Requirement("render", Tier.LIVE, actual_system=True)
    assert gate(requirement, evidence(tier=Tier.LIVE, actual_system=False)).missing == ("render",)


def test_offline_cannot_pass_live_gate():
    assert gate(Requirement("render", Tier.LIVE), evidence()).missing == ("render",)


def test_explicit_actual_live_pass():
    assert gate(Requirement("render", Tier.LIVE, actual_system=True),
                evidence(tier=Tier.LIVE, actual_system=True)).ready


@pytest.mark.parametrize("result", [Result.NOT_RUN, Result.NOT_APPLICABLE, Result.FAILED])
def test_nonpass_never_satisfies_gate(result):
    report = gate(Requirement("render", Tier.OFFLINE), evidence(result=result))
    assert not report.ready
    assert report.blocked == ("render",)


def test_later_failure_blocks_earlier_pass():
    report = gate(Requirement("render", Tier.OFFLINE), evidence(),
                  evidence(evidence_id="e2", result=Result.FAILED, observed_at=T0 + timedelta(seconds=1)))
    assert report.blocked == ("render",)


def test_later_pass_clears_earlier_failure():
    report = gate(Requirement("render", Tier.OFFLINE), evidence(result=Result.FAILED),
                  evidence(evidence_id="e2", observed_at=T0 + timedelta(seconds=1)))
    assert report.ready


def test_tied_pass_and_failure_block():
    assert gate(Requirement("render", Tier.OFFLINE), evidence(),
                evidence(evidence_id="e2", result=Result.FAILED)).blocked == ("render",)


def test_multiple_requirements_distinct_missing_and_blocked():
    report = assess_gate("PKG-UI", SHA,
                         (Requirement("render", Tier.OFFLINE), Requirement("click", Tier.LIVE),
                          Requirement("safety", Tier.OFFLINE)),
                         (evidence(result=Result.FAILED),))
    assert report.missing == ("click", "safety")
    assert report.blocked == ("render",)


@pytest.mark.parametrize("changed", [dict(source_sha="bad"), dict(source_sha="A" * 40),
                                    dict(package=""), dict(check=" "), dict(environment=""),
                                    dict(evidence_id=""), dict(observed_at=datetime(2026, 9, 21)),
                                    dict(source_reference=""), dict(actual_system=True),
                                    dict(result=Result.NOT_RUN, tier=Tier.LIVE, actual_system=True),
                                    dict(tier="offline"), dict(result="passed")])
def test_reject_ambiguous_or_untrusted_claims(changed):
    with pytest.raises((ValueError, TypeError)):
        evidence(**changed)


def test_utc_timestamp_normalization():
    east = timezone(timedelta(hours=2))
    later = evidence(evidence_id="later", result=Result.FAILED,
                     observed_at=(T0 + timedelta(minutes=1)).astimezone(east))
    assert gate(Requirement("render", Tier.OFFLINE), evidence(), later).blocked == ("render",)


def test_no_requirements_is_not_a_release_gate():
    assert assess_gate("PKG-UI", SHA, (), ()).ready is False
