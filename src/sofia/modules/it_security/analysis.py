"""MOD-IT-SECURITY: bounded risk triage from external sanitized findings.

Unknown reports are not verified intrusions. No arbitrary alert text, secret,
endpoint URL, shell command, scanner or remediation can pass this boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-SECURITY"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.security.triage_findings.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "asset_ref", "finding_ref", "observed_at", "kind", "severity", "state"})
_KINDS = {"authentication_anomaly", "unpatched_software", "unexpected_exposure", "configuration_drift", "integrity_alert", "malware_signal"}
_SEVERITY = {"low", "medium", "high", "critical", "unknown"}
_STATES = {"open", "resolved", "unknown"}
_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4, "unknown": 0}
_CHECKS = {
    "authentication_anomaly": "Review approved identity-provider audit evidence and session scope.",
    "unpatched_software": "Compare signed version inventory with current vendor advisories.",
    "unexpected_exposure": "Review scoped ingress rules and authorized service listeners.",
    "configuration_drift": "Compare approved configuration baseline and change receipts.",
    "integrity_alert": "Confirm producer integrity evidence through trusted audit sources.",
    "malware_signal": "Escalate suspected endpoint activity to a human-reviewed security workflow.",
}


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid observed_at")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("timezone required")
    return at.astimezone(timezone.utc)


def triage_findings(findings: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("max_age_seconds out of bounds")
    if type(findings) is not list or not 1 <= len(findings) <= 64:
        raise ValueError("findings must contain 1..64 items")
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        if not isinstance(finding, Mapping) or set(finding) != _FIELDS:
            raise ValueError("security finding fields mismatch")
        source, asset, ref = (finding[k] for k in ("source_ref", "asset_ref", "finding_ref"))
        if any(not isinstance(v, str) or _REF.fullmatch(v) is None for v in (source, asset, ref)):
            raise ValueError("invalid security finding identifier")
        if (source, ref) in seen:
            raise ValueError("duplicate security finding")
        seen.add((source, ref))
        kind, severity, state = (finding[k] for k in ("kind", "severity", "state"))
        if not isinstance(kind, str) or kind not in _KINDS:
            raise ValueError("invalid security kind")
        if not isinstance(severity, str) or severity not in _SEVERITY:
            raise ValueError("invalid security severity")
        if not isinstance(state, str) or state not in _STATES:
            raise ValueError("invalid security state")
        observed = _timestamp(finding["observed_at"])
        delta = (now.astimezone(timezone.utc) - observed).total_seconds()
        freshness = "future" if delta < -5 else "stale" if delta > max_age_seconds else "fresh"
        eligible = freshness == "fresh" and state == "open" and severity != "unknown"
        rows.append({"source_ref": source, "asset_ref": asset, "finding_ref": ref,
                     "observed_at": observed.isoformat(), "freshness": freshness,
                     "reported_kind": kind, "reported_severity": severity,
                     "classification": "reported_open" if eligible else "unknown" if freshness != "fresh" or state == "unknown" or severity == "unknown" else "reported_resolved",
                     "next_check": _CHECKS[kind] if eligible else None})
    active = [row for row in rows if row["classification"] == "reported_open"]
    highest = max((row["reported_severity"] for row in active), key=lambda s: _ORDER[s], default=None)
    return {"schema": "sofia.it.security.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "findings": rows, "highest_reported_severity": highest,
            "summary": "reported_findings_need_review" if active else "unknown" if any(row["classification"] == "unknown" for row in rows) else "no_current_open_reported_findings",
            "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Classify current sanitized security finding reports without remediation.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"findings"}:
            raise ValueError("invalid security capability request")
        return triage_findings(request.parameters["findings"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
