"""Verify Platform shakedown preflight never promotes component tests to GO."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.aegis_platform_row_preflight import (
    BLOCKED_BY_MISSING_INTEGRATION, COUNT, LIB_ROWS, PROBES,
    make_library_preflight, make_report,
)

pytestmark = pytest.mark.pkg_ops


def _junit(tmp_path: Path, cases: str) -> Path:
    path = tmp_path / "unit-results.xml"
    path.write_text("<testsuites><testsuite>" + cases + "</testsuite></testsuites>",
                    encoding="utf-8")
    return path


def test_exactly_38_rows_and_no_release_claim(tmp_path: Path) -> None:
    report = make_report(None, "a" * 40, "win32")
    assert report["row_count"] == COUNT == 38
    assert len(PROBES) == 25
    assert len(BLOCKED_BY_MISSING_INTEGRATION) == 13
    assert [int(row["row_id"]) for row in report["rows"]] == list(range(1, 39))
    assert all(row["acceptance"] == "NOT_CLAIMED" for row in report["rows"])
    assert all(row["signed_installed_host_receipt"] == "REQUIRED"
               for row in report["rows"])
    assert not report["release_accepted"]
    assert not report["production_authorized"]
    assert report["junit_source"] == "JUNIT_UNAVAILABLE"
    assert report["rows"][9]["preflight"] == "BLOCKED_MISSING_INTEGRATION"


def test_one_pass_does_not_fake_full_coverage(tmp_path: Path) -> None:
    case = '<testcase classname="test.test_platform_optional_dependencies" name="safe"/>'
    report = make_report(_junit(tmp_path, case), "b" * 40, "linux")
    assert report["rows"][1]["preflight"] == "PARTIAL_OR_OS_SKIPPED"
    assert report["rows"][1]["observed_cases"] == 1
    assert report["rows"][1]["acceptance"] == "NOT_CLAIMED"


def test_actual_failed_and_skipped_cases_remain_visible(tmp_path: Path) -> None:
    cases = (
        '<testcase classname="test.test_platform_installation_identity" name="okay"/>'
        '<testcase classname="test.test_platform_installation_identity" name="fail">'
        '<failure message="expected"/></testcase>'
        '<testcase classname="test.test_rust_platform_scm" name="windows-only">'
        '<skipped message="Linux"/></testcase>'
    )
    report = make_report(_junit(tmp_path, cases), "c" * 40, "linux")
    assert report["rows"][3]["preflight"] == "COMPONENT_FAIL"
    assert report["rows"][5]["preflight"] == "PARTIAL_OR_OS_SKIPPED"
    assert report["rows"][5]["acceptance"] == "NOT_CLAIMED"


def test_rejects_invalid_junit_xml(tmp_path: Path) -> None:
    bad = tmp_path / "broken.xml"
    bad.write_text("<testsuites><testcase>", encoding="utf-8")
    with pytest.raises(Exception):
        make_report(bad, "d" * 40, "linux")


def test_generated_report_is_bounded_and_no_sensitive_payloads(tmp_path: Path) -> None:
    report = make_report(None, "e" * 40, "linux")
    encoded = json.dumps(report)
    assert len(encoded) < 30000
    assert "SOFIA_OWNER_SECRET" not in encoded
    assert all(row["preflight"] != "PASS" for row in report["rows"])


def test_artifact_library_opt_in_preserves_canonical_38_rows(tmp_path: Path) -> None:
    default = make_report(None, "f" * 40, "linux")
    extended = make_report(
        None, "f" * 40, "linux", include_artifact_library=True,
    )
    assert "artifact_library" not in default  # Stable v1 output for existing consumers.
    assert extended["row_count"] == default["row_count"] == 38
    assert extended["rows"] == default["rows"]  # No canonical row promotion.
    lib = extended["artifact_library"]
    assert lib == make_library_preflight()
    assert lib["scenario_count"] == 16
    assert list(LIB_ROWS) == [f"LIB-{i:02d}" for i in range(1, 17)]
    assert [case["scenario_id"] for case in lib["scenarios"]] == list(LIB_ROWS)
    assert lib["acceptance"] == "NOT_CLAIMED"
    assert not lib["release_accepted"] and not lib["production_authorized"]
    assert all(case["acceptance"] == "NOT_CLAIMED" for case in lib["scenarios"])
    assert all(case["signed_windows_debian_host_receipts"] == "REQUIRED"
               for case in lib["scenarios"])
    assert all(case["positive_negative_cases"] == "NOT_VERIFIED"
               for case in lib["scenarios"])
    assert set(int(i) for row in lib["scenarios"]
               for i in row["refined_platform_rows"]) <= set(range(1, 39))


def test_library_component_junit_pass_does_not_become_host_acceptance(tmp_path: Path) -> None:
    junit = _junit(
        tmp_path,
        '<testcase classname="test.test_platform_optional_dependencies" '
        'name="source-probe"/>'
    )
    report = make_report(
        junit, "1" * 40, "win32", include_artifact_library=True,
    )
    assert report["rows"][1]["preflight"] == "PARTIAL_OR_OS_SKIPPED"
    assert report["artifact_library"]["scenario_count"] == 16
    assert all(case["preflight"] == "BLOCKED_NO_SIGNED_INSTALLED_HOST_EVIDENCE"
               for case in report["artifact_library"]["scenarios"])
    assert not report["release_accepted"]
    assert not report["artifact_library"]["release_accepted"]


def test_library_map_preserves_specific_d028_signed_and_revocation_rows() -> None:
    assert LIB_ROWS["LIB-01"] == (1, 2, 3, 5, 28, 30, 38)
    assert LIB_ROWS["LIB-02"] == (1, 2, 3, 7, 28, 30, 33, 38)
    assert {10, 11, 12, 13, 14}.issubset(LIB_ROWS["LIB-08"])
    assert {17, 18, 19, 21, 25, 28, 29}.issubset(LIB_ROWS["LIB-09"])
    assert {10, 11, 12, 19, 22, 29, 37}.issubset(LIB_ROWS["LIB-13"])
    assert LIB_ROWS["LIB-14"] == tuple(range(30, 39))
    assert LIB_ROWS["LIB-16"] == (29, 30, 32, 33, 34, 35, 36, 37, 38)
