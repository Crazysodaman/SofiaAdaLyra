"""Source-only regression for user-created Hyper-V Hephaestus VM handoff.

Tests intentionally deferred until the owner verification campaign. These
fixtures invoke no Hyper-V commands or operating system installer.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.distributed.capability import RemoteFleetToolService
from sofia.integrations.hyperv import HyperVAdapter
from sofia.ops.workshop_handoff import (
    WorkshopBlankVMHandoff,
    WorkshopHandoffStore,
    inspect_blank_vm_handoff,
    observed_owner_vm,
    preview_owner_created_vm,
)

pytestmark=pytest.mark.pkg_ops
AT=datetime(2026,10,11,17,tzinfo=timezone.utc)
NODE=uuid4()
VM=uuid4()
DISK=r"D:\SofiaLab\Hephaestus\os.vhdx"
MEDIA=r"E:\ApprovedImages\debian-unattended.iso"
SHA="a"*64


def owner_handoff(**changes):
    values={
        "plan_id":"hephaestus:handoff:review001",
        "artemis_node_id":NODE,
        "hyperv_vm_id":VM,
        "expected_os_disk_path":DISK,
        "installer_iso_path":MEDIA,
        "installer_sha256":SHA,
        "approved_boot_media_sha256":SHA,
        "created_at":AT,
        "expires_at":AT+timedelta(minutes=15),
        "owner_declares_empty_disk":True,
    }
    values.update(changes)
    return WorkshopBlankVMHandoff(**values)


def vm_json(**changes):
    values={
        "VmId":str(VM),
        "Name":"Hephaestus",
        "Generation":2,
        "State":"Off",
        "Processors":2,
        "StartupMemoryBytes":4096*1024**2,
        "Disks":[{"Path":DISK,"Size":60*1024**3}],
        "NetworkAdapters":[{"Name":"Sofia-Hephaestus-Private","SwitchType":"Private"}],
        "DvdPaths":[],
        "SecureBoot":"Off",
        "SecureBootTemplate":"",
        "ObservedAtUtc":AT.isoformat(),
    }
    values.update(changes)
    return values


def test_blank_vm_handoff_checks_actual_guid_offline_disk_private_network_and_resources():
    plan=owner_handoff()
    observed=observed_owner_vm(vm_json())
    outcome=inspect_blank_vm_handoff(plan,observed,now=AT)
    assert outcome.ready_for_owner_bootstrap_review
    assert outcome.may_install is False
    assert outcome.may_enroll is False
    assert plan.existing_vm_only
    assert plan.may_modify_network is False
    assert observed.hyperv_vm_id==VM
    assert plan.fingerprint==owner_handoff().fingerprint


@pytest.mark.parametrize("payload,expected",[
    ({"VmId":str(uuid4())},"GUID"),
    ({"Name":"Sofia"},"exact Hephaestus"),
    ({"State":"Running"},"powered off"),
    ({"Generation":1},"Generation-2"),
    ({"Processors":7},"vCPU"),
    ({"StartupMemoryBytes":1024*1024**2},"RAM"),
    ({"Disks":[]},"OS disk"),
    ({"Disks":[{"Path":r"D:\Artemis\canonical.vhdx","Size":60*1024**3}]},"OS disk"),
    ({"NetworkAdapters":[{"Name":"Default Switch","SwitchType":"Internal"}]},"private"),
    ({"NetworkAdapters":[{"Name":"Hephaestus LAN","SwitchType":"External"}]},"private"),
    ({"DvdPaths":[MEDIA]},"DVD"),
    ({"SecureBoot":"On","SecureBootTemplate":"MicrosoftWindows"},"secure boot"),
])
def test_mismatched_existing_vm_cannot_be_claimed_as_installer_target(payload,expected):
    actual=observed_owner_vm(vm_json(**payload))
    review=inspect_blank_vm_handoff(owner_handoff(),actual,now=AT)
    assert review.ready_for_owner_bootstrap_review is False
    assert review.may_install is False
    assert expected.lower() in "; ".join(review.blockers).lower()


def test_empty_disk_is_owner_decision_not_silent_guest_format_permission():
    with pytest.raises(PermissionError,match="empty OS disk"):
        owner_handoff(owner_declares_empty_disk=False)
    with pytest.raises(PermissionError,match="only Hephaestus"):
        owner_handoff(guest_name="Sofia")
    with pytest.raises(PermissionError,match="separate"):
        owner_handoff(may_enroll_fleet=True)
    with pytest.raises(PermissionError,match="dedicated"):
        owner_handoff(switch_name="Default Switch")


def test_short_handoff_expiry_and_missing_disk_metadata_deny_bootstrap():
    review=inspect_blank_vm_handoff(
        owner_handoff(),observed_owner_vm(vm_json()),now=AT+timedelta(minutes=16),
    )
    assert not review.ready_for_owner_bootstrap_review
    assert review.may_install is False
    missing=observed_owner_vm(vm_json(
        Disks=[{"Path":DISK,"Size":None}],
    ))
    assert not inspect_blank_vm_handoff(owner_handoff(),missing,now=AT).ready_for_owner_bootstrap_review


def test_exact_observation_is_static_host_side_and_non_mutating():
    calls=[]
    adapter=HyperVAdapter(runner=lambda command:(
        calls.append(command) or json.dumps(vm_json())
    ))
    result=adapter.workshop_handoff_vm()
    assert result["VmId"]==str(VM)
    assert result["State"]=="Off"
    assert len(calls)==1
    for marker in ("Get-VM","Get-VHD","Get-VMNetworkAdapter","Get-VMSwitch","Get-VMFirmware"):
        assert marker in calls[0]
    for prohibited in ("New-VM ","New-VMSwitch","Set-VMDvdDrive","Start-VM","Set-VMFirmware"):
        assert prohibited not in calls[0]


def test_exact_fleet_observation_plus_digest_only_yields_owner_review_not_install():
    service=object.__new__(RemoteFleetToolService)
    calls=[]
    def invoke(node,capability,operation,args):
        calls.append((node,capability,operation,args))
        if operation=="blank_vm":
            payload=vm_json()
        elif operation=="media":
            payload={"sha256":SHA,"bytes":500_000_000,"kind":".iso"}
        else:
            raise RuntimeError("unexpected operation")
        return {
            "node_id":str(NODE),
            "outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps(payload),
        }
    service.invoke=invoke
    preview=preview_owner_created_vm(
        remote_service=service,
        artemis_node_id=str(NODE),exact_vm_id=str(VM),
        disk_path=DISK,boot_media_path=MEDIA,boot_media_sha256=SHA,
        owner_confirms_blank_disk=True,at=AT,
    )
    assert [item[2] for item in calls]==["blank_vm","media"]
    assert preview.review.ready_for_owner_bootstrap_review
    assert not preview.review.may_install
    assert not preview.review.may_enroll
    assert "May install now: FALSE" in preview.readable()
    assert "OS installed: UNKNOWN" in preview.readable()


def test_missing_mismatched_or_wrong_host_signed_media_never_passes_review():
    service=object.__new__(RemoteFleetToolService)
    def invoke(node,capability,operation,args):
        body=vm_json() if operation=="blank_vm" else {"sha256":"b"*64}
        return {
            "node_id":str(NODE),
            "outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps(body),
        }
    service.invoke=invoke
    kwargs=dict(
        remote_service=service,artemis_node_id=str(NODE),
        exact_vm_id=str(VM),disk_path=DISK,
        boot_media_path=MEDIA,boot_media_sha256=SHA,
        owner_confirms_blank_disk=True,at=AT,
    )
    outcome=preview_owner_created_vm(**kwargs)
    assert not outcome.review.ready_for_owner_bootstrap_review
    assert "SHA-256" in " ".join(outcome.review.blockers)
    service.invoke=lambda *args: {
        "node_id":str(uuid4()),"outcome":"reported_success",
        "request_id":str(uuid4()),"message":json.dumps(vm_json()),
    }
    with pytest.raises(RuntimeError,match="unavailable"):
        preview_owner_created_vm(**kwargs)


def test_canonical_handoff_store_is_read_only_and_does_not_confer_authority(tmp_path):
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    service=object.__new__(RemoteFleetToolService)
    service.invoke=lambda node,cap,op,parameters: {
        "node_id":str(NODE),"outcome":"reported_success",
        "request_id":str(uuid4()),
        "message":json.dumps(
            vm_json() if op=="blank_vm"
            else {"sha256":SHA,"bytes":5000,"kind":".iso"}
        ),
    }
    now=datetime.now(timezone.utc)
    updated=vm_json(ObservedAtUtc=now.isoformat())
    def refreshed(node,cap,op,parameters):
        return {
            "node_id":str(NODE),"outcome":"reported_success",
            "request_id":str(uuid4()),
            "message":json.dumps(
                updated if op=="blank_vm"
                else {"sha256":SHA,"bytes":5000,"kind":".iso"}
            ),
        }
    service.invoke=refreshed
    reviewed=preview_owner_created_vm(
        remote_service=service,artemis_node_id=str(NODE),
        exact_vm_id=str(VM),disk_path=DISK,
        boot_media_path=MEDIA,boot_media_sha256=SHA,
        owner_confirms_blank_disk=True,at=now,
    )
    store=WorkshopHandoffStore(state)
    store.record(reviewed)
    store.record(reviewed)
    brief=store.read_model_brief()
    assert brief["status"]=="reviewed_read_only"
    assert brief["vm_guid"]==str(VM)
    assert brief["ready_for_bootstrap_review"] is True
    assert brief["may_install"] is False
    assert brief["may_enroll"] is False
    with pytest.raises(PermissionError,match="cannot be rewritten"):
        store.record(replace(reviewed,fleet_vm_receipt="fake:replaced"))


def test_hyperv_workshop_blank_read_permission_separate_from_bootstrap():
    from sofia.distributed.authorization import remote_operation_is_read_only
    from sofia.safe.permissions import capability_permission_policy,PermissionLevel
    assert remote_operation_is_read_only("workshop.inspect","blank_vm")
    assert capability_permission_policy("workshop.guest.bootstrap").level is PermissionLevel.PROTECTED
    assert capability_permission_policy("fleet.enroll").level is PermissionLevel.PROTECTED
    assert capability_permission_policy("permissions.grant").level is PermissionLevel.NEVER_SELF_AUTHORIZED
