"""MOD-IT-HELPDESK: deterministic advisory triage of bounded ticket evidence.

A recommendation is an inert diagnostic plan, never an instruction or grant.
No vendor command, repair, network probe, external write or model call occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-HELPDESK"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.helpdesk.triage_evidence.v1"
OPERATION_PROFILE = "ADVISORY"
RESOURCE_REQUIREMENTS = {"cpu_millicores": 50, "ram_mib": 32, "gpu_mib": 0}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_SYMPTOMS = frozenset({"cannot_resolve_name", "cannot_connect", "service_down", "login_rejected", "disk_exhausted", "latency_high"})
_CODES = frozenset({"dns_servfail", "dns_timeout", "link_down", "auth_denied", "storage_full", "service_stopped", "connection_refused", "network_unreachable"})
_FIELDS = frozenset({"ticket_ref", "observed_at", "symptoms", "diagnostic_codes", "expected_network_source_ref"})
_RULES = (
    ("identity", frozenset({"auth_denied"}), "Confirm identity provider status and authentication audit evidence."),
    ("storage", frozenset({"storage_full"}), "Inspect authorized volume capacity and process logs; do not delete data."),
    ("name_resolution", frozenset({"dns_servfail", "dns_timeout"}), "Compare approved resolver and name-resolution measurements."),
    ("connectivity", frozenset({"link_down", "network_unreachable"}), "Check trusted link, route and endpoint evidence."),
    ("service_health", frozenset({"service_stopped", "connection_refused"}), "Inspect authorized service state and endpoint listeners."),
)
_SYMPTOM_CLASS = {"cannot_resolve_name": "name_resolution", "cannot_connect": "connectivity", "service_down": "service_health", "login_rejected": "identity", "disk_exhausted": "storage", "latency_high": "performance"}
_ADVICE = {**{name: plan for name, _, plan in _RULES}, "performance": "Compare scoped latency and resource samples over time.", "unknown": "Gather current authorized diagnostics before selecting a repair."}


def _observed(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("observed_at must be ISO timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("observed_at requires timezone")
    return result.astimezone(timezone.utc)


def _tokens(value: object, allowed: frozenset[str], label: str) -> frozenset[str]:
    if not isinstance(value, list) or len(value) > 12 or any(not isinstance(v, str) or v not in allowed for v in value):
        raise ValueError(f"invalid {label}")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate {label}")
    return frozenset(value)


@dataclass(frozen=True, slots=True)
class HelpdeskAssessment:
    ticket_ref: str
    observed_at: datetime
    freshness: str
    category: str
    confidence: str
    evidence_codes: tuple[str, ...]
    next_check: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "sofia.it.helpdesk.assessment.v1",
            "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "module_id": MODULE_ID,
            "ticket_ref": self.ticket_ref,
            "observed_at": self.observed_at.isoformat(),
            "freshness": self.freshness,
            "category": self.category,
            "confidence": self.confidence,
            "evidence_codes": list(self.evidence_codes),
            "next_check": self.next_check,
            "limitations": list(self.limitations),
            "evidence_class": "supplied_unverified",
            "effect": "none",
        }


def triage_evidence(ticket: Mapping[str, object], *, now: datetime, network_report: Mapping[str, object] | None = None, max_age_seconds: int = 300) -> HelpdeskAssessment:
    """Classify supplied reports only; fail closed for stale evidence or bad joins."""
    if not isinstance(ticket, Mapping) or set(ticket) != _FIELDS:
        raise ValueError("ticket must contain exactly versioned fields")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("max_age_seconds out of bounds")
    ticket_ref = ticket["ticket_ref"]
    expected_source = ticket["expected_network_source_ref"]
    if not isinstance(ticket_ref, str) or _REF.fullmatch(ticket_ref) is None:
        raise ValueError("invalid ticket_ref")
    if expected_source is not None and (not isinstance(expected_source, str) or _REF.fullmatch(expected_source) is None):
        raise ValueError("invalid expected_network_source_ref")
    timestamp = _observed(ticket["observed_at"])
    symptoms = _tokens(ticket["symptoms"], _SYMPTOMS, "symptoms")
    codes = set(_tokens(ticket["diagnostic_codes"], _CODES, "diagnostic_codes"))
    age = (now.astimezone(timezone.utc) - timestamp).total_seconds()
    if age > max_age_seconds or age < -5:
        return HelpdeskAssessment(ticket_ref, timestamp, "stale" if age > max_age_seconds else "future", "unknown", "none", (), _ADVICE["unknown"], ("Ticket evidence is not current.",))
    limitations = ["Classification is advisory; caller-supplied evidence is not independently verified."]
    if network_report is not None:
        if not isinstance(network_report, Mapping):
            raise ValueError("network_report must be mapping")
        if expected_source is None:
            raise ValueError("network report requires explicitly named source")
        if network_report.get("schema") != "sofia.it.network.report.v1" or network_report.get("source_ref") != expected_source:
            raise ValueError("network report source or schema mismatch")
        remote_observed = _observed(network_report.get("observed_at"))
        remote_age = (now.astimezone(timezone.utc) - remote_observed).total_seconds()
        if network_report.get("freshness") != "fresh" or remote_age > max_age_seconds or remote_age < -5:
            limitations.append("Network evidence was stale or outside the allowed clock window; ignored.")
        else:
            findings = network_report.get("findings")
            if not isinstance(findings, list) or len(findings) > 20:
                raise ValueError("invalid network findings")
            for finding in findings:
                if not isinstance(finding, Mapping) or set(finding) != {"code", "severity", "next_check"}:
                    raise ValueError("invalid network finding")
                code = finding["code"]
                if code in {"link_down", "dns_servfail", "dns_timeout"}:
                    codes.add(code)
            limitations.append("Network report is a supplied advisory projection, not a verified Platform receipt.")
    category = "unknown"
    for name, triggers, _ in _RULES:
        if triggers & codes:
            category = name
            break
    if category == "unknown" and symptoms:
        category = next((_SYMPTOM_CLASS[s] for s in sorted(symptoms)), "unknown")
    confidence = "medium" if codes else "low" if symptoms else "none"
    return HelpdeskAssessment(ticket_ref, timestamp, "fresh", category, confidence, tuple(sorted(codes)), _ADVICE[category], tuple(limitations))


def capability_registrations() -> tuple[tuple[Capability, object], ...]:
    capability = Capability(CAPABILITY_ID, "Advisory classification of approved ticket and diagnostic evidence.")

    def handler(request: CapabilityRequest) -> dict[str, object]:
        if request.capability != capability:
            raise ValueError("capability mismatch")
        params = request.parameters
        if set(params) - {"ticket", "network_report"} or "ticket" not in params:
            raise ValueError("expected ticket and optional network_report")
        return triage_evidence(params["ticket"], network_report=params.get("network_report"), now=datetime.now(timezone.utc)).as_dict()

    return ((capability, handler),)
