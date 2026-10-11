"""Deferred option-B host-only Hyper-V Internal-link isolation contracts.

Tests consume synthetic host observations only. No Artemis commands are run.
"""
from datetime import datetime,timedelta,timezone
from dataclasses import replace
import pytest

from sofia.ops.workshop_network import (
    HOST_ADAPTER,HOST_ADDRESS,GUEST_ADDRESS,SWITCH_NAME,
    MODE,decode_host_internal_isolation,review_internal_network,
    guest_network_contract,
)
from sofia.ops.workshop_handoff import (
    WorkshopBlankVMHandoff,observed_owner_vm,inspect_blank_vm_handoff,
)
from sofia.integrations.hyperv import HyperVAdapter

AT=datetime(2026,10,11,18,tzinfo=timezone.utc)


def host_source(**changes):
    payload={
        "HostAdapter":HOST_ADAPTER,
        "HostIPv4Addresses":[{"IPAddress":HOST_ADDRESS,"PrefixLength":30}],
        "IPv4Forwarding":"Disabled","IPv6Forwarding":"Disabled",
        "DefaultRoutes":[],"DnsServers":[],"NatPrefixes":[],
        "IcsSharingEnabled":False,"OtherVmNames":[],
        "ObservedAtUtc":AT.isoformat(),
    }
    payload.update(changes)
    return payload


def test_owner_selected_internal_switch_is_only_host_guest_and_cannot_grant_guest_trust():
    contract=guest_network_contract()
    assert contract["network_mode"]==MODE
    assert contract["switch"]==SWITCH_NAME
    assert contract["host_ipv4"]=="172.30.250.1/30"
    assert contract["guest_ipv4"]=="172.30.250.2/30"
    assert contract["gateway"] is None
    assert contract["dns_servers"]==()
    assert contract["nat_enabled"] is False
    facts=decode_host_internal_isolation(host_source())
    status=review_internal_network(facts,now=AT)
    assert status.isolated_for_host_guest
    assert status.may_route_to_lan is False
    assert status.may_modify_host_network is False
    assert status.may_grant_guest_fleet_trust is False


@pytest.mark.parametrize("facts,expected",[
    ({"HostAdapter":"vEthernet (Default Switch)"},"identity"),
    ({"HostIPv4Addresses":[]},"172.30.250.1/30"),
    ({"HostIPv4Addresses":[{"IPAddress":"172.30.250.33","PrefixLength":24}]},"172.30.250.1/30"),
    ({"IPv4Forwarding":"Enabled"},"IPv4"),
    ({"IPv6Forwarding":"Enabled"},"IPv6"),
    ({"DefaultRoutes":["0.0.0.0/0"]},"default route"),
    ({"DnsServers":["1.1.1.1"]},"DNS"),
    ({"IcsSharingEnabled":True},"Internet Connection Sharing"),
    ({"NatPrefixes":["172.30.250.0/24"]},"WinNAT"),
    ({"NatPrefixes":["172.30.250.0/30"]},"WinNAT"),
    ({"OtherVmNames":["Sofia"]},"other VMs"),
    ({"ObservedAtUtc":(AT-timedelta(minutes=4)).isoformat()},"stale"),
])
def test_isolation_fails_on_route_leak_or_unverified_host_facts(facts,expected):
    result=review_internal_network(
        decode_host_internal_isolation(host_source(**facts)),now=AT,
    )
    assert not result.isolated_for_host_guest
    assert expected.casefold() in ";".join(result.blockers).casefold()


def test_unrelated_nat_network_does_not_falsely_invalidate_dedicated_link():
    found=review_internal_network(
        decode_host_internal_isolation(host_source(
            NatPrefixes=["10.0.0.0/8","192.168.0.0/16"],
        )),
        now=AT,
    )
    assert found.isolated_for_host_guest


@pytest.mark.parametrize("bad",[
    {"HostAdapter":HOST_ADAPTER},
    host_source(IcsSharingEnabled=None),
    host_source(NatPrefixes="not-a-list"),
    host_source(HostIPv4Addresses=[{"IPAddress":"bad"}]),
])
def test_incomplete_or_unobservable_host_isolation_cannot_be_presented_as_safe(bad):
    with pytest.raises((ValueError,TypeError)):
        decode_host_internal_isolation(bad)


def test_host_inspection_never_converts_internal_switch_into_network_permission():
    calls=[]
    import json
    result={
        "Name":"Hephaestus","VmId":"4106fcd6-784d-4479-9255-1db81c5fe281",
        "Generation":2,"State":"Off","Processors":2,
        "StartupMemoryBytes":4*1024**3,
        "Disks":[{"Path":r"D:\SofiaLab\Hephaestus\os.vhdx","Size":60*1024**3}],
        "NetworkAdapters":[{"Name":SWITCH_NAME,"SwitchType":"Internal"}],
        "DvdPaths":[],"BootOrder":["HardDiskDrive"],
        "NetworkIsolation":host_source(),"SecureBoot":"Off",
        "SecureBootTemplate":"","ObservedAtUtc":AT.isoformat(),
    }
    adapter=HyperVAdapter(runner=lambda command:(
        calls.append(command) or json.dumps(result)
    ))
    observed=adapter.workshop_handoff_vm()
    assert observed["NetworkIsolation"]["IPv4Forwarding"]=="Disabled"
    assert observed["NetworkIsolation"]["IcsSharingEnabled"] is False
    assert len(calls)==1
    command=calls[0]
    for value in (
        "Get-NetIPAddress","Get-NetIPInterface","Get-NetNat",
        "Get-NetRoute","Get-DnsClientServerAddress",
        "HNetCfg.HNetShare","Get-VMNetworkAdapter -All",
    ):
        assert value in command
    for forbidden in ("New-VMSwitch","Connect-VMNetworkAdapter","Set-NetIPAddress"):
        assert forbidden not in command


def test_host_power_on_script_rechecks_ip_route_ics_and_nat_before_dvd_mutations():
    import json
    from uuid import UUID
    calls=[]
    vm_id="4106fcd6-784d-4479-9255-1db81c5fe281"
    adapter=HyperVAdapter(runner=lambda cmd:(
        calls.append(cmd) or json.dumps({
            "VmId":vm_id,"Name":"Hephaestus","Outcome":"installer_boot_started",
            "State":"Running","MediaSha256":"a"*64,
            "OsInstalled":False,"FleetEnrolled":False,
        })
    ))
    adapter.bootstrap_existing_hephaestus(
        vm_id=vm_id,os_disk_path=r"D:\SofiaLab\Hephaestus\os.vhdx",
        iso_path=r"E:\ApprovedImages\debian-offline.iso",
        iso_sha256="a"*64,
    )
    assert len(calls)==1
    script=calls[0]
    for flag in (
        "Get-NetIPInterface","Get-NetNat","Get-NetRoute",
        "HNetCfg.HNetShare","HOST_IP_FORWARDING_ENABLED",
        "NAT_COVERS_WORKSHOP_SUBNET","OTHER_GUESTS_ON_INTERNAL_SWITCH",
        "Start-VM",
    ):
        assert flag in script
    assert script.index("HOST_IP_FORWARDING_ENABLED")<script.index("Start-VM")
    assert "New-VMSwitch" not in script
    assert "Set-VMSwitch" not in script
