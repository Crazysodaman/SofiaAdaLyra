"""Read-only, secret-free projection of a specific Portainer stack record.

This is not a Portainer connector, execution authority, deployment planner,
stack health verifier, or permission to inspect arbitrary Docker resources.
The caller must independently authenticate the endpoint and enforce scope.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


def project_portainer_stack_metadata(
    response: Mapping[str, Any], *, stack_id: int, endpoint_id: int,
) -> dict[str, object]:
    """Return an allowlisted display snapshot bound to exact expected IDs.

    No Compose file, environment variable, Git URL, credential, webhook or
    token field from Portainer is ever forwarded. The presence of GitConfig
    is a source hint, never proof that the source commit is trustworthy.
    """
    if type(stack_id) is not int or stack_id < 1:
        raise ValueError("stack_id must be a positive integer")
    if type(endpoint_id) is not int or endpoint_id < 1:
        raise ValueError("endpoint_id must be a positive integer")
    if not isinstance(response, Mapping):
        raise ValueError("invalid Portainer stack metadata")
    if type(response.get("Id")) is not int or response["Id"] != stack_id:
        raise ValueError("Portainer stack identity mismatch")
    if (
        type(response.get("EndpointId")) is not int
        or response["EndpointId"] != endpoint_id
    ):
        raise ValueError("Portainer endpoint identity mismatch")
    name = response.get("Name")
    if (
        not isinstance(name, str)
        or not name
        or len(name) > 128
        or name != name.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise ValueError("invalid Portainer stack display name")
    git_config = response.get("GitConfig")
    if git_config is not None and not isinstance(git_config, Mapping):
        raise ValueError("invalid Portainer Git source metadata")
    status = response.get("Status")
    if status is not None and (type(status) is not int or status < 0):
        raise ValueError("invalid Portainer stack status code")
    return {
        "stack_id": stack_id,
        "endpoint_id": endpoint_id,
        "name": name,
        "source_hint": "git" if git_config else "unknown",
        "raw_status_code": status,
        "evidence_class": "portainer_metadata_unverified_health",
    }


def project_portainer_stacks(
    raw_stacks: list[Mapping[str, Any]], *, endpoint_id: int,
    observed_at: datetime,
) -> dict[str, object]:
    """Project a bounded list through the SAME canonical stack validator.

    The bulk GET never returns Portainer's raw GitConfig, Compose, environment
    variables, webhook, resource controls, credentials or arbitrary fields.
    Status codes are opaque and never assert deployment/health.
    """
    if type(endpoint_id) is not int or not 1 <= endpoint_id <= 1_000_000_000:
        raise ValueError("expected positive Portainer endpoint ID")
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() is None):
        raise ValueError("observed_at must be timezone-aware")
    if type(raw_stacks) is not list or len(raw_stacks) > 256:
        raise ValueError("Portainer stack inventory must be a bounded list")
    seen: set[int] = set()
    stacks: list[dict[str, object]] = []
    for record in raw_stacks:
        if not isinstance(record, Mapping) or len(record) > 128:
            raise ValueError("invalid Portainer stack metadata")
        stack_id = record.get("Id")
        if type(stack_id) is not int or not 1 <= stack_id <= 1_000_000_000:
            raise ValueError("invalid Portainer stack ID")
        if stack_id in seen:
            raise ValueError("duplicate Portainer stack ID")
        status = record.get("Status")
        status = status if type(status) is int and 0 <= status <= 1000 else None
        # Supply ONLY the approved fields to the single-stack validator:
        # never pass through the caller's full potentially secret-bearing dict.
        detail = project_portainer_stack_metadata(
            {"Id": stack_id, "EndpointId": record.get("EndpointId"),
             "Name": record.get("Name"), "Status": status},
            stack_id=stack_id, endpoint_id=endpoint_id,
        )
        stacks.append({
            "stack_id": detail["stack_id"],
            "name": detail["name"],
            "portainer_status_code": detail["raw_status_code"],
            "runtime_health": "UNKNOWN",
            "deployment_verified": False,
        })
        seen.add(stack_id)
    stacks.sort(key=lambda record: record["stack_id"])
    return {
        "schema": "sofia.it.containers.portainer_stacks_projection.v1",
        "module_id": "MOD-IT-CONTAINERS",
        "endpoint_id": endpoint_id,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "source_verified": False,
        "secret_fields_exposed": False,
        "effect": "none",
        "stacks": stacks,
    }
