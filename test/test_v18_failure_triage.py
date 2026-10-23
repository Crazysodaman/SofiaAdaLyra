from __future__ import annotations

import pytest

from sofia.platform.ops.failure_triage import (
    FailureCategory,
    FailureKind,
    FailureSignature,
    Platform,
    triage_failure,
)


def test_deterministic_assertion_is_a_code_defect_and_must_not_be_rerun_away():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.ASSERTION,
        assertion_is_deterministic=True,
    ))
    assert diagnosis.category is FailureCategory.CODE_DEFECT
    assert diagnosis.may_retry_cleanly is False
    assert diagnosis.conceals_code_defect_if_retried is True


def test_flaky_assertion_without_determinism_is_unknown_not_a_code_defect():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.ASSERTION,
        assertion_is_deterministic=None,
    ))
    assert diagnosis.category is FailureCategory.UNKNOWN
    assert diagnosis.conceals_code_defect_if_retried is True


def test_zero_selected_tests_is_absent_package_tests_not_a_green_pass():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.NONE_SELECTED, tests_selected=0,
    ))
    assert diagnosis.category is FailureCategory.ABSENT_PACKAGE_TESTS
    assert diagnosis.may_retry_cleanly is False


def test_marker_or_collection_mismatch_is_test_configuration():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.COLLECTION, marker_filter_mismatch=True,
    ))
    assert diagnosis.category is FailureCategory.TEST_CONFIGURATION
    assert diagnosis.may_retry_cleanly is True


def test_windows_file_lock_is_environment_only_when_resource_is_busy():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.FILE_LOCK,
        platform=Platform.WINDOWS,
        resource_busy=True,
    ))
    assert diagnosis.category is FailureCategory.ENVIRONMENT_WINDOWS_LOCK
    assert diagnosis.may_retry_cleanly is True
    # A file-lock failure on Linux is not the Windows-lock environment case.
    other = triage_failure(FailureSignature(
        failure_kind=FailureKind.FILE_LOCK,
        platform=Platform.LINUX,
        resource_busy=True,
    ))
    assert other.category is FailureCategory.UNKNOWN


def test_import_that_passes_under_pinned_install_is_stale_editable_installation():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.IMPORT, passing_under_pinned_install=True,
    ))
    assert diagnosis.category is FailureCategory.STALE_EDITABLE_INSTALLATION
    assert diagnosis.may_retry_cleanly is True


def test_unobserved_deployment_claim_is_unverifiable_regardless_of_green_reruns():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.ASSERTION,
        assertion_is_deterministic=True,
        deployment_claim=True,
        deployment_independently_observed=False,
    ))
    assert diagnosis.category is FailureCategory.UNVERIFIABLE_DEPLOYMENT
    assert diagnosis.may_retry_cleanly is False


def test_deployment_claim_is_allowed_to_fall_through_when_independently_observed():
    diagnosis = triage_failure(FailureSignature(
        failure_kind=FailureKind.ASSERTION,
        assertion_is_deterministic=True,
        deployment_claim=True,
        deployment_independently_observed=True,
    ))
    assert diagnosis.category is FailureCategory.CODE_DEFECT


def test_signature_rejects_contradictory_or_malformed_observations():
    with pytest.raises(ValueError):
        FailureSignature(failure_kind=FailureKind.ASSERTION, tests_selected=-1)
    with pytest.raises(TypeError):
        FailureSignature(failure_kind="assertion")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        FailureSignature(
            failure_kind=FailureKind.ASSERTION,
            assertion_is_deterministic="yes",  # type: ignore[arg-type]
        )
