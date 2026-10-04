"""Engineering 22F: explicit, exact-scope, revocable local authorization.

Only locally approved grants can authorize a requested node/capability/operation.
No enrollment, advertised capability, prompt, or connectivity grants permission.
Production grants are persisted by DurableRemoteAuthorization; this module
defines the admission interface and immutable grant contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sofia.distributed.capabilities import _aware, _identifier


REMOTE_MUTATION_HOST_CAPABILITIES = {
    ("service.manage", "start"): "remote.service.start",
    ("service.manage", "stop"): "remote.service.stop",
    ("service.manage", "restart"): "remote.service.restart",
    ("system.manage", "reboot"): "remote.host.reboot",
    ("package.manage", "update"): "remote.package.update",
    ("vm.manage", "start"): "remote.vm.start",
    ("vm.manage", "stop"): "remote.vm.stop",
    ("llm.manage", "pull"): "remote.ollama.pull",
    ("llm.manage", "load"): "remote.ollama.load",
    ("llm.manage", "unload"): "remote.ollama.unload",
    ("container.manage", "restart"): "remote.container.restart",
}


def remote_host_capability_name(
    capability: str,
    operation: str,
) -> str | None:
    _identifier(capability, "Remote capability")
    _identifier(operation, "Remote operation")
    return REMOTE_MUTATION_HOST_CAPABILITIES.get((capability, operation))


REMOTE_READ_ONLY_OPERATIONS = frozenset({
    ("system.inspect", "process"),
    ("system.inspect", "system"),
    ("system.inspect", "network"),
    ("system.inspect", "service"),
    ("system.inspect", "hardware"),
    ("vm.inspect", "list"),
    ("vm.inspect", "get"),
    ("container.inspect", "list"),
    ("container.inspect", "get"),
    ("container.inspect", "stats"),
    ("container.inspect", "logs"),
    ("container.inspect", "info"),
    ("container.inspect", "summary"),
    ("container.inspect", "images"),
    ("container.inspect", "volumes"),
    ("container.inspect", "networks"),
    ("container.inspect", "stacks"),
    ("llm.inspect", "inference_policy"),
    ("llm.inspect", "models"),
    ("llm.inspect", "running"),
    ("llm.inspect", "show"),
})


def remote_operation_is_read_only(capability: str, operation: str) -> bool:
    """Return whether a typed remote operation is project Level-1 observation."""
    _identifier(capability, "Remote capability")
    _identifier(operation, "Remote operation")
    return (capability, operation) in REMOTE_READ_ONLY_OPERATIONS


@dataclass(frozen=True)
class RemoteGrant:
    grant_id: UUID
    node_id: UUID
    capability: str
    operation: str
    approved_by: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, UUID) or not isinstance(self.node_id, UUID):
            raise TypeError("Grant identifiers must be UUIDs.")
        _identifier(self.capability, "Grant capability")
        _identifier(self.operation, "Grant operation")
        if not isinstance(self.approved_by, str) or not self.approved_by.strip():
            raise ValueError("Grant must identify its approving authority.")
        _aware(self.expires_at, "Grant expires_at")


class RemoteAuthorization(ABC):
    """Exact-scope admission interface; implementations own grant persistence."""

    @abstractmethod
    def add_approved_grant(self, grant: RemoteGrant) -> None:
        raise NotImplementedError

    @abstractmethod
    def revoke(self, grant_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def permits(self, grant_id: UUID, *, node_id: UUID, capability: str,
                operation: str, now: datetime) -> bool:
        raise NotImplementedError
