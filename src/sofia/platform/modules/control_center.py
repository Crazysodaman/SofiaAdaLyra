"""Bounded, read-only operator projection for the modular Platform.

This is deliberately a projection over canonical owners.  It does not keep
state, infer authority, or turn a lifecycle row into evidence that an adapter
is alive.  The desktop Settings process can therefore explain recorded module
and RUN state without becoming another module manager or execution broker.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.safe.permissions import (
    PermissionLevel,
    capability_permission_policy,
)

from .adapters import AdapterFactoryRegistry
from .observer import CanonicalPlatformModuleObserver


_INSTALLED_LIFECYCLES = frozenset({
    "staged", "installed_disabled", "activating", "active", "draining",
    "paused", "quarantined", "updating", "rolling_back",
})
_RC_EVIDENCE = frozenset({
    "test", "security_audit", "independent_review", "compatibility",
    "interoperability", "rollback",
})
_PRODUCTION_EVIDENCE = _RC_EVIDENCE | frozenset({
    "matching_ci", "host_acceptance",
})


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def platform_control_center_text(
    state_path: Path | str,
    *,
    factories: AdapterFactoryRegistry | None = None,
    job_limit: int = 30,
    operation_limit: int = 30,
) -> str:
    """Return a privacy-minimized snapshot from authoritative Platform state.

    Payloads, requested effects, principals, approval references, results, and
    evidence contents are intentionally omitted.  Factory availability is
    UNKNOWN unless the application supplies its live reviewed registry; a
    separately opened Settings process must not pretend it can reconstruct it.
    """
    if not isinstance(state_path, (Path, str)):
        raise TypeError("state_path must be a Path or path string")
    if factories is not None and not isinstance(
        factories, AdapterFactoryRegistry
    ):
        raise TypeError("factories must be an AdapterFactoryRegistry or None")
    for label, value in (
        ("job_limit", job_limit),
        ("operation_limit", operation_limit),
    ):
        if type(value) is not int or not 1 <= value <= 100:
            raise ValueError(f"{label} must be in 1..100")

    now = datetime.now(timezone.utc)
    observer = CanonicalPlatformModuleObserver(state_path)
    described = {row.module_id: row for row in observer.described()}
    health = {
        row.module_instance_id.split("@", 1)[0]: row
        for row in observer.health()
    }
    lines = [
        "PLATFORM CONTROL CENTER — READ ONLY",
        f"Snapshot: {now.isoformat()}",
        "Lifecycle, health, RUN, and authority are separate states. "
        "No action was performed.",
        "",
        "MODULES",
    ]
    module_ids = sorted(set(described) | set(health))
    if not module_ids:
        lines.append("No installed module lifecycle records.")
    for module_id in module_ids:
        description = described.get(module_id)
        status = health.get(module_id)
        version = "UNKNOWN" if description is None else description.version
        profile = "UNKNOWN" if description is None else description.active_profile
        lifecycle = "UNKNOWN" if status is None else status.lifecycle
        current_health = "UNKNOWN" if status is None else status.health.value
        host = "UNKNOWN" if status is None else status.host_identity
        reasons = (
            "missing-observation"
            if status is None
            else ",".join(status.reason_codes)
        )
        lines.append(
            f"{module_id} version={version} lifecycle={lifecycle} profile={profile} "
            f"health={current_health} host={host} reasons={reasons}"
        )
        if description is not None:
            capabilities = ",".join(description.capabilities) or "none"
            simulated = ",".join(sorted(description.simulated_only)) or "none"
            lines.append(
                f"  declared_capabilities={capabilities}; "
                f"simulated_only={simulated}"
            )

    guard = CanonicalSQLiteGuard(Path(state_path))
    with closing(guard.connect(timeout=10.0, read_only=True)) as db:
        db.row_factory = sqlite3.Row
        lines.extend(("", "RECENT RUN JOBS (metadata only)"))
        if not _table_exists(db, "autonomous_work_job"):
            lines.append("UNKNOWN — canonical RUN table is absent.")
        else:
            jobs = db.execute(
                "SELECT job_id,kind,status,priority,risk,created_at,updated_at,deadline,"
                "attempt_count,CASE WHEN reason IS NULL OR reason='' THEN 0 ELSE 1 END "
                "AS has_reason FROM autonomous_work_job "
                "ORDER BY created_at DESC,job_id LIMIT ?",
                (job_limit,),
            ).fetchall()
            if not jobs:
                lines.append("No RUN jobs recorded.")
            for row in jobs:
                lines.append(
                    f"{row['job_id']} kind={row['kind']} status={row['status']} "
                    f"priority={row['priority']} risk={row['risk']} "
                    f"attempts={row['attempt_count']} updated={row['updated_at']} "
                    f"deadline={row['deadline']} "
                    f"reason_recorded={bool(row['has_reason'])}"
                )

        lines.extend(("", "RECENT MODULE OPERATIONS (metadata only)"))
        operation_tables = all(
            _table_exists(db, name)
            for name in (
                "platform_module_operation_request",
                "platform_module_operation_attempt",
            )
        )
        if not operation_tables:
            lines.append("UNKNOWN — canonical module-operation journal is absent.")
        else:
            operations = db.execute(
                """SELECT request.request_id,request.module_id,request.operation,
                          request.component_id,request.host_identity,request.created_at,
                          attempt.status,attempt.attempt_number,attempt.occurred_at,
                          CASE WHEN attempt.evidence_ref IS NULL
                               THEN 0 ELSE 1 END AS has_evidence
                   FROM platform_module_operation_request AS request
                   LEFT JOIN platform_module_operation_attempt AS attempt
                     ON attempt.event_id=(
                       SELECT newest.event_id
                       FROM platform_module_operation_attempt AS newest
                       WHERE newest.request_id=request.request_id
                       ORDER BY newest.event_id DESC LIMIT 1)
                   ORDER BY request.created_at DESC,request.request_id LIMIT ?""",
                (operation_limit,),
            ).fetchall()
            if not operations:
                lines.append("No module operations recorded.")
            for row in operations:
                lines.append(
                    f"{row['request_id']} module={row['module_id']} operation={row['operation']} "
                    f"component={row['component_id']} host={row['host_identity']} "
                    f"latest={row['status'] or 'admitted-without-attempt'} "
                    f"attempt={row['attempt_number'] or 0} "
                    f"evidence_recorded={bool(row['has_evidence'])} "
                    f"recorded={row['occurred_at'] or row['created_at']}"
                )

    lines.extend(("", "REVIEWED ADAPTER FACTORIES"))
    if factories is None:
        lines.append(
            "UNKNOWN — no live application factory registry was supplied to this viewer."
        )
    else:
        contracts = factories.contracts()
        if not contracts:
            lines.append(
                "No reviewed adapter factories registered in this "
                "application process."
            )
        for contract in contracts:
            lines.append(
                f"{contract.factory_id} module={contract.module_id} "
                f"components={','.join(sorted(contract.component_ids))} "
                f"profiles={','.join(sorted(profile.value for profile in contract.profiles))} "
                f"safe_inspection={contract.safe_inspection} "
                f"safe_shutdown={contract.safe_shutdown} "
                f"replay_safe={contract.start_effect_replay_safe}"
            )
    return "\n".join(lines)


def platform_module_manager_text(state_path: Path | str) -> str:
    """Render a bounded module-manager projection from canonical owners.

    This view deliberately performs no lifecycle transition.  It keeps
    installation, lifecycle, runtime health, release readiness and authority
    visibly separate so a UI cannot turn one into another.
    """
    if not isinstance(state_path, (Path, str)):
        raise TypeError("state_path must be a Path or path string")
    observer = CanonicalPlatformModuleObserver(state_path)
    health_by_module = {
        item.module_instance_id.split("@", 1)[0]: item
        for item in observer.health()
    }
    guard = CanonicalSQLiteGuard(Path(state_path))
    with closing(guard.connect(timeout=10.0, read_only=True)) as db:
        db.row_factory = sqlite3.Row
        if not _table_exists(db, "platform_module_lifecycle"):
            return (
                "MODULE MANAGER — READ ONLY\n"
                "No verified module lifecycle records. Discovery does not "
                "install or authorize a module."
            )
        lifecycle_rows = db.execute(
            "SELECT module_id,version,package_digest,lifecycle,revision,"
            "active_profile,updated_at FROM platform_module_lifecycle "
            "ORDER BY module_id"
        ).fetchall()
        dependencies: dict[str, list[str]] = {}
        if _table_exists(db, "platform_module_dependency"):
            for row in db.execute(
                "SELECT module_id,dependency_id,minimum_version,"
                "maximum_version_exclusive FROM platform_module_dependency "
                "ORDER BY module_id,dependency_id"
            ):
                bounds = f">={row['minimum_version']}"
                if row["maximum_version_exclusive"] is not None:
                    bounds += f",<{row['maximum_version_exclusive']}"
                dependencies.setdefault(str(row["module_id"]), []).append(
                    f"{row['dependency_id']} ({bounds})"
                )
        capabilities: dict[str, list[str]] = {}
        if _table_exists(db, "platform_module_capability"):
            for row in db.execute(
                "SELECT module_id,capability_id FROM platform_module_capability "
                "ORDER BY module_id,capability_id"
            ):
                capabilities.setdefault(str(row["module_id"]), []).append(
                    str(row["capability_id"])
                )
        policies: dict[str, sqlite3.Row] = {}
        if _table_exists(db, "platform_module_policy"):
            policies = {
                str(row["module_id"]): row
                for row in db.execute(
                    "SELECT module_id,package_digest,placement_mode,"
                    "isolation_profile FROM platform_module_policy"
                )
            }
        evidence: dict[str, list[sqlite3.Row]] = {}
        if _table_exists(db, "platform_module_readiness_evidence"):
            for row in db.execute(
                "SELECT module_id,package_digest,source_sha,kind,passed,"
                "observed_at,revoked_at FROM platform_module_readiness_evidence "
                "ORDER BY observed_at,evidence_id"
            ):
                evidence.setdefault(str(row["module_id"]), []).append(row)
        attempts: dict[str, sqlite3.Row] = {}
        if all(
            _table_exists(db, name)
            for name in (
                "platform_module_operation_request",
                "platform_module_operation_attempt",
            )
        ):
            for row in db.execute(
                """SELECT request.module_id,request.operation,attempt.status,
                          attempt.occurred_at
                   FROM platform_module_operation_request AS request
                   JOIN platform_module_operation_attempt AS attempt
                     ON attempt.request_id=request.request_id
                   ORDER BY attempt.occurred_at DESC,attempt.event_id DESC"""
            ):
                attempts.setdefault(str(row["module_id"]), row)
        manifest_projections: dict[str, tuple[str, object]] = {}
        if _table_exists(db, "platform_module_manifest_projection"):
            for row in db.execute(
                "SELECT module_id,package_digest,manifest_json "
                "FROM platform_module_manifest_projection ORDER BY module_id"
            ):
                raw = str(row["manifest_json"])
                digest = str(row["package_digest"])
                try:
                    document = (
                        json.loads(raw)
                        if sha256(raw.encode("utf-8")).hexdigest() == digest
                        else None
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    document = None
                manifest_projections[str(row["module_id"])] = (
                    digest, document,
                )

    lines = [
        "MODULE MANAGER — VERIFIED READ-ONLY PROJECTION",
        "Lifecycle, health, readiness, compatibility, and authority are "
        "independent. Use governed lifecycle commands for changes.",
    ]
    for row in lifecycle_rows:
        module_id = str(row["module_id"])
        lifecycle = str(row["lifecycle"])
        package_digest = str(row["package_digest"])
        current_evidence = [
            item for item in evidence.get(module_id, ())
            if str(item["package_digest"]) == package_digest
        ]
        source_sha = (
            "UNKNOWN" if not current_evidence
            else str(current_evidence[-1]["source_sha"])
        )
        exact_revision_evidence = [
            item for item in current_evidence
            if str(item["source_sha"]) == source_sha
        ]
        failed = any(
            (not bool(item["passed"])) or item["revoked_at"] is not None
            for item in exact_revision_evidence
        )
        satisfied = {
            str(item["kind"]) for item in exact_revision_evidence
            if bool(item["passed"]) and item["revoked_at"] is None
        }
        if lifecycle in {"quarantined", "removed"} or failed:
            readiness = "BLOCKED"
        elif _PRODUCTION_EVIDENCE.issubset(satisfied):
            readiness = "PRODUCTION_READY"
        elif _RC_EVIDENCE.issubset(satisfied):
            readiness = "RELEASE_CANDIDATE"
        elif lifecycle in _INSTALLED_LIFECYCLES:
            readiness = "BETA"
        else:
            readiness = "ALPHA"
        health = health_by_module.get(module_id)
        health_name = "UNKNOWN" if health is None else health.health.value.upper()
        host = "UNKNOWN" if health is None else health.host_identity
        reason = "missing-observation" if health is None else ",".join(health.reason_codes)
        policy = policies.get(module_id)
        policy_identity_ok = (
            policy is not None and str(policy["package_digest"]) == package_digest
        )
        capability_values = capabilities.get(module_id, [])
        protected = [
            capability for capability in capability_values
            if capability_permission_policy(capability).level
            > PermissionLevel.SAFE_AUTONOMOUS
        ]
        latest = attempts.get(module_id)
        latest_operation = (
            "none" if latest is None
            else f"{latest['operation']}:{latest['status']}@{latest['occurred_at']}"
        )
        signed_policy = manifest_projections.get(module_id)
        manifest = (
            signed_policy[1]
            if signed_policy is not None
            and signed_policy[0] == package_digest
            and isinstance(signed_policy[1], dict)
            else None
        )
        resources = "UNKNOWN"
        devices = "UNKNOWN"
        profiles = "UNKNOWN"
        maintenance = "UNKNOWN"
        if manifest is not None:
            raw_resources = manifest.get("resources")
            if isinstance(raw_resources, list) and all(
                isinstance(item, list) and len(item) == 2
                and isinstance(item[0], str) and type(item[1]) is int
                for item in raw_resources
            ):
                resources = ",".join(
                    f"{name}={amount}" for name, amount in raw_resources
                ) or "none"
            raw_devices = manifest.get("device_requirements")
            if isinstance(raw_devices, list) and all(
                isinstance(item, str) for item in raw_devices
            ):
                devices = ",".join(raw_devices) or "none"
            raw_profiles = manifest.get("profiles")
            if isinstance(raw_profiles, list) and all(
                isinstance(item, dict)
                and isinstance(item.get("profile_id"), str)
                and type(item.get("permission_ceiling")) is int
                for item in raw_profiles
            ):
                profiles = ",".join(
                    f"{item['profile_id']}(ceiling={item['permission_ceiling']})"
                    for item in raw_profiles
                ) or "none"
            raw_maintenance = manifest.get("maintenance_profile")
            if isinstance(raw_maintenance, dict) and all(
                key in raw_maintenance
                for key in (
                    "support_status", "retry_limit", "quarantine_threshold",
                    "health_probe_ids", "update_policy", "rollback_procedure",
                )
            ):
                probes = raw_maintenance["health_probe_ids"]
                maintenance = (
                    f"support={raw_maintenance['support_status']};"
                    f"retries={raw_maintenance['retry_limit']};"
                    f"quarantine_threshold="
                    f"{raw_maintenance['quarantine_threshold']};"
                    f"probes={','.join(probes) if isinstance(probes, list) else 'UNKNOWN'}"
                )
        lines.extend((
            "",
            f"{module_id} version={row['version']} installed="
            f"{str(lifecycle in _INSTALLED_LIFECYCLES).lower()} "
            f"lifecycle={lifecycle.upper()} revision={row['revision']}",
            f"  package={package_digest} profile="
            f"{row['active_profile'] or 'DISABLED'} readiness={readiness} "
            f"source={source_sha}",
            f"  health={health_name} host={host} reasons={reason}",
            f"  dependencies={'; '.join(dependencies.get(module_id, [])) or 'none'}",
            f"  capabilities={','.join(capability_values) or 'none'}; "
            f"protected={','.join(protected) or 'none'}",
            "  effective_authority=UNKNOWN (declared capability is not a grant)",
            f"  placement="
            f"{('UNKNOWN' if policy is None else policy['placement_mode'])}; "
            f"isolation={('UNKNOWN' if policy is None else policy['isolation_profile'])}; "
            f"policy_identity={'verified' if policy_identity_ok else 'unknown-or-mismatch'}",
            f"  readiness_evidence={','.join(sorted(satisfied)) or 'none'}; "
            f"latest_operation={latest_operation}",
            f"  signed_resources={resources}; devices={devices}; "
            f"profiles={profiles}",
            f"  maintenance={maintenance}",
            "  module_settings=UNSUPPORTED (signed manifest has no settings "
            "contract); no configuration UI is simulated",
        ))
    return "\n".join(lines)
