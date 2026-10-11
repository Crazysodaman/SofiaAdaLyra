"""Source-only regression coverage for operator-created Sofia VM pre-OS readiness.

Hyper-V host inventory proves neither an installed Debian guest nor a
permission to relocate, promote or run canonical sofia.db.
"""
from __future__ import annotations

import json
from uuid import UUID

import pytest

from sofia.integrations.hyperv import HyperVAdapter, HyperVError
from sofia.ops.sofia_guest_readiness import (
    VM_NAME, review_sofia_guest_inventory,
)
from sofia.safe.permissions import (
    PermissionLevel, capability_permission_policy,
)
from sofia.distributed.authorization import remote_operation_is_read_only

VM_ID = "1f50d0cd-7b50-4df0-8d9e-d1f03ec57565"


def observed_vm(*, switch="Internal", disk=True, generation=2):
    return {
        "Name": "Sofia",
        "VmId": VM_ID,
        "Generation": generation,
        "State": "Off",
        "Processors": 4,
        "StartupMemoryBytes": 4096 * 1024 * 1024,
        "Disks": [{"Path": r"D:\\VMs\\Sofia\\Sofia.vhdx", "Size": 64 * 1024**3}] if disk else [],
        "NetworkAdapters": [{"SwitchName": "GuestInternal", "SwitchType": switch}],
        "DvdPaths": [],
        "ObservedAtUtc": "2026-10-11T14:44:00Z",
    }


def test_created_hyperv_vm_does_not_imply_debian_installed_or_writer_ready():
    review = review_sofia_guest_inventory(observed_vm())
    assert review.observed_vm_id == str(UUID(VM_ID))
    assert review.inventory_eligible_for_review
    assert not review.host_blockers
    assert review.guest_os_verified is False
    assert review.migration_authorized is False
    assert review.may_activate_canonical_writer is False


@pytest.mark.parametrize("observation,expected", [
    (None, "hyperv_vm_not_observed"),
    ({"Name": "Hephaestus"}, "wrong_production_vm_name"),
    (observed_vm(disk=False), "guest_boot_disk_not_verified"),
    (observed_vm(generation=1), "hyperv_generation_2_not_verified"),
    (observed_vm(switch="Unknown"), "guest_network_topology_not_observed"),
    (observed_vm(switch="External"), "external_virtual_switch_requires_operator_review"),
])
def test_missing_or_unreviewed_host_facts_block_inventory_review(observation, expected):
    report = review_sofia_guest_inventory(observation)
    assert expected in report.host_blockers
    assert not report.inventory_eligible_for_review
    assert not report.may_activate_canonical_writer


def test_immutable_observation_rejects_malformed_vm_identity():
    report = review_sofia_guest_inventory({**observed_vm(), "VmId": "not-a-guid"})
    assert "hyperv_vm_id_missing_or_invalid" in report.host_blockers
    with pytest.raises(TypeError):
        review_sofia_guest_inventory(["not a VM"])


def test_real_hyperv_adapter_queries_only_exact_named_vm_without_changes():
    calls = []
    adapter = HyperVAdapter(
        lambda command: calls.append(command) or json.dumps(observed_vm()),
    )
    received = adapter.sofia_guest_inventory()
    assert len(calls) == 1
    command = calls[0]
    assert "Get-VM -Name 'Sofia'" in command
    assert "Get-VMHardDiskDrive" in command
    assert "Get-VMNetworkAdapter" in command
    assert "Get-VMDvdDrive" in command
    for mutation in ("Start-VM ", "Stop-VM ", "Set-VM ", "New-VM ", "Remove-VM ", "Install-"):
        assert mutation not in command
    assert received["host_inventory"]["Name"] == VM_NAME
    assert received["read_only_review"]["inventory_eligible_for_review"] is True
    assert received["guest_os_installed"] == "unverified"
    assert received["canonical_writer_active"] == "unverified"
    assert received["activation_authorized"] is False


def test_host_wrong_vm_observation_fails_closed():
    adapter = HyperVAdapter(lambda command: json.dumps({**observed_vm(), "Name": "other"}))
    with pytest.raises(HyperVError, match="reserved Sofia VM"):
        adapter.sofia_guest_inventory()


def test_local_and_remote_guest_inspection_is_explicit_read_only_authority():
    assert capability_permission_policy(
        "hyperv.sofia.inspect",
    ).level is PermissionLevel.OBSERVE_READ
    assert remote_operation_is_read_only("vm.inspect", "sofia_preflight")
    assert capability_permission_policy(
        "remote.vm.sofia.inspect",
    ).level is PermissionLevel.OBSERVE_READ
    assert not remote_operation_is_read_only("vm.manage", "start")


def test_actual_remote_tool_routes_exact_guest_inspection_through_fleet(
    monkeypatch, tmp_path,
):
    from sofia.distributed import capability as remote_module
    calls = []

    class FakeFleet:
        def invoke(self, node_id, capability, operation, params):
            calls.append((node_id, capability, operation, params))
            return {"source": "enrolled-agent", "status": "unverified"}

    monkeypatch.setattr(
        remote_module, "create_configured_remote_fleet_service",
        lambda state_path: FakeFleet(),
    )
    registered = {
        item.capability.name: item
        for item in remote_module.create_configured_remote_fleet_tools(
            tmp_path / "sofia.db",
        )
    }
    bound = registered["remote.vm.sofia.inspect"]
    from sofia.capability.model import CapabilityRequest
    request = CapabilityRequest(
        capability=bound.capability,
        parameters={"node_id": VM_ID},
        requested_scope=None,
        rationale="Read only guest installation planning",
    )
    assert bound.handler(request) == {
        "source": "enrolled-agent", "status": "unverified",
    }
    assert calls == [(VM_ID, "vm.inspect", "sofia_preflight", {})]
