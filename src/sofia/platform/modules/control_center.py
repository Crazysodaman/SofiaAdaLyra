"""Bounded, read-only operator projection for the modular Platform.

This is deliberately a projection over canonical owners.  It does not keep
state, infer authority, or turn a lifecycle row into evidence that an adapter
is alive.  The desktop Settings process can therefore explain recorded module
and RUN state without becoming another module manager or execution broker.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .adapters import AdapterFactoryRegistry
from .observer import CanonicalPlatformModuleObserver


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
