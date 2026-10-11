"""Deferred owner's existing Hyper-V VM -> Debian unattended installer contracts.

All host/remote calls are simulated. NEVER run as part of coding phase.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.distributed.capability import RemoteFleetToolService
from sofia.integrations.hyperv import HyperVAdapter
from sofia.ops.workshop_handoff import (
    WorkshopBlankVMHandoff, WorkshopHandoffPreview,
    WorkshopHandoffStore, inspect_blank_vm_handoff, observed_owner_vm,
)
from sofia.ops.workshop_guest_bootstrap import (
    WorkshopInstallerBootStore, reviewed_handoff_from_store,
    start_owner_approved_installer,
)
from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)

pytestmark=pytest.mark.pkg_ops
NODE=uuid4()
VM=uuid4()
DISK=r"D:\SofiaLab\Hephaestus\os.vhdx"
ISO=r"E:\ApprovedImages\debian-preseed-unattended.iso"
SHA="a"*64


def vm_facts(at):
    return {
        "VmId":str(VM),"Name":"Hephaestus","Generation":2,
        "State":"Off","Processors":2,"StartupMemoryBytes":4096*1024**2,
        "Disks":[{"Path":DISK,"Size":60*1024**3}],
        "NetworkAdapters":[
            {"Name":"Sofia-Hephaestus-Private","SwitchType":"Private"},
        ],
        "DvdPaths":[],"SecureBoot":"Off",
        "SecureBootTemplate":"",
        "BootOrder":["HardDiskDrive","NetworkAdapter"],
        "ObservedAtUtc":at.isoformat(),
    }


def reviewed_state(tmp_path):
    at=datetime.now(timezone.utc)
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    plan=WorkshopBlankVMHandoff(
        plan_id="hephaestus:handoff:"+uuid4().hex,
        artemis_node_id=NODE,hyperv_vm_id=VM,
        expected_os_disk_path=DISK,installer_iso_path=ISO,
        installer_sha256=SHA,approved_boot_media_sha256=SHA,
        owner_declares_empty_disk=True,
        created_at=at,expires_at=at+timedelta(minutes=15),
    )
    observed=observed_owner_vm(vm_facts(at))
    review=inspect_blank_vm_handoff(plan,observed,now=at)
    assert review.ready_for_owner_bootstrap_review
    preview=WorkshopHandoffPreview(
        handoff=plan,observation=observed,review=review,
        observed_boot_sha256=SHA,
        fleet_vm_receipt="fixture:vm",
        fleet_media_receipt="fixture:iso",
    )
    WorkshopHandoffStore(state).record(preview)
    params={
        "artemis_node_id":str(NODE),
        "vm_id":str(VM),
        "disk_path":DISK,
        "iso_path":ISO,
        "iso_sha256":SHA,
        "handoff_fingerprint":plan.fingerprint,
    }
    approval=ExecutionApproval(
        approval_id=str(uuid4()),
        capability="workshop.guest.bootstrap",
        request_fingerprint=execution_fingerprint(
            "workshop.guest.bootstrap",params,
        ),
        approved_by="Sparks",approved_at=at,
        expires_at=at+timedelta(minutes=10),
    )
    ExecutionApprovalVerifier(state).record(approval)
    return state,plan,approval,at,params


def fake_service(state,at,*,result="reported_success",mutated=False,
                 fail_after_dispatch=False):
    remote=object.__new__(RemoteFleetToolService)
    observed=vm_facts(at)
    if mutated:
        observed["NetworkAdapters"][0]["SwitchType"]="External"
    calls=[]
    def invoke(node,capability,operation,params):
        calls.append((node,capability,operation,params))
        if capability=="workshop.inspect" and operation=="blank_vm":
            return {
                "node_id":str(NODE),"outcome":"reported_success",
                "request_id":str(uuid4()),"message":json.dumps(observed),
            }
        if capability=="workshop.inspect" and operation=="media":
            return {
                "node_id":str(NODE),"outcome":"reported_success",
                "request_id":str(uuid4()),
                "message":json.dumps({"sha256":SHA,"kind":".iso"}),
            }
        if capability=="workshop.bootstrap" and operation=="start":
            # The production RemoteFleetToolService.invoke does this guard,
            # not the agent or an LLM-provided model approval.
            ExecutionApprovalVerifier(state).consume(
                approval_id=params["approval_id"],
                capability="workshop.guest.bootstrap",
                parameters={
                    "artemis_node_id":node,
                    "vm_id":params["vm_id"],
                    "disk_path":params["disk_path"],
                    "iso_path":params["iso_path"],
                    "iso_sha256":params["iso_sha256"],
                    "handoff_fingerprint":params["handoff_fingerprint"],
                },
                now=at+timedelta(seconds=2),
            )
            if fail_after_dispatch:
                raise TimeoutError("Hyper-V remote outcome unknown")
            return {
                "node_id":str(NODE),"outcome":result,
                "request_id":str(uuid4()),
                "message":json.dumps({
                    "VmId":str(VM),"Name":"Hephaestus",
                    "Outcome":"installer_boot_started",
                    "MediaSha256":SHA,"OsInstalled":False,
                    "FleetEnrolled":False,"State":"Running",
                }),
            }
        raise AssertionError("unexpected remote capability")
    remote.invoke=invoke
    return remote,calls


def test_owner_approved_debian_boot_receipt_is_not_installed_or_enrolled(tmp_path):
    state,plan,approval,at,params=reviewed_state(tmp_path)
    remote,calls=fake_service(state,at)
    done=start_owner_approved_installer(
        state_path=state,remote_service=remote,
        plan_id=plan.plan_id,approval_id=approval.approval_id,
        now=at+timedelta(seconds=2),
    )
    assert [c[2] for c in calls]==["blank_vm","media","start"]
    assert done.status=="INSTALLER_BOOT_STARTED"
    assert done.exact_vm_id==str(VM)
    assert done.observed_vm_state=="Running"
    assert done.os_installed is False
    assert done.fleet_enrolled is False
    assert not ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=approval.approval_id,
        capability="workshop.guest.bootstrap",
        parameters=params,
        now=at+timedelta(seconds=3),
    )
    saved=WorkshopInstallerBootStore(state).inspect(plan_id=plan.plan_id)
    assert saved.status=="INSTALLER_BOOT_STARTED"
    with pytest.raises(Exception):
        start_owner_approved_installer(
            state_path=state,remote_service=remote,
            plan_id=plan.plan_id,approval_id=approval.approval_id,
            now=at+timedelta(seconds=3),
        )


def test_changed_vm_private_network_blocks_before_consuming_owner_approval(tmp_path):
    state,plan,approval,at,params=reviewed_state(tmp_path)
    remote,calls=fake_service(state,at,mutated=True)
    with pytest.raises(PermissionError,match="no longer eligible"):
        start_owner_approved_installer(
            state_path=state,remote_service=remote,
            plan_id=plan.plan_id,approval_id=approval.approval_id,
            now=at+timedelta(seconds=1),
        )
    assert [c[2] for c in calls]==["blank_vm"]
    assert WorkshopInstallerBootStore(state).inspect(plan_id=plan.plan_id) is None
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=approval.approval_id,
        capability="workshop.guest.bootstrap",
        parameters=params,now=at+timedelta(seconds=2),
    )


def test_lost_host_receipt_is_uncertain_and_never_automatically_replayed(tmp_path):
    state,plan,approval,at,_=reviewed_state(tmp_path)
    remote,calls=fake_service(
        state,at,fail_after_dispatch=True,
    )
    done=start_owner_approved_installer(
        state_path=state,remote_service=remote,
        plan_id=plan.plan_id,approval_id=approval.approval_id,
        now=at+timedelta(seconds=2),
    )
    assert done.status=="UNCERTAIN"
    assert not done.os_installed
    assert [c[2] for c in calls].count("start")==1
    with pytest.raises(Exception):
        start_owner_approved_installer(
            state_path=state,remote_service=remote,
            plan_id=plan.plan_id,approval_id=approval.approval_id,
            now=at+timedelta(seconds=3),
        )
    assert [c[2] for c in calls].count("start")==1


def test_production_hyperv_boot_command_never_creates_vm_or_network():
    commands=[]
    response={
        "VmId":str(VM),"Name":"Hephaestus",
        "Outcome":"installer_boot_started","State":"Running",
        "MediaSha256":SHA,"OsInstalled":False,
        "FleetEnrolled":False,
    }
    adapter=HyperVAdapter(
        runner=lambda statement:commands.append(statement) or json.dumps(response),
    )
    receipt=adapter.bootstrap_existing_hephaestus(
        vm_id=str(VM),os_disk_path=DISK,iso_path=ISO,
        iso_sha256=SHA,
    )
    assert receipt["Outcome"]=="installer_boot_started"
    assert len(commands)==1
    command=commands[0]
    for required in (
        "Get-VM -Name 'Hephaestus'",
        "Get-VMHardDiskDrive","Get-VHD","Get-VMSwitch",
        "Get-FileHash","Set-VMFirmware","Start-VM",
        "VM_GUID_MISMATCH","NOT_PRIVATE_SWITCH",
    ):
        assert required in command
    for forbidden in (
        "New-VM ","New-VMSwitch","Connect-VMNetworkAdapter",
        "Set-VMNetworkAdapter","Remove-VM ","Stop-VM ",
        "Copy-Item ","Invoke-Expression",
    ):
        assert forbidden not in command


@pytest.mark.parametrize("kwargs",[
    {"vm_id":"not-a-guid"},
    {"os_disk_path":r"C:\Somewhere\guest.exe"},
    {"iso_path":r"\\server\share\untrusted.iso"},
    {"iso_sha256":"unsigned"},
])
def test_bootstrap_rejects_unreviewed_ids_disks_and_media(kwargs):
    values=dict(vm_id=str(VM),os_disk_path=DISK,iso_path=ISO,iso_sha256=SHA)
    values.update(kwargs)
    adapter=HyperVAdapter(
        runner=lambda _:pytest.fail("invalid input must never run PowerShell"),
    )
    with pytest.raises((ValueError,PermissionError)):
        adapter.bootstrap_existing_hephaestus(**values)


def test_replayed_or_missing_owner_approval_cannot_boot(tmp_path):
    state,plan,approval,at,_=reviewed_state(tmp_path)
    remote,calls=fake_service(state,at)
    with pytest.raises(PermissionError,match="unconsumed owner installer grant"):
        start_owner_approved_installer(
            state_path=state,remote_service=remote,
            plan_id=plan.plan_id,approval_id=str(uuid4()),
            now=at+timedelta(seconds=1),
        )
    assert not any(c[2]=="start" for c in calls)
    assert WorkshopInstallerBootStore(state).inspect(plan_id=plan.plan_id) is None



def test_host_side_installer_status_is_observed_without_claiming_debian_installed():
    from sofia.ops.workshop_guest_bootstrap import inspect_existing_vm_installer
    commands=[]
    result={
        "VmId":str(VM),"Name":"Hephaestus","Generation":2,
        "State":"Running","Media":[ISO],
        "Services":[{"Name":"Heartbeat","Enabled":True,"PrimaryStatus":"OK"}],
        "BootOrder":["DVDDrive","HardDiskDrive"],
        "ObservedAtUtc":datetime.now(timezone.utc).isoformat(),
        "OsInstalled":None,"FleetEnrolled":None,
    }
    adapter=HyperVAdapter(runner=lambda command:(
        commands.append(command) or json.dumps(result)
    ))
    observed=adapter.workshop_installer_status()
    assert observed["OsInstalled"] is None
    assert observed["FleetEnrolled"] is None
    assert observed["State"]=="Running"
    assert len(commands)==1
    assert "Get-VMIntegrationService" in commands[0]
    for forbidden in ("Set-VMDvdDrive","New-VM ","Start-VM ","Set-VMFirmware"):
        assert forbidden not in commands[0]


def test_postboot_observation_preserves_unknown_guest_os_and_private_receipt(tmp_path):
    from sofia.ops.workshop_guest_bootstrap import inspect_existing_vm_installer
    state,plan,approval,at,_=reviewed_state(tmp_path)
    service,calls=fake_service(state,at)
    receipt=start_owner_approved_installer(
        state_path=state,remote_service=service,
        plan_id=plan.plan_id,approval_id=approval.approval_id,
        now=at+timedelta(seconds=1),
    )
    assert receipt.status=="INSTALLER_BOOT_STARTED"
    timestamp=datetime.now(timezone.utc)
    def read_only_inspection(node,capability,operation,parameters):
        assert capability=="workshop.inspect" and operation=="installer_status"
        assert parameters=={}
        return {
            "node_id":str(NODE),"outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps({
                "Name":"Hephaestus","VmId":str(VM),
                "State":"Running","Media":[ISO],
                "Services":[{"Name":"Heartbeat","Enabled":False}],
                "BootOrder":["DVDDrive","HardDiskDrive"],
                "ObservedAtUtc":timestamp.isoformat(),
                "OsInstalled":None,"FleetEnrolled":None,
            }),
        }
    service.invoke=read_only_inspection
    observed=inspect_existing_vm_installer(
        state_path=state,remote_service=service,
        plan_id=plan.plan_id,now=timestamp+timedelta(seconds=1),
    )
    assert observed["host_power_state"]=="Running"
    assert observed["os_installed"]=="UNKNOWN"
    assert observed["guest_authenticated"]=="UNKNOWN"
    assert observed["fleet_enrolled"]=="UNKNOWN"
    import sqlite3
    with sqlite3.connect(state) as db:
        row=db.execute(
            "SELECT host_report_json FROM ops_workshop_installer_observation"
        ).fetchone()
    assert "UNKNOWN" in row[0]


def test_wrong_host_or_guest_vm_cannot_fake_installer_completion(tmp_path):
    from sofia.ops.workshop_guest_bootstrap import inspect_existing_vm_installer
    state,plan,approval,at,_=reviewed_state(tmp_path)
    service,_=fake_service(state,at)
    start_owner_approved_installer(
        state_path=state,remote_service=service,
        plan_id=plan.plan_id,approval_id=approval.approval_id,
        now=at+timedelta(seconds=1),
    )
    service.invoke=lambda *_a,**_kw:{
        "node_id":str(NODE),"outcome":"reported_success",
        "request_id":str(uuid4()),
        "message":json.dumps({
            "Name":"Hephaestus","VmId":str(uuid4()),"State":"Running",
            "ObservedAtUtc":datetime.now(timezone.utc).isoformat(),
            "OsInstalled":True,"FleetEnrolled":True,
        }),
    }
    with pytest.raises(PermissionError,match="VM identity"):
        inspect_existing_vm_installer(
            state_path=state,remote_service=service,
            plan_id=plan.plan_id,now=datetime.now(timezone.utc),
        )
