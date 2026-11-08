"""Bounded, secret-free Portainer stack metadata projection.

Never projects Compose files, environment variables, Git credentials, or
health assertions. Source data is untrusted until the Platform authenticates
and admits its Portainer observation separately.
"""
from __future__ import annotations

from collections.abc import Mapping


def summarize_stack_metadata(record: Mapping[str, object], *,
                             stack_id: int, endpoint_id: int) -> dict[str, object]:
    """Project an exact Portainer stack/endpoint match without any raw secrets."""
    if type(stack_id) is not int or stack_id < 1:
        raise ValueError("stack_id must be a positive integer")
    if type(endpoint_id) is not int or endpoint_id < 1:
        raise ValueError("endpoint_id must be a positive integer")
    if not isinstance(record, Mapping):
        raise ValueError("invalid Portainer stack response")
    if type(record.get("Id")) is not int or record["Id"] != stack_id:
        raise ValueError("Portainer stack identity mismatch")
    if type(record.get("EndpointId")) is not int or record["EndpointId"] != endpoint_id:
        raise ValueError("Portainer environment identity mismatch")
    name = record.get("Name")
    if (not isinstance(name, str) or not 1 <= len(name) <= 128
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("invalid Portainer stack name")
    kind, status = record.get("Type"), record.get("Status")
    if kind is not None and (type(kind) is not int or not 0 <= kind <= 255):
        raise ValueError("invalid Portainer stack type")
    if status is not None and (type(status) is not int or not 0 <= status <= 255):
        raise ValueError("invalid Portainer stack status")
    git = record.get("GitConfig")
    if "GitConfig" not in record:
        source = "unknown"
    elif git is None:
        source = "not_git_evidenced"
    elif isinstance(git, Mapping):
        source = "git"
    else:
        source = "unknown"
    return {
        "schema": "sofia.it.containers.portainer_stack_summary.v1",
        "stack_id": stack_id,
        "endpoint_id": endpoint_id,
        "name": name,
        "type_code": kind,
        "status_code": status,
        "source_class": source,
        "runtime_health_verified": False,
        "compose_or_env_exposed": False,
        "evidence_class": "supplied_unverified",
        "effect": "none",
    }
