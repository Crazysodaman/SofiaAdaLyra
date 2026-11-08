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


def test_d028_four_host_plan_is_inert_and_single_primary() -> None:
    plan_path = Path(__file__).resolve().parent / "fixtures" / "aegis_d028" / "qa_four_host_topology.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["schema"] == "aegis.qa.d028.disposable-four-host-plan.v1"
    assert plan["state"] == "PLAN_ONLY"
    assert plan["release_accepted"] is False
    assert plan["production_authorized"] is False
    assert plan["signed_os_installed_host_evidence"] == "NOT_COLLECTED"
    assert plan["actual_host_ids"] == []
    assert plan["live_production_targets"] == []
    assert plan["acceptance_claim"] == "NOT_CLAIMED"
    assert plan["required_completed_lib_cases"] == len(LIB_ROWS) == 16
    assert plan["original_acceptance_rows"] == COUNT == 38
    hosts = {row["id"]: row for row in plan["hosts"]}
    assert set(hosts) == {"W-EMPTY", "D-HUB", "D-CLIENT", "W-PEER"}
    assert all(row["platform_id"] == "OBSERVE_AFTER_INSTALL" for row in hosts.values())
    assert all(row["service_binary_sha256"] == "OBSERVE_AFTER_INSTALL"
               for row in hosts.values())
    assert hosts["D-HUB"]["role"] == "SOLE_PRIMARY_HUB"
    assert all(row["role"] != "SOLE_PRIMARY_HUB" for k, row in hosts.items()
               if k != "D-HUB")
    logical = plan["logical_library"]
    assert logical["primary_count"] == 1
    assert logical["primary_test_host"] == "D-HUB"
    assert logical["read_replica_test_hosts_initially"] == []
    assert plan["proposed_real_primary_placement"]["target_is_not_a_test_host"]
    assert plan["proposed_real_primary_placement"]["deployment_authorized"] is False


def test_d028_four_host_network_backup_and_approvals_fail_closed() -> None:
    path = Path(__file__).resolve().parent / "fixtures" / "aegis_d028" / "qa_four_host_topology.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    network = plan["network_isolation"]
    assert network["wan"].startswith("DENY_BY_DEFAULT")
    assert network["user_production_lan"] == "DENY"
    assert network["real_host_dns_and_discovery"] == "DISABLED"
    assert network["no_real_addresses_or_hostnames_embedded"] is True
    assert "EXTERNAL_INDEPENDENT_TRUST_ROOT" == plan["logical_library"]["publisher_signing_authority"]
    assert plan["logical_library"]["owner_authority"] == "SAME_CANONICAL_PLATFORM_SAFE_STOP"
    assert plan["backup_retention"]["deleted_pinned_artifacts_allowed"] is False
    assert plan["backup_retention"]["independent_physical_fault_domain_required_for_real_continuity_claim"]
    assert "sofia.db" in plan["backup_retention"]["must_exclude"]
    phase_ids = {p["id"] for p in plan["phase_sequence"]}
    assert "REPLICA_AND_RECOVERY" in phase_ids
    assert "COEXISTENCE_AND_RETENTION" in phase_ids
    assert all(p["status"] == "NOT_EXECUTED" for p in plan["phase_sequence"])
    combined = "\\n".join("|".join(p["require"]) for p in plan["phase_sequence"])
    assert "manual_promotion_only_after_old_primary_fence_and_independent_witness" in combined
    assert "recipient_reverifies_trusted_signature" in combined
    assert "restore_verified_off_primary_backup_no_core_state" in combined
