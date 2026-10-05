"""Temporary exact remote grants derived from one approved workload migration.

This bridges the protected migration approval to the lower-level pinned-mTLS
remote authorization boundary without creating a standing Fleet mutation grant.
Grant scope is restricted to the reviewed workload catalog operations that the
migration executor can actually call for the source/target hosts.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterator, Mapping
from uuid import UUID, uuid4

from sofia.distributed.authorization import (
    RemoteGrant,
    remote_operation_is_read_only,
)
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.workload import MigrationPlan
from sofia.ops.workload_backend import WorkloadExecutionCatalog


@dataclass(frozen=True, slots=True)
class MigrationRemoteGrantSpec:
    host_id: str
    node_id: UUID
    capability: str
    operation: str


def migration_remote_grant_specs(
    *,
    catalog: WorkloadExecutionCatalog,
    plan: MigrationPlan,
    host_node_ids: Mapping[str, UUID | None],
    local_host_id: str | None = None,
) -> tuple[MigrationRemoteGrantSpec, ...]:
    """Return only the remote non-read-only operations this migration may call.

    This function has no side effects and is intentionally suitable for
    preflight before the one-time migration approval is consumed.
    """
    if not isinstance(catalog, WorkloadExecutionCatalog):
        raise TypeError("catalog must be WorkloadExecutionCatalog")
    if not isinstance(plan, MigrationPlan):
        raise TypeError("plan must be MigrationPlan")
    if not isinstance(host_node_ids, Mapping):
        raise TypeError("host_node_ids must be a mapping")
    local = (local_host_id or "").strip()

    workload_id = plan.workload.contract.workload_id
    version = plan.workload.contract.version
    source = catalog.profile(workload_id, version, plan.source_host_id)
    target = catalog.profile(workload_id, version, plan.target_host_id)

    source_steps = ["drain"]
    if plan.workload.checkpoint_required:
        source_steps.append("checkpoint")
    source_steps.extend(("fence", "rollback"))

    target_steps = ["start", "ready"]
    if plan.workload.contract.singleton:
        target_steps.append("activate")
    target_steps.append("rollback")

    requested: list[tuple[str, object | None]] = [
        *((plan.source_host_id, getattr(source, step)) for step in source_steps),
        *((plan.target_host_id, getattr(target, step)) for step in target_steps),
    ]

    specs: dict[tuple[UUID, str, str], MigrationRemoteGrantSpec] = {}
    for host_id, binding in requested:
        if host_id == local or binding is None:
            continue
        if remote_operation_is_read_only(binding.capability, binding.operation):
            continue
        node_id = host_node_ids.get(host_id)
        if not isinstance(node_id, UUID):
            raise PermissionError(
                f"remote migration host lacks an enrolled node identity: {host_id}"
            )
        key = (node_id, binding.capability, binding.operation)
        specs[key] = MigrationRemoteGrantSpec(
            host_id=host_id,
            node_id=node_id,
            capability=binding.capability,
            operation=binding.operation,
        )

    return tuple(
        specs[key]
        for key in sorted(
            specs,
            key=lambda item: (str(item[0]), item[1], item[2]),
        )
    )


def _binding_document(binding) -> dict | None:
    if binding is None:
        return None
    return {
        "capability": binding.capability,
        "operation": binding.operation,
        "parameters": [
            [key, value] for key, value in binding.parameters
        ],
        "context_parameters": [
            [key, value] for key, value in binding.context_parameters
        ],
        "expect_path": binding.expect_path,
        "expect_equals": binding.expect_equals,
        "result_ref_path": binding.result_ref_path,
    }


def migration_execution_profile_document(
    *,
    catalog: WorkloadExecutionCatalog,
    plan: MigrationPlan,
) -> dict:
    """Canonical exact operation profile the operator is approving."""
    if not isinstance(catalog, WorkloadExecutionCatalog):
        raise TypeError("catalog must be WorkloadExecutionCatalog")
    if not isinstance(plan, MigrationPlan):
        raise TypeError("plan must be MigrationPlan")
    workload_id = plan.workload.contract.workload_id
    version = plan.workload.contract.version
    source = catalog.profile(workload_id, version, plan.source_host_id)
    target = catalog.profile(workload_id, version, plan.target_host_id)

    source_steps = ["drain"]
    if plan.workload.checkpoint_required:
        source_steps.append("checkpoint")
    source_steps.extend(("fence", "rollback"))

    target_steps = ["start", "ready"]
    if plan.workload.contract.singleton:
        target_steps.append("activate")
    target_steps.append("rollback")

    return {
        "workload_id": workload_id,
        "version": version,
        "source_host_id": plan.source_host_id,
        "target_host_id": plan.target_host_id,
        "source_operations": [
            {
                "step": step,
                "binding": _binding_document(getattr(source, step)),
            }
            for step in source_steps
        ],
        "target_operations": [
            {
                "step": step,
                "binding": _binding_document(getattr(target, step)),
            }
            for step in target_steps
        ],
    }


def migration_execution_profile_sha256(
    *,
    catalog: WorkloadExecutionCatalog,
    plan: MigrationPlan,
) -> str:
    document = migration_execution_profile_document(
        catalog=catalog,
        plan=plan,
    )
    return sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def migration_approval_parameters(
    *,
    catalog: WorkloadExecutionCatalog,
    plan: MigrationPlan,
    workload_parameters: dict,
    source_node_id: UUID | None,
    target_node_id: UUID | None,
    grant_specs: tuple[MigrationRemoteGrantSpec, ...],
) -> dict:
    """Exact approval document bound to nodes + typed execution profile."""
    if not isinstance(workload_parameters, dict):
        raise TypeError("workload_parameters must be a dict")
    if not isinstance(grant_specs, tuple):
        raise TypeError("grant_specs must be a tuple")
    return {
        "migration_id": plan.migration_id,
        "workload": workload_parameters,
        "source_host_id": plan.source_host_id,
        "target_host_id": plan.target_host_id,
        "source_node_id": (
            None if source_node_id is None else str(source_node_id)
        ),
        "target_node_id": (
            None if target_node_id is None else str(target_node_id)
        ),
        "state_mode": plan.workload.state_mode.value,
        "checkpoint_required": plan.workload.checkpoint_required,
        "failure_domain_spread": plan.workload.failure_domain_spread,
        "execution_profile_sha256": migration_execution_profile_sha256(
            catalog=catalog,
            plan=plan,
        ),
        "remote_operations": [
            {
                "host_id": spec.host_id,
                "node_id": str(spec.node_id),
                "capability": spec.capability,
                "operation": spec.operation,
            }
            for spec in grant_specs
        ],
    }


@contextmanager
def temporary_migration_remote_grants(
    *,
    state_path: Path,
    specs: tuple[MigrationRemoteGrantSpec, ...],
    approved_by: str,
    now: datetime,
    ttl: timedelta = timedelta(minutes=30),
) -> Iterator[tuple[RemoteGrant, ...]]:
    """Materialize exact grants for one migration and always revoke them."""
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be Path")
    if not isinstance(specs, tuple) or any(
        not isinstance(item, MigrationRemoteGrantSpec) for item in specs
    ):
        raise TypeError("specs must be MigrationRemoteGrantSpec tuple")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("approved_by must be nonempty")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if (
        not isinstance(ttl, timedelta)
        or ttl <= timedelta(0)
        or ttl > timedelta(hours=1)
    ):
        raise ValueError("migration remote grant ttl must be in (0, 1 hour]")

    authorization = DurableRemoteAuthorization(state_path)
    created: list[RemoteGrant] = []
    try:
        for spec in specs:
            grant = RemoteGrant(
                grant_id=uuid4(),
                node_id=spec.node_id,
                capability=spec.capability,
                operation=spec.operation,
                approved_by=approved_by.strip(),
                expires_at=now + ttl,
            )
            authorization.add_approved_grant(grant)
            created.append(grant)
        yield tuple(created)
    finally:
        for grant in created:
            authorization.revoke(grant.grant_id)
        authorization.close()
