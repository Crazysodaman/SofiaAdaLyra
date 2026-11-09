"""Bounded, allowlisted Portainer stack projections for MOD-IT-CONTAINERS.

Read-only schema adapter: never exposes raw Portainer response objects, Compose
files, environment values, Git authentication fields or arbitrary
metadata to a Core. Stack names remain untrusted and need privacy review
before exposure to a model. No Portainer API calls, SDK registration, state writes,
signature verification, permissions or deployment authority exist here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping


def project_portainer_stacks(
    raw_stacks: list[Mapping[str, object]], *,
    endpoint_id: int,
    observed_at: datetime,
) -> dict[str, object]:
    """Return only bounded, nonsecret stack identifiers and metadata.

    Portainer's status code is kept opaque: it is *not* proof of container
    health, successful deployment or a trusted Portainer session.
    """
    if type(endpoint_id) is not int or not 1 <= endpoint_id <= 1_000_000_000:
        raise ValueError("expected positive Portainer endpoint ID")
    if (not isinstance(observed_at, datetime)
            or observed_at.tzinfo is None or observed_at.utcoffset() is None):
        raise ValueError("observed_at must be timezone-aware")
    if type(raw_stacks) is not list or len(raw_stacks) > 256:
        raise ValueError("Portainer stack inventory must be a bounded list")

    seen_ids: set[int] = set()
    projected: list[dict[str, object]] = []
    for stack in raw_stacks:
        if not isinstance(stack, Mapping) or len(stack) > 128:
            raise ValueError("invalid stack metadata")
        stack_id = stack.get("Id")
        reported_endpoint = stack.get("EndpointId")
        if (type(stack_id) is not int or not 1 <= stack_id <= 1_000_000_000
                or stack_id in seen_ids):
            raise ValueError("invalid or duplicate stack ID")
        if type(reported_endpoint) is not int or reported_endpoint != endpoint_id:
            raise ValueError("stack endpoint mismatch or unknown endpoint")

        name = stack.get("Name")
        if (type(name) is not str or not 1 <= len(name) <= 160
                or name != name.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in name)):
            raise ValueError("invalid stack name")

        # Codes are intentionally uninterpreted and cannot imply "healthy".
        status_code = stack.get("Status")
        if (type(status_code) is not int
                or not 0 <= status_code <= 1000):
            status_code = None

        # Do not copy raw objects or nested keys. Raw stack metadata can
        # contain Env, GitConfig, Compose files and other private content.
        projected.append({
            "stack_id": stack_id,
            "name": name,
            "portainer_status_code": status_code,
            "runtime_health": "UNKNOWN",
            "deployment_verified": False,
        })
        seen_ids.add(stack_id)

    projected.sort(key=lambda item: item["stack_id"])
    return {
        "schema": "sofia.it.containers.portainer_stacks_projection.v1",
        "module_id": "MOD-IT-CONTAINERS",
        "endpoint_id": endpoint_id,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "source_verified": False,
        "secret_fields_exposed": False,
        "effect": "none",
        "stacks": projected,
    }
