"""Failure-resolution decision tree for V18 CA-3710.

The original requirement asks for an explicit tree that separates a *code
defect*, a *test configuration* mistake, a *stale editable installation*, an
*environment-only Windows file lock*, the *absence of package tests*, and an
*unverifiable deployment behaviour* -- and that refuses to let a green rerun
conceal a real bug.

This module is a deterministic, side-effect-free classifier over an explicit
failure signature. It never runs commands, never edits the repository and never
downgrades a deterministic code defect to a flaky retry.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class FailureKind(str, Enum):
    ASSERTION = "assertion"
    IMPORT = "import"
    COLLECTION = "collection"
    FILE_LOCK = "file_lock"
    TIMEOUT = "timeout"
    NONE_SELECTED = "none_selected"


class Platform(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    OTHER = "other"


class FailureCategory(str, Enum):
    CODE_DEFECT = "code_defect"
    TEST_CONFIGURATION = "test_configuration"
    STALE_EDITABLE_INSTALLATION = "stale_editable_installation"
    ENVIRONMENT_WINDOWS_LOCK = "environment_windows_lock"
    ABSENT_PACKAGE_TESTS = "absent_package_tests"
    UNVERIFIABLE_DEPLOYMENT = "unverifiable_deployment"
    UNKNOWN = "unknown"


class TriageError(ValueError):
    """Raised when a failure signature is malformed or contradictory."""


@dataclass(frozen=True, slots=True)
class FailureSignature:
    """Explicit, reproducible observations about one failure.

    ``passes_under_pinned_install`` is ``True`` only when the same failing
    selection passes after an isolated pinned installation; ``None`` means it
    was not tested. ``assertion_is_deterministic`` is ``True`` only when the
    exact same assertion fails again on an independent rerun.
    """

    failure_kind: FailureKind
    platform: Platform = Platform.OTHER
    tests_selected: int = 1
    passing_under_pinned_install: bool | None = None
    assertion_is_deterministic: bool | None = None
    resource_busy: bool = False
    deployment_claim: bool = False
    deployment_independently_observed: bool = False
    marker_filter_mismatch: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.failure_kind, FailureKind):
            raise TypeError("failure_kind must be FailureKind")
        if not isinstance(self.platform, Platform):
            raise TypeError("platform must be Platform")
        if type(self.tests_selected) is not int or self.tests_selected < 0:
            raise TriageError("tests_selected must be a non-negative integer")
        for name, value in (
            ("passing_under_pinned_install", self.passing_under_pinned_install),
            ("assertion_is_deterministic", self.assertion_is_deterministic),
        ):
            if value is not None and type(value) is not bool:
                raise TriageError(f"{name} must be bool or None")
        for name, value in (
            ("resource_busy", self.resource_busy),
            ("deployment_claim", self.deployment_claim),
            ("deployment_independently_observed",
             self.deployment_independently_observed),
            ("marker_filter_mismatch", self.marker_filter_mismatch),
        ):
            if type(value) is not bool:
                raise TriageError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class FailureDiagnosis:
    category: FailureCategory
    remediation: str
    may_retry_cleanly: bool
    conceals_code_defect_if_retried: bool

    def __post_init__(self) -> None:
        if not isinstance(self.category, FailureCategory):
            raise TypeError("category must be FailureCategory")
        if not isinstance(self.remediation, str) or not self.remediation.strip():
            raise TriageError("diagnosis requires a remediation")
        if type(self.may_retry_cleanly) is not bool:
            raise TypeError("may_retry_cleanly must be bool")
        if type(self.conceals_code_defect_if_retried) is not bool:
            raise TypeError("conceals_code_defect_if_retried must be bool")


def triage_failure(signature: FailureSignature) -> FailureDiagnosis:
    """Classify one failure using the ordered decision tree.

    Order matters and is deliberate: an unverifiable deployment claim and an
    empty test selection are decided first because no amount of green rerunning
    can make them true. A deterministic assertion is a code defect regardless of
    whether a subsequent rerun happened to pass.
    """
    if signature.deployment_claim and not signature.deployment_independently_observed:
        return FailureDiagnosis(
            FailureCategory.UNVERIFIABLE_DEPLOYMENT,
            "Deployment behaviour was not independently observed; provide a "
            "host receipt on the exact revision instead of assuming success.",
            may_retry_cleanly=False,
            conceals_code_defect_if_retried=False,
        )
    if signature.tests_selected == 0 or (
        signature.failure_kind is FailureKind.NONE_SELECTED
    ):
        return FailureDiagnosis(
            FailureCategory.ABSENT_PACKAGE_TESTS,
            "No tests were selected (marker or path mismatch); fix the selector "
            "or add the missing package tests.",
            may_retry_cleanly=False,
            conceals_code_defect_if_retried=True,
        )
    if signature.marker_filter_mismatch or (
        signature.failure_kind is FailureKind.COLLECTION
    ):
        return FailureDiagnosis(
            FailureCategory.TEST_CONFIGURATION,
            "Collection or marker configuration is wrong; correct the test "
            "selection before judging the code.",
            may_retry_cleanly=True,
            conceals_code_defect_if_retried=False,
        )
    if (
        signature.failure_kind is FailureKind.FILE_LOCK
        and signature.platform is Platform.WINDOWS
        and signature.resource_busy
    ):
        return FailureDiagnosis(
            FailureCategory.ENVIRONMENT_WINDOWS_LOCK,
            "A Windows file handle was still open; serialize teardown, retry "
            "once, and do not weaken the test.",
            may_retry_cleanly=True,
            conceals_code_defect_if_retried=False,
        )
    if (
        signature.failure_kind is FailureKind.IMPORT
        and signature.passing_under_pinned_install is True
    ):
        return FailureDiagnosis(
            FailureCategory.STALE_EDITABLE_INSTALLATION,
            "The editable install shadows the pinned distribution; rebuild and "
            "reinstall from the pinned wheel before re-testing.",
            may_retry_cleanly=True,
            conceals_code_defect_if_retried=False,
        )
    if (
        signature.failure_kind is FailureKind.ASSERTION
        and signature.assertion_is_deterministic is True
    ):
        return FailureDiagnosis(
            FailureCategory.CODE_DEFECT,
            "A deterministic functional assertion failed; fix the code, do not "
            "rerun to obtain green.",
            may_retry_cleanly=False,
            conceals_code_defect_if_retried=True,
        )
    return FailureDiagnosis(
        FailureCategory.UNKNOWN,
        "The signature is insufficient to decide; gather more evidence rather "
        "than assuming flakiness.",
        may_retry_cleanly=False,
        conceals_code_defect_if_retried=True,
    )
