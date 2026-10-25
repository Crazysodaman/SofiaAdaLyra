"""MOD-REMOTE-ACCESS: interpret *supplied* sanitized access/session signals.

Never opens a connection, reads credentials, issues identities or grants scopes.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-REMOTE-ACCESS"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "remote_access.review_session.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
FIELDS = frozenset({"source_ref", "session_ref", "observed_at", "transport", "status", "mfa_reported", "device_enrolled_reported", "channel_encrypted_reported", "idle_seconds", "revoke_reported"})
TRANSPORTS = frozenset({"ssh", "rdp", "vpn", "remote_shell", "other"})
STATES = frozenset({"active", "closed", "failed", "unknown"})


def assess_session(observation: Mapping[str, object], *, now: datetime,
                   max_age_seconds: int = 300, max_idle_seconds: int = 900) -> dict[str, object]:
    if not isinstance(observation, Mapping) or set(observation) != FIELDS:
        raise ValueError("session observation requires exact safe schema")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if any(type(v) is not int or not 1 <= v <= 86400 for v in (max_age_seconds, max_idle_seconds)):
        raise ValueError("invalid policy limits")
    for key in ("source_ref", "session_ref"):
        if not isinstance(observation[key], str) or REF.fullmatch(observation[key]) is None:
            raise ValueError(f"invalid {key}")
    if not isinstance(observation["transport"], str) or observation["transport"] not in TRANSPORTS:
        raise ValueError("invalid transport")
    if not isinstance(observation["status"], str) or observation["status"] not in STATES:
        raise ValueError("invalid status")
    for key in ("mfa_reported", "device_enrolled_reported", "channel_encrypted_reported", "revoke_reported"):
        if type(observation[key]) is not bool:
            raise ValueError(f"invalid {key}")
    idle = observation["idle_seconds"]
    if idle is not None and (type(idle) is not int or not 0 <= idle <= 86400):
        raise ValueError("invalid idle_seconds")
    if observation["status"] == "active" and idle is None:
        raise ValueError("active session requires idle observation")
    try:
        stamp = datetime.fromisoformat(observation["observed_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid observed_at") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    observed = stamp.astimezone(timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
    findings = []
    if freshness == "fresh":
        if observation["revoke_reported"] and observation["status"] == "active":
            findings.append("active_after_revocation_reported")
        if observation["status"] == "failed":
            findings.append("access_failure_reported")
        if observation["status"] == "active":
            if not observation["device_enrolled_reported"]:
                findings.append("device_enrollment_unconfirmed")
            if not observation["mfa_reported"]:
                findings.append("mfa_unconfirmed")
            if not observation["channel_encrypted_reported"]:
                findings.append("encryption_unconfirmed")
            if idle is not None and idle > max_idle_seconds:
                findings.append("idle_timeout_exceeded")
        if observation["status"] == "unknown":
            findings.append("session_state_unknown")
    else:
        findings.append("stale_or_future_evidence")
    return {"schema": "sofia.remote_access.session.report.v1", "module_id": MODULE_ID,
            "sdk_protocol": str(SDK_PROTOCOL_VERSION), "source_ref": observation["source_ref"],
            "session_ref": observation["session_ref"], "transport": observation["transport"],
            "observed_at": observed.isoformat(), "freshness": freshness,
            "classification": "unknown" if freshness != "fresh" or observation["status"] == "unknown" else "attention" if findings else "no_issue_observed",
            "findings": findings, "authorization_conclusion": "not_evaluated",
            "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Assess sanitized remote session evidence without connecting or granting access.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observation"}:
            raise ValueError("invalid Remote Access capability request")
        return assess_session(request.parameters["observation"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
