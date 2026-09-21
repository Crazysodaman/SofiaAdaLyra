import pytest

from sofia.package_foundations.verify import Environment, Outcome, VerificationRecord


SHA = 'a' * 40


def test_not_run_cannot_be_conflated_with_pass():
    record = VerificationRecord(SHA, Environment.WINDOWS, Outcome.NOT_RUN)
    assert not record.needs_external_validation
    assert record.outcome is Outcome.NOT_RUN


def test_reported_fixture_pass_still_needs_validation():
    record = VerificationRecord(SHA, Environment.FIXTURE, Outcome.PASSED, 'local-log')
    assert record.needs_external_validation
    assert record.environment is Environment.FIXTURE


def test_abbreviated_sha_is_rejected():
    with pytest.raises(ValueError):
        VerificationRecord('abc123', Environment.WINDOWS, Outcome.PASSED)
