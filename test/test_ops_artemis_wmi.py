"""Restricted Artemis Hyper-V WMI observation and fallback safety tests."""
from __future__ import annotations

import json
from uuid import UUID

import pytest

from sofia.ops import artemis_controller as controller
from sofia.ops import artemis_wmi


VM_ID = UUID("1f50d0cd-7b50-4df0-8d9e-d1f03ec57565")


def response(*, name="Sofia", vm_id=VM_ID, enabled_state=2):
    return json.dumps({
        "VmId": str(vm_id),
        "Name": name,
        "EnabledState": enabled_state,
    })


def test_wmi_queries_only_pinned_guid_and_never_mutates_or_scans_other_guests():
    commands = []
    observer = artemis_wmi.ArtemisWmiObserver(
        expected_vm_id=VM_ID,
        runner=lambda script: commands.append(script) or response(),
    )
    result = observer()
    assert len(commands) == 1
    query = commands[0]
    assert "Get-CimInstance" in query
    assert "Msvm_ComputerSystem" in query
    assert "root/virtualization/v2" in query
    assert "-Filter \"Name='" + str(VM_ID) + "'\"" in query
    assert "Get-VM " not in query
    assert "Get-VMSwitch" not in query
    for mutation in (
        "Start-VM", "Stop-VM", "Set-VM ", "Remove-VM",
        "New-VM", "Invoke-CimMethod", "Set-CimInstance",
    ):
        assert mutation not in query
    assert result["host_inventory"]["VmId"] == str(VM_ID)
    assert result["host_inventory"]["State"] == "WMI.EnabledState:2"
    assert result["read_only_review"]["inventory_eligible_for_review"] is False
    assert result["read_only_review"]["may_activate_canonical_writer"] is False
    assert result["activation_authorized"] is False
    assert result["canonical_writer_active"] == "unverified"
    assert result["observation_source"] == "hyperv_wmi_read_only"


def test_wmi_monitoring_still_never_confers_full_guest_readiness(tmp_path):
    cfg = controller.ArtemisControllerConfig(
        expected_vm_id=VM_ID, audit_directory=tmp_path
    )
    observed = controller.observe_exact_sofia(
        cfg,
        inventory=artemis_wmi.ArtemisWmiObserver(
            expected_vm_id=VM_ID, runner=lambda _: response()
        ),
        hostname=lambda: "Artemis",
    )
    assert observed.outcome == "requires_review"
    assert observed.observed_vm_id == str(VM_ID)
    assert observed.vm_state == "WMI.EnabledState:2"
    assert "wmi_identity_and_enabled_state_only" in observed.blockers
    assert observed.payload()["guest_os_verified"] is False
    assert observed.payload()["old_writer_fenced"] is False
    assert observed.payload()["migration_authorized"] is False
    assert observed.payload()["canonical_writer_verified"] is False


@pytest.mark.parametrize("payload", [
    response(vm_id=UUID("320a5199-71d2-41c6-997e-c52215412d19")),
    response(name="Hephaestus"),
    response(enabled_state=True),
    response(enabled_state=None),
    response(enabled_state=-1),
    response(enabled_state=65536),
    json.dumps([json.loads(response())]),
    json.dumps({"VmId": str(VM_ID), "Name": "Sofia"}),
    "not-json",
    "",
])
def test_wmi_rejects_untrusted_identity_or_state(payload):
    observer = artemis_wmi.ArtemisWmiObserver(
        expected_vm_id=VM_ID, runner=lambda _: payload
    )
    with pytest.raises(artemis_wmi.ArtemisWmiObservationError):
        observer()


def test_wmi_refuses_alternate_vm_configuration():
    with pytest.raises(artemis_wmi.ArtemisWmiObservationError, match="canonical"):
        artemis_wmi.ArtemisWmiObserver(
            expected_vm_id=VM_ID, vm_name="Hephaestus",
            runner=lambda _: response()
        )


def test_wmi_probe_is_available_as_explicit_diagnostic_only():
    """Do not automatically treat WMI namespace access as VM visibility."""
    observer = artemis_wmi.ArtemisWmiObserver(
        expected_vm_id=VM_ID, runner=lambda _: response(),
    )
    assert observer()["host_inventory"]["VmId"] == str(VM_ID)


def test_wmi_failure_fails_closed_without_logging_host_exception(tmp_path):
    def denied(_script):
        raise RuntimeError("CIM access denied C:\\Secret\\private.pem")
    cfg = controller.ArtemisControllerConfig(
        expected_vm_id=VM_ID, audit_directory=tmp_path
    )
    obs = controller.observe_exact_sofia(
        cfg,
        inventory=artemis_wmi.ArtemisWmiObserver(
            expected_vm_id=VM_ID, runner=denied
        ),
        hostname=lambda: "Artemis",
    )
    assert obs.outcome == "unavailable"
    assert obs.observed_vm_id is None
    assert obs.payload()["migration_authorized"] is False
    assert "Secret" not in json.dumps(obs.payload())
