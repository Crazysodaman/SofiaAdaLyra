"""Read-only, secret-free projection of a specific Portainer stack record.

This is not a Portainer connector, execution authority, deployment planner,
stack health verifier, or permission to inspect arbitrary Docker resources.
The caller must independently authenticate the endpoint and enforce scope.
"""
from __future__ import annotations

from collections.abc import Mapping
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
