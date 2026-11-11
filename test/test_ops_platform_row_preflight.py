"""Verify Platform shakedown preflight never promotes component tests to GO."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from tools.aegis_platform_row_preflight import (
    BLOCKED_BY_MISSING_INTEGRATION, COUNT, LIB_ROWS, PROBES,
    D028_EVIDENCE_FILES, make_d028_four_host_preflight,
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


def _d028_plan() -> dict:
    path = Path(__file__).resolve().parent / "fixtures" / "aegis_d028" / "qa_four_host_topology.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_d028_runnable_harness_has_16_blocked_cases_and_no_acceptance() -> None:
    report = make_d028_four_host_preflight("a" * 40, topology=_d028_plan())
    assert report["schema"] == "aegis.d028.four-host-evidence-intake.v1"
    assert report["host_ids"] == ["W-EMPTY", "D-HUB", "D-CLIENT", "W-PEER"]
    assert report["one_initial_primary"] is True
    assert report["initial_replica_count"] == 0
    assert not report["evidence_dir_supplied"]
    assert report["scenario_count"] == len(LIB_ROWS) == 16
    assert [x["scenario_id"] for x in report["scenarios"]] == list(LIB_ROWS)
    assert all(x["receipt_inspection"] == "NOT_EXECUTED" for x in report["scenarios"])
    assert all(x["acceptance"] == "NOT_CLAIMED" for x in report["scenarios"])
    assert all(x["signed_installed_host_witness"] == "NOT_VERIFIED"
               for x in report["scenarios"])
    assert report["publisher_signature_and_revocation"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert report["OS_installed_service_and_enrolled_SAFE"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert report["release_accepted"] is False
    assert report["production_authorized"] is False


@pytest.mark.parametrize("bad_case", [
    "production", "second_primary", "reader_grants", "wan", "fake_execution",
    "fake_release_pass", "source_sha",
])
def test_d028_runnable_harness_rejects_unsafe_topology(bad_case: str) -> None:
    plan = _d028_plan()
    source = "b" * 40
    if bad_case == "production":
        plan["live_production_targets"] = ["DO_NOT_TOUCH_HOST"]
    elif bad_case == "second_primary":
        plan["logical_library"]["primary_count"] = 2
    elif bad_case == "reader_grants":
        plan["logical_library"]["owner_authority"] = "HUB_LOCAL_ADMIN"
    elif bad_case == "wan":
        plan["network_isolation"]["user_production_lan"] = "ALLOW"
    elif bad_case == "fake_execution":
        plan["phase_sequence"][0]["status"] = "PASSED"
    elif bad_case == "fake_release_pass":
        plan["release_accepted"] = True
    else:
        source = "fake-sha"
    with pytest.raises(ValueError):
        make_d028_four_host_preflight(source, topology=plan)


def test_d028_runnable_harness_rehashes_bytes_but_does_not_trust_signer(
    tmp_path: Path,
) -> None:
    exact = "c" * 40
    payload = tmp_path / "artifacts" / "synthetic-seed.bin"
    payload.parent.mkdir()
    payload.write_bytes(b"non-executable mock package bytes only")
    digest = sha256(payload.read_bytes()).hexdigest()
    (tmp_path / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": exact,
        "artifacts": [{"path": "artifacts/synthetic-seed.bin", "sha256": digest}],
        "signature_valid": True,   # Never trust an unsigned JSON Boolean.
    }), encoding="utf-8")
    (tmp_path / "LIB-01.json").write_text(json.dumps({
        "scenario_id": "LIB-01", "source_sha": exact, "status": "PASS",
    }), encoding="utf-8")
    report = make_d028_four_host_preflight(
        exact, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert report["byte_digests_verified_only"] == [digest]
    assert report["evidence_invalid"] == []
    assert "release-manifest.json" in report["evidence_missing"]
    assert len(report["evidence_missing"]) == 5 + 15
    assert report["scenarios"][0]["receipt_inspection"] == (
        "RECEIPT_PRESENT_INDEPENDENT_REVIEW_REQUIRED"
    )
    assert report["scenarios"][0]["acceptance"] == "NOT_CLAIMED"
    assert report["publisher_signature_and_revocation"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert report["signed_Hub_index_and_peer_receipts"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert report["release_accepted"] is False
    assert report["production_authorized"] is False
    assert set(D028_EVIDENCE_FILES) - {"signed-artifacts.json"} <= set(report["evidence_missing"])


def test_d028_runnable_harness_rejects_changed_bytes_wrong_sha_and_links(
    tmp_path: Path,
) -> None:
    exact = "d" * 40
    (tmp_path / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": exact, "artifacts": [
            {"path": "artifacts/payload.bin", "sha256": sha256(b"expected").hexdigest()},
            {"path": "../escape.bin", "sha256": "a" * 64},
            {"path": "private-state.db", "sha256": sha256(b"private").hexdigest()},
        ],
    }), encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "payload.bin").write_bytes(b"tampered")
    (tmp_path / "private-state.db").write_bytes(b"private")
    (tmp_path / "LIB-02.json").write_text(json.dumps({
        "scenario_id": "LIB-02", "source_sha": "e" * 40, "status": "PASS",
    }), encoding="utf-8")
    try:
        (tmp_path / "link.json").symlink_to(tmp_path / "signed-artifacts.json")
    except (OSError, NotImplementedError):
        pass
    report = make_d028_four_host_preflight(
        exact, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert "artifact[0]:BYTE_INTEGRITY_FAILED" in report["evidence_invalid"]
    assert "artifact[1]:BYTE_INTEGRITY_FAILED" in report["evidence_invalid"]
    assert "artifact[2]:BYTE_INTEGRITY_FAILED" in report["evidence_invalid"]
    assert "LIB-02.json:UNBOUND" in report["evidence_invalid"]
    assert report["byte_digests_verified_only"] == []
    assert report["scenarios"][1]["receipt_inspection"] == "REJECTED_UNBOUND_CASE_RECEIPT"
    assert not report["release_accepted"]


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX linked evidence inode semantics")
def test_d028_intake_rejects_hardlinked_artifact_bytes(tmp_path):
    import os
    exact = "e" * 40
    source = tmp_path / "other.bin"
    source.write_bytes(b"source-only untrusted artifact")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    os.link(source, artifacts / "payload.bin")
    (tmp_path / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": exact,
        "artifacts": [{"path": "artifacts/payload.bin",
                       "sha256": sha256(source.read_bytes()).hexdigest()}],
    }), encoding="utf-8")
    report = make_d028_four_host_preflight(
        exact, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert "artifact[0]:BYTE_INTEGRITY_FAILED" in report["evidence_invalid"]
    assert report["byte_digests_verified_only"] == []
    assert not report["release_accepted"]


def test_d028_runnable_harness_fails_closed_on_symlinked_signed_metadata(
    tmp_path: Path,
) -> None:
    target = tmp_path / "external-metadata.json"
    target.write_text('{"source_sha":"' + "f" * 40 + '"}', encoding="utf-8")
    link = tmp_path / "release-manifest.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links unavailable")
    report = make_d028_four_host_preflight(
        "f" * 40, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert "release-manifest.json" in report["evidence_invalid"]
    assert report["acceptance"] == "NOT_CLAIMED"
    assert not report["release_accepted"]


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX hard-link metadata provenance")
def test_d028_intake_rejects_hardlinked_metadata_even_with_matching_sha(tmp_path):
    import os
    exact = "f" * 40
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"source_sha": exact}), encoding="utf-8")
    os.link(outside, tmp_path / "release-manifest.json")
    report = make_d028_four_host_preflight(
        exact, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert "release-manifest.json" in report["evidence_invalid"]
    assert report["acceptance"] == "NOT_CLAIMED"
    assert not report["release_accepted"]


def test_d028_cli_can_plan_but_never_greenlight_supplied_host_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    import sys
    from tools import aegis_platform_row_preflight as qa

    exact = "a" * 40
    monkeypatch.setattr(qa, "_git_sha", lambda: exact)
    monkeypatch.setattr(sys, "argv", [
        "aegis_platform_row_preflight", "--d028-four-host",
    ])
    assert qa.main() == 0  # Planning validity, not signed-host evidence.
    no_receipts = json.loads(capsys.readouterr().out)
    assert no_receipts["d028_four_host"]["acceptance"] == "NOT_CLAIMED"
    assert no_receipts["d028_four_host"]["evidence_dir_supplied"] is False

    monkeypatch.setattr(sys, "argv", [
        "aegis_platform_row_preflight", "--d028-four-host",
        "--d028-evidence-dir", str(tmp_path),
    ])
    assert qa.main() == 2  # Missing actual signed-host evidence cannot green CI.
    missing = json.loads(capsys.readouterr().out)
    assert missing["d028_four_host"]["evidence_missing"]

    for name in D028_EVIDENCE_FILES:
        (tmp_path / name).write_text(json.dumps({"source_sha": exact}), encoding="utf-8")
    payload = tmp_path / "artifacts" / "synthetic-reviewed-bytes.bin"
    payload.parent.mkdir()
    payload.write_bytes(b"synthetic source bytes, NOT a signed native installer")
    (tmp_path / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": exact,
        "artifacts": [{"path": "artifacts/synthetic-reviewed-bytes.bin",
                       "sha256": sha256(payload.read_bytes()).hexdigest()}],
        "signature_valid": True,  # Still just a self-reported string.
    }), encoding="utf-8")
    for case in LIB_ROWS:
        (tmp_path / (case + ".json")).write_text(json.dumps({
            "source_sha": exact, "scenario_id": case, "status": "PASS",
        }), encoding="utf-8")
    assert qa.main() == 3  # A full set of self-reported JSON remains UNTRUSTED.
    untrusted = json.loads(capsys.readouterr().out)
    assert untrusted["d028_four_host"]["evidence_missing"] == []
    assert untrusted["d028_four_host"]["evidence_invalid"] == []
    assert len(untrusted["d028_four_host"]["byte_digests_verified_only"]) == 1
    assert untrusted["d028_four_host"]["release_accepted"] is False
    assert all(entry["acceptance"] == "NOT_CLAIMED"
               for entry in untrusted["d028_four_host"]["scenarios"])


def test_d028_no_artifact_bytes_is_incomplete_not_receipt_ready(
    tmp_path: Path,
) -> None:
    exact = "1" * 40
    (tmp_path / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": exact,
        "artifacts": [],
        "signature_valid": True,
    }), encoding="utf-8")
    result = make_d028_four_host_preflight(
        exact, topology=_d028_plan(), evidence_dir=tmp_path,
    )
    assert "signed-artifacts.json:NO_ARTIFACT_BYTES" in result["evidence_invalid"]
    assert result["byte_digests_verified_only"] == []
    assert result["release_accepted"] is False


def _ig001_source_manifest() -> dict:
    path = (
        Path(__file__).resolve().parents[1]
        / "docs" / "development"
        / "PLATFORM_1_0_TEAM_E_IG001_REPRODUCIBLE_SOURCE_MANIFEST_2026-11-08.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_ig001_manifest_sources_pinned_and_no_authorization() -> None:
    """An unassembled QA source manifest never masquerades as installed release."""
    import re
    m = _ig001_source_manifest()
    assert m["schema"] == "aegis.platform.ig001.reproducible-integration-manifest.v1"
    assert m["milestone"] == "IG-001"
    assert m["source_snapshot_only"] is True
    assert m["integrated_tree_built"] is False
    assert m["integration_branch_created"] is False
    assert m["release_accepted"] is False
    assert m["production_authorized"] is False
    assert m["real_core_activation"] is False
    assert m["owner_hub_deployed"] is False
    assert m["qa_branch"] == "chatgpt/team-e-release-qa-20261108"
    assert re.fullmatch("[0-9a-f]{40}", m["reference_main_sha"])
    sources = m["dependency_sources"]
    assert {p["pr"] for p in sources} == {241, 244, 243, 251, 247, 249, 255, 245, 248}
    assert all(re.fullmatch("[0-9a-f]{40}", p["head"]) for p in sources)
    assert all(re.fullmatch("[0-9a-f]{40}", p["base"]) for p in sources)
    assert all(p["integrated"] is False for p in sources)
    assert m["acceptance"] == {
        "platform_total": 38, "platform_pass": 0,
        "platform_fail": 7, "platform_not_tested": 31,
        "library_total": 16, "library_pass": 0,
        "library_not_tested": 16,
        "ig001_functional_status": "NOT_EXECUTED",
        "milestone_ci": "NOT_COMPLETE", "go": "NO",
    }


def test_ig001_manifest_conflicts_and_execution_gates_fail_closed() -> None:
    m = _ig001_source_manifest()
    conflicts = {entry["path"]: entry for entry in m["overlapping_files"]}
    assert len(conflicts) == len(m["overlapping_files"]) == 8
    assert set(conflicts[".github/workflows/aegis-debian12-vm.yml"]["contributors"]) == {241, 245}
    service = conflicts["rust/crates/sofia-platform-lifecycle/src/bin/platform_service.rs"]
    assert set(service["contributors"]) == {241, 249, 255}
    assert "DO NOT cherry-pick" in service["resolution"]
    assert set(conflicts["test/conftest.py"]["contributors"]) == {251, 236, 239}
    assert all(c["status"] != "RESOLVED" for c in m["overlapping_files"])
    assert {item["state"] for item in m["semantic_boundaries"]} == {"HOLD"}
    phases = m["execution_phases"]
    assert len(phases) == 6
    assert all(p["status"] != "PASS" for p in phases)
    assert any(p["id"] == "G4_LIVE_STATUS_AND_DENIALS" and
               p["status"] == "BLOCKED_AUTHORITY_AND_UI" for p in phases)
    assert m["local_author_environment"]["cargo"] is False
    assert m["local_author_environment"]["qemu"] is False
    assert m["proposed_disposable_environment"]["required_os"] == "Debian GNU/Linux 12 x86_64"
    assert m["proposed_disposable_environment"]["personal_core"] is False
    assert "STOP before and midrequest" in m["security_negatives_must_preserve"]


def test_ig001_e008_assembled_source_does_not_claim_functional_acceptance() -> None:
    """Git object assembly is not an installed service, signer or release gate."""
    import re
    p = (
        Path(__file__).resolve().parents[1] / "docs" / "development"
        / "PLATFORM_1_0_TEAM_E_E008_SOURCE_ASSEMBLY_RECEIPT_2026-11-08.json"
    )
    row = json.loads(p.read_text(encoding="utf-8"))
    assert row["schema"] == "aegis.platform.ig001.e008.source-assembly-receipt.v1"
    assert re.fullmatch(r"[0-9a-f]{40}", row["integrated_source_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", row["integration_tree_sha"])
    assert {p["pr"] for p in row["source_prs"]} == {241, 244, 243, 258, 245}
    assert row["overlay_tree_entries"] == 78
    assert row["shared_contract_blobs_identical"] == 6
    assert row["source_only_verified"] is True
    assert row["compiled_integrated_platform"] is False
    assert row["disposable_host_executed"] is False
    assert row["genuine_platform_status_observed"] is False
    assert row["canonical_writer_recovery_witness"] is False
    assert row["integrated_milestone_ci"] == "NOT_STARTED"
    assert row["release_accepted"] is False
    assert row["production_authorized"] is False
    assert row["personal_core_activated"] is False
    assert row["acceptance"] == {
        "platform_38_pass": 0, "platform_38_fail": 7,
        "platform_38_not_tested": 31, "library_16_pass": 0,
        "library_16_not_tested": 16, "go": "NO",
    }
    assert {x["team"] for x in row["first_functional_blockers"]} >= {"B", "C", "E"}
