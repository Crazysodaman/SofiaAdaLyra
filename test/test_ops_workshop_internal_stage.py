"""Deferred live-route regression: host-only Artemis Internal switch creation.

Fixtures simulate Fleet and Hyper-V; no VM, network, installer or CI run.
"""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import json
import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.distributed.capability import RemoteFleetToolService
from sofia.integrations.hyperv import HyperVAdapter
from sofia.ops.workshop_network import network_policy_digest,SWITCH_NAME
from sofia.ops.workshop_network_stage import (
    WorkshopNetworkStageStore,stage_approved_internal_network,
)
from sofia.safe.execution_approval import (
    ExecutionApproval,ExecutionApprovalVerifier,execution_fingerprint,
)
from sofia.distributed.authorization import (
    remote_host_capability_name,remote_operation_is_read_only,
)
from sofia.safe.permissions import capability_permission_policy,PermissionLevel
from test.owner_auth_fixture import record_verified_owner_approval

NOW=datetime.now(timezone.utc)
NODE=uuid4()
VM=uuid4()


def approved_source(tmp_path):
    state=tmp_path/"sofia.db"
    RuntimeUserSettingsStore(state).load()
    scope={
        "artemis_node_id":str(NODE),
        "vm_id":str(VM),
        "network_policy_digest":network_policy_digest(),
    }
    approval=ExecutionApproval(
        approval_id=str(uuid4()),
        capability="workshop.network.create",
        request_fingerprint=execution_fingerprint(
            "workshop.network.create",scope,
        ),
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW+timedelta(minutes=10),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(state), approval,
    )
    return state,approval,scope


def fake_fleet(state,scope,*,remote_timeout=False):
    service=object.__new__(RemoteFleetToolService)
    calls=[]
    def invoke(node,cap,operation,payload):
        calls.append((node,cap,operation,payload))
        assert node==str(NODE)
        assert cap=="workshop.network" and operation=="stage"
        assert payload["vm_id"]==scope["vm_id"]
        assert payload["network_policy_digest"]==scope["network_policy_digest"]
        ExecutionApprovalVerifier(state).consume(
            approval_id=payload["approval_id"],
            capability="workshop.network.create",
            parameters=scope,now=datetime.now(timezone.utc),
        )
        if remote_timeout:
            raise TimeoutError("Hyper-V network stage outcome is unknown")
        return {
            "node_id":str(NODE),
            "request_id":str(uuid4()),
            "outcome":"reported_success",
            "message":json.dumps({
                "VmId":str(VM),"VmState":"Off",
                "Outcome":"host_internal_link_staged",
                "SwitchName":SWITCH_NAME,"SwitchType":"Internal",
                "HostIPv4":"172.30.250.1/30",
                "GuestIPv4":"172.30.250.2/30",
                "NatEnabled":False,"GuestConfigured":False,
                "ObservedAtUtc":datetime.now(timezone.utc).isoformat(),
            }),
        }
    service.invoke=invoke
    return service,calls


def test_one_use_owner_authority_stages_only_exact_existing_vm(tmp_path):
    state,approval,scope=approved_source(tmp_path)
    fleet,calls=fake_fleet(state,scope)
    receipt=stage_approved_internal_network(
        state_path=state,service=fleet,
        artemis_node_id=str(NODE),hyperv_vm_id=str(VM),
        approval_id=approval.approval_id,at=NOW,
    )
    assert receipt.status=="HOST_STAGE_REPORTED"
    assert receipt.guest_configured is False
    assert receipt.lan_access_verified is False
    assert receipt.guest_enrolled is False
    assert receipt.policy_sha256==network_policy_digest()
    assert len(calls)==1
    assert remote_host_capability_name(
        "workshop.network","stage",
    )=="workshop.network.create"
    assert remote_operation_is_read_only("workshop.network","stage") is False
    assert capability_permission_policy("workshop.network.create").level is PermissionLevel.PROTECTED
    with pytest.raises(PermissionError):
        stage_approved_internal_network(
            state_path=state,service=fleet,
            artemis_node_id=str(NODE),hyperv_vm_id=str(VM),
            approval_id=approval.approval_id,at=NOW+timedelta(seconds=2),
        )
    assert len(calls)==1


def test_unknown_network_state_is_uncertain_and_never_replayed(tmp_path):
    state,approval,scope=approved_source(tmp_path)
    fleet,calls=fake_fleet(state,scope,remote_timeout=True)
    receipt=stage_approved_internal_network(
        state_path=state,service=fleet,
        artemis_node_id=str(NODE),hyperv_vm_id=str(VM),
        approval_id=approval.approval_id,at=NOW,
    )
    assert receipt.status=="UNCERTAIN"
    assert len(calls)==1
    with pytest.raises(PermissionError):
        stage_approved_internal_network(
            state_path=state,service=fleet,
            artemis_node_id=str(NODE),hyperv_vm_id=str(VM),
            approval_id=approval.approval_id,at=NOW,
        )
    assert len(calls)==1


def test_host_power_shell_restricts_new_internal_switch_to_exact_guest():
    commands=[]
    adapter=HyperVAdapter(runner=lambda command:(
        commands.append(command) or json.dumps({
            "VmId":str(VM),"Outcome":"host_internal_link_staged",
            "VmState":"Off","SwitchName":SWITCH_NAME,
            "SwitchType":"Internal","HostIPv4":"172.30.250.1/30",
            "GuestIPv4":"172.30.250.2/30",
            "GuestConfigured":False,"NatEnabled":False,
        })
    ))
    observed=adapter.stage_hephaestus_internal_link(vm_id=str(VM))
    assert observed["GuestConfigured"] is False
    assert len(commands)==1
    command=commands[0]
    for expected in (
        "Get-VM -Name 'Hephaestus'",
        "VM_GUID_MISMATCH","EXISTING_OFF_GEN2_REQUIRED",
        "Sofia-Hephaestus-Internal",
        "NAT_OVERLAPS_GUEST_SUBNET",
        "EXISTING_ICS_SHARING_ACTIVE",
        "OTHER_GUESTS_ON_INTERNAL_SWITCH",
        "Get-NetIPInterface","Set-NetIPInterface",
        "New-VMSwitch","New-NetIPAddress",
        "Connect-VMNetworkAdapter",
    ):
        assert expected in command
    for prohibited in (
        "Set-VMSwitch -SwitchType External",
        "New-NetNat","New-VM ","Remove-VM","Stop-VM ",
        "Start-VM ","Enable-NetAdapterBinding",
        "Set-DnsClientServerAddress -ServerAddresses",
    ):
        assert prohibited not in command
    assert command.index("NAT_OVERLAPS_GUEST_SUBNET")<command.index("New-VMSwitch")
    assert command.index("STAGED_HOST_IP_NOT_EXACT") < command.index(
        "Connect-VMNetworkAdapter"
    )
    assert command.index("STAGED_HOST_FORWARDING_NOT_DISABLED") < command.index(
        "Connect-VMNetworkAdapter"
    )
    assert "Get-NetIPInterface -InterfaceAlias $alias" in command
    assert "Get-NetIPAddress -InterfaceAlias $alias" in command
    # Independently re-observe the same existing Gen2 VM, exact one NIC,
    # and actual switch type after the potential host mutation.
    for safeguard in (
        "POST_STAGE_VM_IDENTITY_OR_POWER_CHANGED",
        "POST_STAGE_NIC_IDENTITY_CHANGED",
        "POST_STAGE_SWITCH_NOT_INTERNAL",
    ):
        assert safeguard in command
        assert command.index("Connect-VMNetworkAdapter") < command.index(safeguard)
    assert "[string]$postVm.Id" in command
    assert "[string]$finalSwitch.SwitchType" in command


def test_stage_cannot_authorize_a_different_vm_or_unrecognized_policy(tmp_path):
    state,approval,scope=approved_source(tmp_path)
    fleet,calls=fake_fleet(state,scope)
    with pytest.raises(PermissionError,match="owner authorization"):
        stage_approved_internal_network(
            state_path=state,service=fleet,
            artemis_node_id=str(NODE),hyperv_vm_id=str(uuid4()),
            approval_id=approval.approval_id,at=NOW,
        )
    assert not calls
    from sofia.ops.workshop_network import guest_network_contract
    assert guest_network_contract()["nat_enabled"] is False
    assert len(network_policy_digest())==64


def test_original_vm_network_can_be_inspected_without_internal_switch_existing():
    commands=[]
    payload={
        "VmId":str(VM),"Name":"Hephaestus","State":"Off","Generation":2,
        "NicCount":1,
        "OriginalSwitchNames":["Sofia-Hephaestus-Private"],
        "OriginalSwitchTypes":["Private"],
        "TargetExists":False,"TargetType":"",
        "OtherVmNames":[],"NatPrefixes":[],"AddressCollision":False,
        "IcsSharingEnabled":False,
        "ObservedAtUtc":NOW.isoformat(),"HostChangePerformed":False,
    }
    provider=HyperVAdapter(runner=lambda statement:(
        commands.append(statement) or json.dumps(payload)
    ))
    observed=provider.workshop_internal_stage_preflight()
    assert observed["OriginalSwitchNames"]==["Sofia-Hephaestus-Private"]
    assert observed["TargetExists"] is False
    assert observed["HostChangePerformed"] is False
    assert len(commands)==1
    for expected in (
        "Get-VM -Name 'Hephaestus'",
        "Get-VMNetworkAdapter",
        "Get-VMSwitch","Get-NetNat","Get-NetIPAddress",
        "HNetCfg.HNetShare",
    ):
        assert expected in commands[0]
    for prohibited in (
        "New-VMSwitch","Connect-VMNetworkAdapter",
        "Set-NetIPInterface","New-NetIPAddress","Start-VM",
    ):
        assert prohibited not in commands[0]


def test_host_original_network_preflight_cannot_forge_stage_success():
    provider=HyperVAdapter(runner=lambda _cmd:json.dumps({
        "Name":"Hephaestus","VmId":str(VM),
        "HostChangePerformed":True,
    }))
    with pytest.raises(Exception,match="read-only"):
        provider.workshop_internal_stage_preflight()
    assert remote_operation_is_read_only(
        "workshop.inspect","network_stage_preflight",
    ) is True
