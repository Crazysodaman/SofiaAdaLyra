"""Exact endpoint policy for distributed PKG-NET operations.

This is an authorization precondition, not peer authentication or a firewall.
It prevents a known node from silently drifting to an unreviewed hostname,
port, or transport. The real transport must still enforce DNS/IP/TLS and prove
the enrolled peer identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sofia.distributed.model import NodeEndpoint


@dataclass(frozen=True, slots=True)
class ApprovedEndpoint:
    node_id: UUID
    endpoint: NodeEndpoint
    approved_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, UUID):
            raise TypeError("node_id must be a UUID")
        if not isinstance(self.endpoint, NodeEndpoint):
            raise TypeError("endpoint must be a NodeEndpoint")
        if not isinstance(self.approved_by, str) or not self.approved_by.strip():
            raise ValueError("approved_by must identify the human approver")


class EndpointPolicy:
    """Append-only exact endpoint approvals with explicit revocation."""

    def __init__(self) -> None:
        self._approved: dict[UUID, ApprovedEndpoint] = {}

    def approve(self, approval: ApprovedEndpoint) -> None:
        if not isinstance(approval, ApprovedEndpoint):
            raise TypeError("approval must be an ApprovedEndpoint")
        if approval.node_id in self._approved:
            raise ValueError("node already has an endpoint approval; revoke before replacing")
        self._approved[approval.node_id] = approval

    def revoke(self, node_id: UUID) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        self._approved.pop(node_id, None)

    def permits(self, node_id: UUID, endpoint: NodeEndpoint) -> bool:
        if not isinstance(node_id, UUID) or not isinstance(endpoint, NodeEndpoint):
            return False
        approval = self._approved.get(node_id)
        return bool(approval is not None and approval.endpoint == endpoint)
