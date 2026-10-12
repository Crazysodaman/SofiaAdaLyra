"""Artemis host controller acceptance contracts, no live VM or DB mutation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from sofia.ops import artemis_controller as controller
from sofia.ops import artemis_controller_admin as admin
from sofia.ops import artemis_controller_service as service


VM_ID = UUID("1f50d0cd-7b50-4df0-8d9e-d1f03ec57565")
NOW = datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc)


def config(tmp_path):
    return controller.ArtemisControllerConfig(
        expected_vm_id=VM_ID,
        audit_directory=tmp_path,
        poll_seconds=60,
    )


def report(*, vm_id=VM_ID, name="Sofia", state="Running",
           blockers=(), can_activate=False):
    return {
        "host_inventory": {
            "Name": name, "VmId": str(vm_id), "State": state,
        },
        "read_only_review": {
            "inventory_eligible_for_review": not blockers,
            "host_blockers": list(blockers),
            "may_activate_canonical_writer": can_activate,
        },
        "canonical_writer_active": "unverified",
        "activation_authorized": False,
    }


def test_exact_artemis_hyperv_inventory_is_independent_read_only_receipt(tmp_path):
    attempts = []
    result = controller.controller_once(
        config(tmp_path),
        inventory=lambda: attempts.append("inventory") or report(),
        hostname=lambda: "Artemis",
    )
    assert attempts == ["inventory"]
    assert result["vm_id"] == str(VM_ID)
    assert result["vm_state"] == "Running"
    assert result["outcome"] == "observed"
    assert result["canonical_writer_verified"] is False
    assert result["guest_os_verified"] is False
    assert result["old_writer_fenced"] is False
    assert result["migration_authorized"] is False
    assert result["host_change_performed"] is False
    assert result["sequence"] == 1
    assert len(result["sha256"]) == 64

    journal = controller.ArtemisControllerJournal(tmp_path)
    assert journal.inspect() == (1, result["sha256"])


def test_second_observation_extends_durable_chain(tmp_path):
    setup = config(tmp_path)
    first = controller.controller_once(
        setup, inventory=lambda: report(), hostname=lambda: "artemis",
    )
    second = controller.controller_once(
        setup, inventory=lambda: report(state="Off"), hostname=lambda: "Artemis",
    )
    assert second["sequence"] == 2
    assert second["previous_sha256"] == first["sha256"]
    assert second["vm_state"] == "Off"
    assert controller.ArtemisControllerJournal(tmp_path).inspect()[0] == 2


@pytest.mark.parametrize("bad", [
    report(vm_id=UUID("a1bbdd6c-5424-4c7a-8f42-123456789012")),
    report(name="Hephaestus"),
    report(can_activate=True),
    {"host_inventory": {"Name": "Sofia"}},
])
def test_invalid_host_inventory_does_not_claim_vm_or_writer_authority(tmp_path, bad):
    result = controller.observe_exact_sofia(
        config(tmp_path), inventory=lambda: bad,
        hostname=lambda: "Artemis", now=lambda: NOW,
    )
    assert result.outcome == "unavailable"
    assert result.observed_vm_id is None
    assert result.payload()["old_writer_fenced"] is False
    assert result.payload()["migration_authorized"] is False


def test_hyperv_unavailable_produces_explicit_unknown_receipt(tmp_path):
    def unreachable():
        raise RuntimeError("hypervisor PowerShell failure")
    observation = controller.observe_exact_sofia(
        config(tmp_path), inventory=unreachable,
        hostname=lambda: "Artemis", now=lambda: NOW,
    )
    assert observation.outcome == "unavailable"
    assert observation.blockers == ("unspecified_hyperv_inventory_failed",)


def test_host_refuses_non_artemis_before_hyperv_is_called(tmp_path):
    calls = []
    with pytest.raises(controller.ArtemisControllerError, match="outside Artemis"):
        controller.controller_once(
            config(tmp_path), inventory=lambda: calls.append(1),
            hostname=lambda: "Venus",
        )
    assert calls == []
    assert not list(tmp_path.glob("*.jsonl"))


def test_external_network_needs_review_not_approval(tmp_path):
    observation = controller.observe_exact_sofia(
        config(tmp_path),
        inventory=lambda: report(blockers=("external_virtual_switch_requires_operator_review",)),
        hostname=lambda: "Artemis",
        now=lambda: NOW,
    )
    assert observation.outcome == "requires_review"
    assert observation.payload()["migration_authorized"] is False


def test_corrupt_journal_refuses_future_append_and_does_not_repair(tmp_path):
    config_obj = config(tmp_path)
    controller.controller_once(
        config_obj, inventory=lambda: report(), hostname=lambda: "Artemis",
    )
    path = tmp_path / "artemis-controller.jsonl"
    before = path.read_bytes()
    path.write_bytes(before.replace(b'"vm_state":"Running"', b'"vm_state":"Off"'))
    with pytest.raises(controller.ArtemisControllerError, match="chain"):
        controller.controller_once(
            config_obj, inventory=lambda: report(), hostname=lambda: "Artemis",
        )
    assert path.read_bytes() != before
    assert path.read_bytes().count(b"\n") == 1


def test_partial_crash_line_refuses_implicit_truncation(tmp_path):
    path = tmp_path / "artemis-controller.jsonl"
    path.write_bytes(b'{"sequence":1')
    with pytest.raises(controller.ArtemisControllerError, match="partial"):
        controller.ArtemisControllerJournal(tmp_path).inspect()
    assert path.read_bytes() == b'{"sequence":1'


def test_config_fails_closed_on_missing_vm_uuid_and_forged_authority(tmp_path):
    cfg = {
        "schema": 1,
        "expected_host": "Artemis",
        "vm_name": "Sofia",
        "expected_vm_id": str(VM_ID),
        "audit_directory": str(tmp_path),
        "poll_seconds": 60,
    }
    path = tmp_path / "controller.json"
    path.write_text(json.dumps(cfg))
    assert controller.ArtemisControllerConfig.load(path).expected_vm_id == VM_ID
    cfg["enable_writer_promotion"] = True
    path.write_text(json.dumps(cfg))
    with pytest.raises(controller.ArtemisControllerError, match="schema"):
        controller.ArtemisControllerConfig.load(path)
    del cfg["enable_writer_promotion"]
    cfg["expected_vm_id"] = "unknown"
    path.write_text(json.dumps(cfg))
    with pytest.raises(controller.ArtemisControllerError, match="UUID"):
        controller.ArtemisControllerConfig.load(path)


@pytest.mark.parametrize("name", [
    "LocalSystem", "SYSTEM", "Administrator", "Artemis\\Administrator",
    "NT AUTHORITY\\SYSTEM", "NT AUTHORITY\\NetworkService", "user",
])
def test_privileged_or_unmanaged_scm_account_is_never_permitted(name):
    with pytest.raises(ValueError):
        admin.permitted_service_account(name)


def test_scoped_controller_service_registration_is_independent():
    assert service.SERVICE_NAME == "SofiaArtemisController"
    assert admin.CLASS_STRING.endswith("SofiaArtemisControllerService")
    assert "SofiaAdaLyraFleetAgent" != service.SERVICE_NAME
    assert admin.permitted_service_account("NT AUTHORITY\\LocalService") == admin.LOCAL_SERVICE
    assert admin.permitted_service_account("EXAMPLE\\sofia-host$") == "EXAMPLE\\sofia-host$"
    assert service.SofiaArtemisControllerService is not None


@pytest.mark.parametrize("diagnostic,expected", [
    ("Get-VM : Access is denied", "vm_inventory_permission_denied"),
    ("Get-VHD : Access is denied", "vhd_metadata_permission_denied"),
    ("Get-VMSwitch : Access is denied", "switch_metadata_permission_denied"),
    ("Get-VMNetworkAdapter : Access is denied", "vm_network_permission_denied"),
    ("Get-VM : The term 'Get-VM' is not recognized as the name of a cmdlet",
     "vm_inventory_powershell_hyperv_cmdlet_unavailable"),
    ("Get-VM : The RPC server is unavailable", "vm_inventory_hyperv_management_service_unavailable"),
    ("No such Hyper-V object", "unspecified_hyperv_inventory_failed"),
])
def test_hyperv_subprocess_failure_is_sanitized_in_local_service_receipts(
    tmp_path, diagnostic, expected,
):
    def broken():
        raise RuntimeError(diagnostic + " at C:\\Private\\DoNotLog\\Secret.key")
    observation = controller.observe_exact_sofia(
        config(tmp_path), inventory=broken,
        hostname=lambda: "Artemis", now=lambda: NOW,
    )
    assert observation.outcome == "unavailable"
    assert observation.blockers == (expected,)
    payload = observation.payload()
    assert "Secret" not in json.dumps(payload)
    assert not payload["migration_authorized"]
    assert not payload["old_writer_fenced"]
