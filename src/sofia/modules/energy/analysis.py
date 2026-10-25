"""MOD-ENERGY: effect-free UPS power and runtime risk assessment.

UPS values are untrusted until authenticated by Platform and can never actuate
power, shutdown, transfer load, or authorize other modules.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-ENERGY"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "energy.assess_ups.v1"
PROFILE = "OBSERVE"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
FIELDS = frozenset({"source_ref", "ups_ref", "observed_at", "mains_present", "battery_percent", "load_percent", "runtime_seconds", "self_test_state"})
TEST_STATES = frozenset({"passed", "failed", "not_run", "unknown"})


def assess_ups(observation: Mapping[str, object], *, now: datetime,
               max_age_seconds: int = 120, reserve_seconds: int = 600) -> dict[str, object]:
    if not isinstance(observation, Mapping) or set(observation) != FIELDS:
        raise ValueError("UPS observation requires exact schema")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if any(type(v) is not int or not 1 <= v <= 86400 for v in (max_age_seconds, reserve_seconds)):
        raise ValueError("invalid policy limits")
    for key in ("source_ref", "ups_ref"):
        if not isinstance(observation[key], str) or REF.fullmatch(observation[key]) is None:
            raise ValueError(f"invalid {key}")
    mains = observation["mains_present"]
    if mains is not None and type(mains) is not bool:
        raise ValueError("invalid mains_present")
    battery, load, remaining = (observation[k] for k in ("battery_percent", "load_percent", "runtime_seconds"))
    for name, value in (("battery_percent", battery), ("load_percent", load)):
        if value is not None and (type(value) not in {int, float} or not 0 <= value <= 100):
            raise ValueError(f"invalid {name}")
    if remaining is not None and (type(remaining) is not int or not 0 <= remaining <= 604800):
        raise ValueError("invalid runtime_seconds")
    if not isinstance(observation["self_test_state"], str) or observation["self_test_state"] not in TEST_STATES:
        raise ValueError("invalid self_test_state")
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
        if mains is False:
            findings.append("utility_power_absent_reported")
        elif mains is None:
            findings.append("utility_state_unknown")
        if battery is None:
            findings.append("battery_state_unknown")
        elif battery <= 20:
            findings.append("battery_low_reported")
        if load is None:
            findings.append("load_unknown")
        elif load >= 100:
            findings.append("load_at_or_over_limit_reported")
        elif load >= 85:
            findings.append("load_high_reported")
        if remaining is None:
            findings.append("runtime_estimate_unknown")
        elif remaining < reserve_seconds:
            findings.append("estimated_runtime_below_reserve")
        if observation["self_test_state"] == "failed":
            findings.append("self_test_failure_reported")
        elif observation["self_test_state"] in {"not_run", "unknown"}:
            findings.append("self_test_unverified")
    else:
        findings.append("stale_or_future_evidence")
    classification = "unknown" if freshness != "fresh" or mains is None or battery is None or load is None else "attention" if findings else "no_issue_observed"
    return {"schema": "sofia.energy.ups.report.v1", "module_id": MODULE_ID,
            "sdk_protocol": str(SDK_PROTOCOL_VERSION), "source_ref": observation["source_ref"],
            "ups_ref": observation["ups_ref"], "observed_at": observed.isoformat(),
            "freshness": freshness, "classification": classification, "findings": findings,
            "runtime_estimate_seconds": remaining if freshness == "fresh" else None,
            "estimate_is_not_a_shutdown_permission": True,
            "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Assess a scoped UPS observation without contacting or controlling power hardware.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observation"}:
            raise ValueError("invalid Energy capability request")
        return assess_ups(request.parameters["observation"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
