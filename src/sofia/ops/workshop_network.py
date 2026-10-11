"""Option B: exact Hyper-V Internal switch, isolated host-to-guest /30.

An Internal Hyper-V switch is NOT automatically isolated. Host-observed
address/forwarding/NAT/ICS/routing and sibling-VM evidence is mandatory.
Review alone never reconfigures an Artemis NIC, VM, firewall or switch.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from ipaddress import ip_address, ip_network
from typing import Any

SWITCH_NAME="Sofia-Hephaestus-Internal"
HOST_ADAPTER=f"vEthernet ({SWITCH_NAME})"
HOST_ADDRESS="172.30.250.1"
GUEST_ADDRESS="172.30.250.2"
PREFIX_LENGTH=30
ISOLATED_SUBNET=ip_network("172.30.250.0/30")
GUEST_DEFAULT_GATEWAY=None
GUEST_DNS_SERVERS=()
MODE="internal_host_guest_no_lan"


@dataclass(frozen=True,slots=True)
class HostInternalIsolation:
    host_adapter:str
    host_ipv4_addresses:tuple[tuple[str,int],...]
    ipv4_forwarding:str
    ipv6_forwarding:str
    default_routes:tuple[str,...]
    dns_servers:tuple[str,...]
    nat_prefixes:tuple[str,...]
    ics_sharing_enabled:bool|None
    other_vm_names:tuple[str,...]
    observed_at:datetime

    def __post_init__(self):
        if not isinstance(self.observed_at,datetime) or (
            self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None
        ):
            raise ValueError("aware host isolation observation required")
        for items in (
            self.host_ipv4_addresses,self.default_routes,self.dns_servers,
            self.nat_prefixes,self.other_vm_names,
        ):
            if not isinstance(items,tuple) or len(items)>64:
                raise ValueError("bounded host internal network observation required")


@dataclass(frozen=True,slots=True)
class InternalNetworkReview:
    isolated_for_host_guest:bool
    blockers:tuple[str,...]
    may_route_to_lan:bool=False
    may_grant_guest_fleet_trust:bool=False
    may_modify_host_network:bool=False


def decode_host_internal_isolation(payload:Any)->HostInternalIsolation:
    if not isinstance(payload,dict):
        raise ValueError("missing actual Artemis host isolation observation")
    fields=("HostAdapter","HostIPv4Addresses","IPv4Forwarding",
            "IPv6Forwarding","DefaultRoutes","DnsServers","NatPrefixes",
            "IcsSharingEnabled","OtherVmNames","ObservedAtUtc")
    if any(k not in payload for k in fields):
        raise ValueError("incomplete host IP, forwarding, NAT or ICS proof")
    try:
        addr=tuple(
            (str(row["IPAddress"]),int(row["PrefixLength"]))
            for row in payload["HostIPv4Addresses"]
        )
        at=datetime.fromisoformat(
            str(payload["ObservedAtUtc"]).replace("Z","+00:00")
        )
    except (TypeError,KeyError,ValueError) as exc:
        raise ValueError("invalid source-observed host IPv4 CIDR evidence") from exc
    if type(payload["IcsSharingEnabled"]) is not bool:
        raise ValueError("unobserved Windows Internet Connection Sharing state")
    for key in ("DefaultRoutes","DnsServers","NatPrefixes","OtherVmNames"):
        if (
            not isinstance(payload[key],list)
            or len(payload[key])>64
            or any(not isinstance(v,str) for v in payload[key])
        ):
            raise ValueError("missing verified host routing/NAT/peer facts")
    return HostInternalIsolation(
        host_adapter=str(payload["HostAdapter"]),
        host_ipv4_addresses=addr,
        ipv4_forwarding=str(payload["IPv4Forwarding"]),
        ipv6_forwarding=str(payload["IPv6Forwarding"]),
        default_routes=tuple(payload["DefaultRoutes"]),
        dns_servers=tuple(payload["DnsServers"]),
        nat_prefixes=tuple(payload["NatPrefixes"]),
        ics_sharing_enabled=payload["IcsSharingEnabled"],
        other_vm_names=tuple(payload["OtherVmNames"]),
        observed_at=at,
    )


def review_internal_network(
    fact:HostInternalIsolation|None,*,now:datetime,
)->InternalNetworkReview:
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware source-comparison time required")
    issues=[]
    if fact is None:
        return InternalNetworkReview(False,(
            "Artemis Internal-switch network isolation not observed",
        ))
    if not isinstance(fact,HostInternalIsolation):
        raise TypeError("typed Artemis network observation required")
    if not timedelta(0)<=now-fact.observed_at<=timedelta(minutes=3):
        issues.append("Internal switch isolation observation stale or future")
    if fact.host_adapter!=HOST_ADAPTER:
        issues.append("dedicated host virtual Ethernet adapter identity mismatch")
    if fact.host_ipv4_addresses!=((HOST_ADDRESS,PREFIX_LENGTH),):
        issues.append("host must have only approved 172.30.250.1/30 static link address")
    if fact.ipv4_forwarding.casefold()!="disabled":
        issues.append("host IPv4 forwarding not explicitly disabled")
    if fact.ipv6_forwarding.casefold()!="disabled":
        issues.append("host IPv6 forwarding not explicitly disabled")
    if fact.default_routes:
        issues.append("isolated vEthernet adapter has default route/gateway")
    if fact.dns_servers:
        issues.append("isolated vEthernet adapter has DNS servers")
    if fact.ics_sharing_enabled is not False:
        issues.append("Internet Connection Sharing active or unknown")
    if fact.other_vm_names:
        issues.append("other VMs connected to dedicated workshop switch")
    for value in fact.nat_prefixes:
        try:
            subnet=ip_network(value,strict=False)
        except ValueError:
            issues.append("unparseable host NAT prefix")
            continue
        if subnet.version==4 and subnet.overlaps(ISOLATED_SUBNET):
            issues.append("WinNAT covers the isolated workshop subnet")
    return InternalNetworkReview(not issues,tuple(dict.fromkeys(issues)))


def guest_network_contract()->dict:
    return {
        "network_mode":MODE,
        "switch":SWITCH_NAME,
        "host_ipv4":f"{HOST_ADDRESS}/{PREFIX_LENGTH}",
        "guest_ipv4":f"{GUEST_ADDRESS}/{PREFIX_LENGTH}",
        "gateway":None,
        "dns_servers":(),
        "network_forwarding_enabled":False,
        "internet_connection_sharing_enabled":False,
        "nat_enabled":False,
        "physical_lan_access":"DENIED",
        "guest_os_installed":False,
        "may_modify_host_network":False,
    }


def network_policy_digest()->str:
    """Exact owner-reviewed Internal link contract for one-use SAFE approval."""
    import json
    from hashlib import sha256
    content=json.dumps(
        guest_network_contract(),sort_keys=True,separators=(",",":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(content).hexdigest()
