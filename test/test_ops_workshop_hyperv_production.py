"""Deferred production Hyper-V preflight and immutable workshop plan contracts.

All fixture PowerShell responses are synthetic. No host, VM, CI or test
execution is authorized by this file.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from sofia.integrations.hyperv import HyperVAdapter
from sofia.distributed.capability import RemoteFleetToolService
from sofia.ops.workshop_provision import (
    EXPECTED_SWITCH,
    WorkshopProvisionPlan,
    inspect_workshop_plan,
    observed_hyperv_host,
    preview_owner_hephaestus_plan,
)

pytestmark=pytest.mark.pkg_ops
NOW=datetime(2026,10,11,18,tzinfo=timezone.utc)
NODE=str(uuid4())


def plan(**overrides):
    data=dict(
        plan_id="hephaestus:stage-123",
        hypervisor_host_id=NODE,
        hypervisor_version="WindowsHyperV/10.0.20348",
        guest_name="Hephaestus",
        vm_root=r"D:\SofiaLab\Hephaestus",
        installer_image_path=r"E:\ApprovedImages\debian-12.vhdx",
        installer_image_sha256="a"*64,
        switch_name=EXPECTED_SWITCH,
        vcpu=2,memory_mb=4096,disk_gib=60,duration_minutes=60,
        created_at=NOW,expires_at=NOW+timedelta(minutes=15),
    )
    data.update(overrides)
    return WorkshopProvisionPlan(**data)


def host_data():
    return {
        "Platform":"Hyper-V","HypervisorAvailable":True,
        "WindowsHostVersion":"10.0.20348",
        "ObservedAtUtc":NOW.isoformat(),
        "LogicalProcessors":16,"FreeMemoryMB":32768,
        "TotalMemoryMB":65536,
        "Drives":[{"Drive":"D:","FreeBytes":200*(1024**3)}],
        "Machines":[
            {"Name":"Sofia","State":"Running","AssignedBytes":8192*1024**2},
            {"Name":"Hestia","State":"Running","AssignedBytes":4096*1024**2},
            {"Name":"Eos","State":"Running","AssignedBytes":4096*1024**2},
        ],
        "Switches":[{"Name":"Default Switch","SwitchType":"Internal"}],
    }


def observed():
    return observed_hyperv_host(
        payload=host_data(),authenticated_fleet_host_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",image_sha256="a"*64,
    )


def test_exact_host_observation_stays_readonly_and_does_not_guess_resources():
    seen=[]
    adapter=HyperVAdapter(runner=lambda command:(
        seen.append(command) or json.dumps(host_data())
    ))
    result=adapter.workshop_host()
    assert result["LogicalProcessors"]==16
    assert len(seen)==1
    for fragment in ("Get-VMHost","Get-VM","Get-VMSwitch","Get-CimInstance"):
        assert fragment in seen[0]
    for forbidden in ("New-VM","New-VMSwitch","Set-VM","Start-VM","Remove-VM"):
        assert forbidden not in seen[0]
    known=observed()
    assert known.hypervisor_version=="WindowsHyperV/10.0.20348"
    assert known.free_disk_gib==200
    assert known.existing_vm_names==("Sofia","Hestia","Eos")


def test_plan_digest_stable_and_preview_cannot_actuate_even_when_eligible():
    proposal=plan()
    assert proposal.fingerprint_sha256==plan().fingerprint_sha256
    decision=inspect_workshop_plan(proposal,observed(),at=NOW)
    assert decision.review_eligible
    assert not decision.blockers
    assert decision.may_provision is False


@pytest.mark.parametrize("override",[
    {"guest_name":"Sofia"},
    {"guest_name":"Artemis"},
    {"switch_name":"Default Switch"},
    {"network_mode":"external"},
    {"hypervisor":"Proxmox"},
    {"firmware_generation":1},
    {"vm_root":r"\\network\shared\Hephaestus"},
    {"vm_root":r"D:\SofiaLab\..\Artemis"},
    {"vcpu":64},
    {"memory_mb":100000},
    {"disk_gib":2000},
    {"installer_image_sha256":"unverified"},
    {"expires_at":NOW+timedelta(days=1)},
])
def test_unreviewed_host_mutation_scope_never_becomes_a_plan(override):
    with pytest.raises(ValueError):
        plan(**override)


def test_missing_capacity_image_collision_and_external_switch_all_block():
    base=host_data()
    base["Drives"]=[]
    base["Machines"].append({"Name":"Hephaestus","State":"Off","AssignedBytes":0})
    base["Switches"].append({
        "Name":EXPECTED_SWITCH,"SwitchType":"External",
    })
    base["FreeMemoryMB"]=1
    obs=observed_hyperv_host(
        payload=base,authenticated_fleet_host_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",
    )
    review=inspect_workshop_plan(plan(),obs,at=NOW)
    assert not review.review_eligible
    assert not review.may_provision
    issues=";".join(review.blockers)
    assert "RAM" in issues
    assert "disk" in issues
    assert "collision" in issues
    assert "non-private" in issues
    assert "hash" in issues


def test_pin_mtls_remote_node_and_preserve_missing_image_hash_as_unknown():
    service=object.__new__(RemoteFleetToolService)
    calls=[]
    def invoke(node_id,capability,operation,parameters):
        calls.append((node_id,capability,operation,parameters))
        return {
            "node_id":NODE,
            "outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps(host_data()),
        }
    service.invoke=invoke
    preview=preview_owner_hephaestus_plan(
        remote_service=service,artemis_node_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",
        installer_image_path=r"E:\ApprovedImages\debian-12.vhdx",
        installer_image_sha256="a"*64,at=NOW,
    )
    assert calls==[
        (NODE,"workshop.inspect","host",{}),
        (NODE,"workshop.inspect","media",{
            "image_path":r"E:\ApprovedImages\debian-12.vhdx",
        }),
    ]
    assert preview.plan.hypervisor_version=="WindowsHyperV/10.0.20348"
    assert preview.plan.memory_mb==4096
    assert preview.plan.disk_gib==60
    assert preview.observation.image_sha256 is None
    assert "installer image hash has not been observed" in preview.readable()
    assert "May create VM: FALSE" in preview.readable()
    service.invoke=lambda *_:dict(
        node_id=str(uuid4()),
        outcome="reported_success",
        request_id=str(uuid4()),
        message=json.dumps(host_data()),
    )
    with pytest.raises(RuntimeError,match="not authenticated"):
        preview_owner_hephaestus_plan(
            remote_service=service,artemis_node_id=NODE,
            vm_root=r"D:\SofiaLab\Hephaestus",
            installer_image_path=r"E:\ApprovedImages\debian-12.vhdx",
            installer_image_sha256="a"*64,at=NOW,
        )


def test_wrong_authenticated_node_and_stale_host_disallow_preflight():
    good=plan()
    mismatched=replace(observed(),host_id=str(uuid4()))
    assert not inspect_workshop_plan(good,mismatched,at=NOW).review_eligible
    stale=replace(observed(),observed_at=NOW-timedelta(hours=1))
    assert not inspect_workshop_plan(good,stale,at=NOW).review_eligible
    assert not inspect_workshop_plan(good,None,at=NOW).review_eligible


def test_exact_installer_digest_inspection_is_read_only():
    commands=[]
    adapter=HyperVAdapter(runner=lambda cmd:(
        commands.append(cmd) or ("a"*64+"\n")
    ))
    assert adapter.workshop_image_sha256(
        r"E:\ApprovedImages\debian-12.vhdx",
    )=="a"*64
    assert len(commands)==1 and "Get-FileHash" in commands[0]
    assert "New-VM" not in commands[0]
    with pytest.raises(ValueError):
        adapter.workshop_image_sha256(r"\\server\admin\secrets.vhdx")


def test_host_pinned_media_hash_can_qualify_readonly_plan_but_never_execute():
    service=object.__new__(RemoteFleetToolService)
    def invoke(node_id,capability,operation,params):
        if (capability,operation)==("workshop.inspect","host"):
            body=host_data()
        elif (capability,operation)==("workshop.inspect","media"):
            assert params=={
                "image_path":r"E:\ApprovedImages\debian-12.vhdx",
            }
            body={"sha256":"a"*64,"bytes":4096,"kind":".vhdx"}
        else:
            raise PermissionError("unexpected remote capability")
        return {
            "node_id":NODE,
            "outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps(body),
        }
    service.invoke=invoke
    reviewed=preview_owner_hephaestus_plan(
        remote_service=service,artemis_node_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",
        installer_image_path=r"E:\ApprovedImages\debian-12.vhdx",
        installer_image_sha256="a"*64,at=NOW,
    )
    assert reviewed.observation.image_sha256=="a"*64
    assert reviewed.review.review_eligible is True
    assert reviewed.review.may_provision is False
    assert "May create VM: FALSE" in reviewed.readable()


def test_host_pinned_media_mismatch_blocks_workshop_creation():
    service=object.__new__(RemoteFleetToolService)
    service.invoke=lambda _,capability,operation,params: {
        "node_id":NODE,"outcome":"reported_success",
        "request_id":str(uuid4()),
        "message":json.dumps(
            host_data()
            if operation=="host"
            else {"sha256":"b"*64,"bytes":4096,"kind":".vhdx"}
        ),
    }
    result=preview_owner_hephaestus_plan(
        remote_service=service,artemis_node_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",
        installer_image_path=r"E:\ApprovedImages\debian-12.vhdx",
        installer_image_sha256="a"*64,at=NOW,
    )
    assert result.review.review_eligible is False
    assert "image digest differs" in ";".join(result.review.blockers)


def test_production_fleet_manifest_exposes_only_readonly_host_and_media_inspection():
    from sofia.distributed.authorization import remote_operation_is_read_only
    assert remote_operation_is_read_only("workshop.inspect","host")
    assert remote_operation_is_read_only("workshop.inspect","media")
    assert not remote_operation_is_read_only("workshop.vm","provision")
    assert not remote_operation_is_read_only("workshop.vm","quarantine")


def test_canonical_preview_is_model_readable_but_never_an_action_grant(tmp_path):
    from sofia.config.user_settings import RuntimeUserSettingsStore
    from sofia.ops.workshop_provision import (
        WorkshopPreflight, WorkshopRemotePreview, WorkshopPreviewStore,
    )
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    now=datetime.now(timezone.utc)
    drafted=plan(
        created_at=now,expires_at=now+timedelta(minutes=15),
    )
    observed_host=replace(observed(),observed_at=now)
    decision=inspect_workshop_plan(drafted,observed_host,at=now)
    preview=WorkshopRemotePreview(
        drafted,observed_host,decision,str(uuid4()),
    )
    cache=WorkshopPreviewStore(state)
    assert cache.read_model_brief()["status"]=="unobserved"
    cache.record(preview)
    cache.record(preview)
    brief=WorkshopPreviewStore(state).read_model_brief()
    assert brief["status"]=="observed_read_only"
    assert brief["vm"]=="Hephaestus"
    assert brief["hypervisor"]=="Hyper-V"
    assert brief["observed_host_free_memory_mb"]==32768
    assert brief["may_provision"] is False
    assert brief["plan_fingerprint_sha256"]==drafted.fingerprint_sha256
    assert "installer image hash" in "; ".join(brief["blockers"]) or brief["review_eligible"]
    assert brief["notes"].startswith("Not a SAFE grant")
    with pytest.raises(PermissionError,match="cannot be rewritten"):
        cache.record(replace(preview,fleet_request_id=str(uuid4())))


def test_ops_tool_uses_approved_canonical_preview_only():
    from sofia.ops.capability import OpsCapabilitySet, create_ops_tool_bindings
    from sofia.safe.permissions import PermissionLevel,capability_permission_policy

    assert capability_permission_policy("ops.workshop.preview").level is PermissionLevel.OBSERVE_READ
    capabilities=OpsCapabilitySet(service=object()).capabilities()
    assert any(item.name=="ops.workshop.preview" for item in capabilities)
    bindings=create_ops_tool_bindings()
    assert any(
        item.capability_name=="ops.workshop.preview"
        for item in bindings
    )
    assert not any(
        item.capability_name=="workshop.vm.provision"
        for item in bindings
    )


def test_host_capacity_unknown_and_unverified_image_are_not_successful_preflight():
    incomplete=host_data()
    incomplete["FreeMemoryMB"]=None
    incomplete["LogicalProcessors"]=None
    incomplete["Drives"]=[]
    obs=observed_hyperv_host(
        payload=incomplete,authenticated_fleet_host_id=NODE,
        vm_root=r"D:\SofiaLab\Hephaestus",
    )
    review=inspect_workshop_plan(plan(),obs,at=NOW)
    assert not review.review_eligible
    assert not review.may_provision
    messages=";".join(review.blockers)
    assert "unknown/insufficient" in messages
    assert "hash" in messages
