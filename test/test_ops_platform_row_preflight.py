"""Verify Platform shakedown preflight never promotes component tests to GO."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.aegis_platform_row_preflight import (
    BLOCKED_BY_MISSING_INTEGRATION, COUNT, PROBES, make_report,
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
