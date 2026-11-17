"""Disposable guided-installer acceptance harness tests.

These tests exercise the synthetic harness only. A green harness is never an
installed-host or production authorization claim; the report must keep both
false and must not hide a lifecycle contract failure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.aegis_guided_installer_acceptance import (
    LABEL, SCHEMA, run_acceptance,
)

pytestmark = pytest.mark.pkg_ops
SOURCE_SHA = "a" * 40


@pytest.fixture(scope="module")
def report(tmp_path_factory, platform_wheels):
    root = tmp_path_factory.mktemp("guided-installer-acceptance")
    return run_acceptance(
        work_root=root, wheels=platform_wheels, source_sha=SOURCE_SHA,
    )


def _scenario(document, name):
    return next(item for item in document["scenarios"] if item["name"] == name)


def _successful_commands(document):
    return {
        item["command"]: item for item in document["commands"]
        if item["outcome"] in {
            "INSTALLED", "VERIFIED", "UPDATED", "REPAIRED", "ROLLED_BACK",
            "UNINSTALLED", "REINSTALLED", "OK",
        }
    }


def test_report_is_explicitly_simulated_and_never_claims_host_certification(report):
    assert report["schema"] == SCHEMA
    assert report["label"] == LABEL
    assert report["simulated"] is True
    assert report["installed_host_verified"] is False
    assert report["production_authorized"] is False
    assert report["certified"] is False
    assert report["fixture_signing_only"] is True
    assert report["source_sha"] == SOURCE_SHA
    assert any("real signed" in item.lower() for item in report["limitations"])


def test_report_contains_exact_source_and_artifact_digests(report):
    assert report["source_sha"] == SOURCE_SHA
    assert report["trust_anchor"]["expected_source_sha"] == SOURCE_SHA
    assert report["trust_anchor"]["publisher_key_sha256"]
    assert len(report["bundles"]) >= 6
    assert report["artifact_digests"]
    for release_id, digests in report["artifact_digests"].items():
        assert release_id
        assert len(digests["manifest_sha256"]) == 64
        assert digests["assets"]
    for bundle in report["bundles"]:
        assert bundle["source_sha"] == SOURCE_SHA
        assert len(bundle["manifest_sha256"]) == 64
        assert bundle["assets"]
        assert all(len(digest) == 64 for digest in bundle["assets"].values())
        assert "aegis-platform-service" in bundle["assets"]
        assert "python-runtime.zip" in bundle["assets"]
        assert "dependency-index.json" in bundle["assets"]


def test_guided_discovery_needs_no_manual_sha_approval_or_python_inputs(report):
    scenario = _scenario(report, "guided_discovery_no_manual_inputs")
    assert scenario["pass"] is True
    observed = scenario["observed"]
    assert observed["manual_inputs_required"] == []
    assert observed["discovered"]["expected_source_sha"] == SOURCE_SHA
    assert observed["verify_outcome"] == "VERIFIED"


def test_operator_apps_launcher_path_and_shortcut_are_idempotent(report):
    scenario = _scenario(report, "operator_apps_idempotent")
    assert scenario["pass"] is True
    observed = scenario["observed"]
    assert observed["launchers"] == ["aegis.cmd", "aegis.ps1"]
    assert observed["shortcuts_created"] == 2
    assert observed["shortcuts_removed"] == 2
    assert observed["first_path_action"] == "ADD"
    assert observed["second_path_action"] == "NO_CHANGE"
    assert observed["uninstall_path_action"] == "REMOVE"
    assert observed["second_uninstall_path_action"] == "NO_CHANGE"


def test_stop_and_revoked_owner_proof_deny_before_any_effect(report):
    stop = _scenario(report, "stop_denied")
    assert stop["pass"] is True
    assert stop["observed"]["stop_active"] is True
    assert stop["observed"]["outcome"] == "DENIED"
    assert stop["observed"]["native_effects"] == 0

    revoked = _scenario(report, "revoked_owner_proof_denied")
    assert revoked["pass"] is True
    assert revoked["observed"]["revoked_owner_proof"] is True
    assert revoked["observed"]["outcome"] == "DENIED"
    assert revoked["observed"]["native_effects"] == 0


def test_all_negative_release_trust_and_dependency_cases_are_denied(report):
    scenario = _scenario(report, "negative_release_and_trust_cases")
    assert scenario["pass"] is True
    cases = scenario["observed"]["cases"]
    names = {item["scenario"] for item in cases}
    assert {
        "missing_trust_anchor", "wrong_trust_pin", "wrong_trust_signer",
        "wrong_source_sha", "stale_revision_floor", "wrong_release_target",
        "wrong_parent_manifest", "trust_inside_bundle",
        "tampered_release_manifest", "tampered_release_signature",
        "tampered_release_asset", "missing_dependency_wheelhouse",
        "missing_runtime_asset",
    } <= names
    for item in cases:
        assert item["outcome"] == "DENIED"
        assert item["executed"] is False
        assert item["owner_approved"] is False
        assert item["destination_exists"] is False
        assert item["native_effects"] == 0
        assert item["history_entries"] == 0


def test_lifecycle_reports_the_repair_contract_blocker_without_fabricating_pass(report):
    scenario = _scenario(report, "default_guided_lifecycle")
    assert scenario["pass"] is False
    assert "error" not in scenario
    observed = scenario["observed"]
    assert observed["failures"]
    failure = observed["failures"][0]
    assert failure["operation"] == "repair_after_update"
    assert failure["outcome"] == "DENIED"

    successful = _successful_commands(report)
    assert successful["install"]["outcome"] == "INSTALLED"
    assert successful["verify"]["outcome"] == "VERIFIED"
    assert successful["update"]["outcome"] == "UPDATED"
    assert successful["rollback"]["outcome"] == "ROLLED_BACK"
    assert successful["uninstall"]["outcome"] == "UNINSTALLED"
    assert successful["reinstall"]["outcome"] == "REINSTALLED"
    assert successful["status"]["outcome"] == "OK"
    assert successful["repair"]["outcome"] == "REPAIRED"
    assert observed["pre_update_repair"] == "REPAIRED"
    denied_repair = [
        item for item in report["commands"]
        if item["command"] == "repair" and item["outcome"] == "DENIED"
    ]
    assert len(denied_repair) == 1
    assert denied_repair[0]["attempts"][-1]["required_approval"] is None
    assert observed["durable_revision_floor"] == 5
    assert observed["identity_preserved"] is True
    assert observed["protected_state_preserved"] is True
    assert observed["post_reinstall_installed_verified"] is True
    assert observed["native_journal_phase"] == "SERVICE_OBSERVED"
    assert observed["single_writer_state"].count("platform.db") == 1
    assert "sofia.db" not in observed["single_writer_state"]


def test_lifecycle_has_no_duplicate_service_launcher_or_writer(report):
    observed = _scenario(report, "default_guided_lifecycle")["observed"]
    effects = observed["effects"]
    assert len(effects) == 6
    assert [item["process_state"] for item in effects] == [
        "RUNNING", "RUNNING", "RUNNING", "RUNNING", "REMOVED", "RUNNING",
    ]
    assert observed["effect_count"] == len(effects)
    assert observed["operator_launchers_after_uninstall"] == 0


def test_report_marks_overall_pass_false_for_the_unresolved_repair_blocker(report):
    assert report["pass"] is False
    assert report["scenario_count"] == 6
    assert report["command_count"] >= 10
    assert report["installed_host_verified"] is False
    assert report["production_authorized"] is False
    json.dumps(report, sort_keys=True, allow_nan=False, default=str)


def test_check_mode_is_preview_only_with_zero_effects(tmp_path, platform_wheels):
    report = run_acceptance(
        check=True, work_root=tmp_path / "check", wheels=platform_wheels,
        source_sha=SOURCE_SHA,
    )
    assert report["mode"] == "check"
    assert report["preview_only"] is True
    assert report["pass"] is True
    assert report["installed_host_verified"] is False
    assert report["production_authorized"] is False
    scenario = _scenario(report, "check_preview_zero_effects")
    assert scenario["pass"] is True
    observed = scenario["observed"]
    assert observed["destination_exists"] is False
    assert observed["native_effects"] == 0
    assert observed["shortcut_effects"] == 0
    assert observed["store_history_entries"] == 0
    assert observed["preview_executed"] is False
    assert observed["preview_owner_approved"] is False
    assert observed["preview_production_authorized"] is False
