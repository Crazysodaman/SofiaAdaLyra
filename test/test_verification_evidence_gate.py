"""Gate classification only; does not validate the authenticity of test output."""
import pytest
from sofia.verification.evidence_gate import Check, GateReport, Outcome, Tier, evaluate_gate

SHA = "a" * 40


def check(**changes):
    fields = dict(name="unit", required_tier=Tier.OFFLINE, outcome=Outcome.PASS, observed_tier=Tier.OFFLINE, revision=SHA, evidence="pytest log")
    fields.update(changes)
    return Check(**fields)


def test_matching_pass():
    assert evaluate_gate((check(),), target_revision=SHA) == GateReport(True, (), (), ())


def test_live_not_satisfied_by_mock():
    r = evaluate_gate((check(required_tier=Tier.LIVE),), target_revision=SHA)
    assert not r.ready and r.incomplete == ("unit",)


def test_integration_not_satisfied_by_offline():
    assert not evaluate_gate((check(required_tier=Tier.INTEGRATION),), target_revision=SHA).ready


def test_higher_observed_tier_satisfies_lower():
    assert evaluate_gate((check(observed_tier=Tier.LIVE),), target_revision=SHA).ready

@pytest.mark.parametrize("changes", [dict(outcome=Outcome.NOT_RUN), dict(observed_tier=None), dict(revision="b" * 40), dict(revision=None), dict(evidence=""), dict(evidence=None)])
def test_missing_or_stale_evidence_is_incomplete(changes):
    r = evaluate_gate((check(**changes),), target_revision=SHA)
    assert not r.ready and r.failed == () and r.incomplete == ("unit",)


def test_fail_is_not_incomplete():
    r = evaluate_gate((check(outcome=Outcome.FAIL),), target_revision=SHA)
    assert r.failed == ("unit",) and r.incomplete == () and not r.ready


def test_not_applicable_needs_justification():
    r = evaluate_gate((check(outcome=Outcome.NOT_APPLICABLE),), target_revision=SHA)
    assert not r.ready
    r = evaluate_gate((check(outcome=Outcome.NOT_APPLICABLE, justification="No robot is enrolled"),), target_revision=SHA)
    assert r.ready


def test_multiple_failures_are_reported():
    r = evaluate_gate((check(), check(name="live", required_tier=Tier.LIVE)), target_revision=SHA)
    assert r.blocking == ("live",)


def test_no_checks_not_ready():
    assert not evaluate_gate((), target_revision=SHA).ready

@pytest.mark.parametrize("bad", ["", " ", None])
def test_target_sha_required(bad):
    with pytest.raises(ValueError):
        evaluate_gate((check(),), target_revision=bad)


def test_duplicate_check_name():
    with pytest.raises(ValueError):
        evaluate_gate((check(), check()), target_revision=SHA)


def test_bad_check_type():
    with pytest.raises(TypeError):
        evaluate_gate(("unit",), target_revision=SHA)


def test_invalid_check_fields():
    with pytest.raises(TypeError):
        check(required_tier="live")
    with pytest.raises(ValueError):
        check(name=" ")
