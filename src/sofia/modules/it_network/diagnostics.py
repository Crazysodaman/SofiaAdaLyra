"""MOD-IT-NETWORK: bounded interpretation of caller-supplied observations.

No sockets, subprocesses, state writes or discovery. The Platform authenticates
sources and authorizes calls before invoking this advisory capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address, ip_interface
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-NETWORK"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.network.interpret_snapshot.v1"
OPERATION_PROFILE = "OBSERVE"
RESOURCE_REQUIREMENTS = {"cpu_millicores": 50, "ram_mib": 32, "gpu_mib": 0}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_LINK = frozenset({"up", "down", "unknown"})
_DNS = frozenset({"NOERROR", "NXDOMAIN", "SERVFAIL", "TIMEOUT", "UNKNOWN"})
_TCP = frozenset({"success", "timeout", "refused", "unreachable", "unknown"})
_FIELDS = frozenset({"source_ref", "observed_at", "link_state", "address_cidr", "default_gateway", "dns_rcode", "tcp_result"})


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("observed_at must be an ISO timestamp")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    return moment.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class NetworkFinding:
    code: str
    severity: str
    next_check: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "next_check": self.next_check}


@dataclass(frozen=True, slots=True)
class NetworkReport:
    source_ref: str
    observed_at: datetime
    freshness: str
    assessment: str
    findings: tuple[NetworkFinding, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "sofia.it.network.report.v1",
            "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "module_id": MODULE_ID,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at.isoformat(),
            "freshness": self.freshness,
            "assessment": self.assessment,
            "findings": [finding.as_dict() for finding in self.findings],
            "evidence_class": "supplied_unverified",
            "effect": "none",
        }


def interpret_snapshot(snapshot: Mapping[str, object], *, now: datetime, max_age_seconds: int = 300) -> NetworkReport:
    """Interpret a single, explicitly scoped snapshot, never gather live data."""
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError("network snapshot requires exactly the versioned fields")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("max_age_seconds out of bounds")
    source = snapshot["source_ref"]
    if not isinstance(source, str) or _ID.fullmatch(source) is None:
        raise ValueError("source_ref must be bounded")
    observed = _timestamp(snapshot["observed_at"])
    for field, allowed in (("link_state", _LINK), ("dns_rcode", _DNS), ("tcp_result", _TCP)):
        if not isinstance(snapshot[field], str) or snapshot[field] not in allowed:
            raise ValueError(f"invalid {field}")
    address = snapshot["address_cidr"]
    gateway = snapshot["default_gateway"]
    if address is not None:
        if not isinstance(address, str) or len(address) > 50:
            raise ValueError("invalid address_cidr")
        try:
            address = ip_interface(address)
        except ValueError as exc:
            raise ValueError("invalid address_cidr") from exc
    if gateway is not None:
        if not isinstance(gateway, str) or len(gateway) > 50:
            raise ValueError("invalid default_gateway")
        try:
            gateway = ip_address(gateway)
        except ValueError as exc:
            raise ValueError("invalid default_gateway") from exc
        if address is not None and address.version != gateway.version:
            raise ValueError("gateway and interface address families differ")
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    if age < -5:
        return NetworkReport(source, observed, "future", "unknown", (
            NetworkFinding("future_timestamp", "warning", "Check source clock and observation provenance."),
        ))
    if age > max_age_seconds:
        return NetworkReport(source, observed, "stale", "unknown", (
            NetworkFinding("stale_observation", "warning", "Request a newly authorized observation."),
        ))
    findings: list[NetworkFinding] = []
    if snapshot["link_state"] == "down":
        findings.append(NetworkFinding("link_down", "critical", "Inspect approved interface and physical link observations."))
    if address is None and snapshot["link_state"] == "up":
        findings.append(NetworkFinding("address_missing", "warning", "Check approved address assignment observations."))
    if address is not None and gateway is not None and gateway not in address.network:
        findings.append(NetworkFinding("gateway_outside_subnet", "warning", "Review on-link routes before changing configuration."))
    if snapshot["dns_rcode"] == "SERVFAIL":
        findings.append(NetworkFinding("dns_servfail", "warning", "Compare scoped resolver health and upstream answers."))
    elif snapshot["dns_rcode"] == "TIMEOUT":
        findings.append(NetworkFinding("dns_timeout", "warning", "Inspect approved DNS reachability observations."))
    elif snapshot["dns_rcode"] == "NXDOMAIN":
        findings.append(NetworkFinding("dns_name_not_found", "info", "Check the queried name; NXDOMAIN alone does not prove DNS failure."))
    if snapshot["tcp_result"] in {"timeout", "refused", "unreachable"}:
        result = snapshot["tcp_result"]
        findings.append(NetworkFinding(f"tcp_{result}", "warning", "Compare an authorized endpoint/service observation."))
    known = (snapshot["link_state"] != "unknown" or snapshot["dns_rcode"] != "UNKNOWN" or snapshot["tcp_result"] != "unknown" or address is not None)
    if not known:
        findings.append(NetworkFinding("insufficient_evidence", "info", "Provide a scoped, current interface or query observation."))
        assessment = "unknown"
    else:
        assessment = "degraded" if any(item.severity in {"critical", "warning"} for item in findings) else "no_fault_observed"
    return NetworkReport(source, observed, "fresh", assessment, tuple(findings))


def capability_registrations() -> tuple[tuple[Capability, object], ...]:
    """Inert registration data. Platform's existing gateway enforces authority."""
    capability = Capability(CAPABILITY_ID, "Interpret one approved network snapshot, without probing or writes.")

    def handler(request: CapabilityRequest) -> dict[str, object]:
        if request.capability != capability:
            raise ValueError("capability mismatch")
        params = request.parameters
        if set(params) != {"snapshot"}:
            raise ValueError("expected only snapshot")
        return interpret_snapshot(params["snapshot"], now=datetime.now(timezone.utc)).as_dict()

    return ((capability, handler),)
