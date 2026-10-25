"""MOD-IT-DEVOPS: deterministic, inert review of supplied CI/CD observations.

An observation is never an authenticated workflow receipt or permission to deploy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-DEVOPS"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.devops.assess_pipeline.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
SHA = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
FIELDS = frozenset({"source_ref", "pipeline_ref", "observed_at", "commit_sha", "branch", "build", "tests", "security_scan", "artifact_digest", "deploy_state"})
RUN_STATES = frozenset({"passed", "failed", "pending", "not_run"})
DEPLOY_STATES = frozenset({"not_requested", "waiting_approval", "deployed_reported", "failed_reported"})


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid observed_at")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("observed_at requires timezone")
    return result.astimezone(timezone.utc)


def assess_pipeline(observation: Mapping[str, object], *, now: datetime,
                    max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(observation, Mapping) or set(observation) != FIELDS:
        raise ValueError("pipeline observation requires exact schema")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid max_age_seconds")
    for key in ("source_ref", "pipeline_ref", "branch"):
        value = observation[key]
        if not isinstance(value, str) or REF.fullmatch(value) is None:
            raise ValueError(f"invalid {key}")
    commit = observation["commit_sha"]
    digest = observation["artifact_digest"]
    if not isinstance(commit, str) or SHA.fullmatch(commit) is None:
        raise ValueError("commit_sha must be a Git SHA")
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("artifact_digest must be SHA256")
    for key in ("build", "tests", "security_scan"):
        if not isinstance(observation[key], str) or observation[key] not in RUN_STATES:
            raise ValueError(f"invalid {key}")
    if not isinstance(observation["deploy_state"], str) or observation["deploy_state"] not in DEPLOY_STATES:
        raise ValueError("invalid deploy_state")
    observed = _timestamp(observation["observed_at"])
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
    findings: list[str] = []
    if freshness == "fresh":
        for key in ("build", "tests", "security_scan"):
            if observation[key] == "failed":
                findings.append(f"{key}_failed_reported")
            elif observation[key] in {"pending", "not_run"}:
                findings.append(f"{key}_not_complete")
        if digest is None:
            findings.append("artifact_digest_missing")
        if observation["deploy_state"] == "deployed_reported":
            findings.append("deployment_outcome_unverified")
        elif observation["deploy_state"] == "failed_reported":
            findings.append("deployment_failure_reported")
        ready_to_propose = not findings and observation["deploy_state"] in {"not_requested", "waiting_approval"}
    else:
        ready_to_propose = False
        findings.append("stale_or_future_evidence")
    return {"schema": "sofia.it.devops.report.v1", "module_id": MODULE_ID,
            "sdk_protocol": str(SDK_PROTOCOL_VERSION), "source_ref": observation["source_ref"],
            "pipeline_ref": observation["pipeline_ref"], "commit_sha": commit,
            "observed_at": observed.isoformat(), "freshness": freshness,
            "classification": "unknown" if freshness != "fresh" else "attention" if findings else "no_issue_observed",
            "eligible_for_human_review": ready_to_propose,
            "findings": findings, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Review supplied CI/CD evidence without deploying or accessing source repositories.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observation"}:
            raise ValueError("invalid DevOps capability request")
        return assess_pipeline(request.parameters["observation"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
