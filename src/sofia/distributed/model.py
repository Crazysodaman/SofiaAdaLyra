"""Batch 22A: immutable evidence contracts for known remote machines.

Identity is assigned independently of hostnames, addresses, network status,
and Sofía's runtime ID. No object here grants authority or executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from re import fullmatch
from uuid import UUID




class NodeTransport(str, Enum):
    SSH = "ssh"
    HTTPS = "https"
    OTHER = "other"


@dataclass(frozen=True)
class DistributedNode:
    """A provisioned node, not a discovery result or an authorization."""

    node_id: UUID
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, UUID):
            raise TypeError("DistributedNode node_id must be a UUID.")
        if not isinstance(self.name, str):
            raise TypeError("DistributedNode name must be a string.")
        if not self.name.strip():
            raise ValueError("DistributedNode name must not be empty.")


@dataclass(frozen=True)
class NodeEndpoint:
    """A location hint, never proof of identity, trust, or authority."""

    hostname: str
    port: int
    transport: NodeTransport

    def __post_init__(self) -> None:
        if not isinstance(self.hostname, str):
            raise TypeError("NodeEndpoint hostname must be a string.")
        if not self.hostname.strip():
            raise ValueError("NodeEndpoint hostname must not be empty.")
        if type(self.port) is not int or not (1 <= self.port <= 65535):
            raise ValueError("NodeEndpoint port must be between 1 and 65535.")
        if not isinstance(self.transport, NodeTransport):
            raise TypeError("NodeEndpoint transport must be a NodeTransport.")


@dataclass(frozen=True)
class NodeEnrollment:
    """Human-provisioned ID/key pin, not a verified remote session."""

    node: DistributedNode
    public_key_sha256: str
    provisioned_at: datetime
    recorded_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.node, DistributedNode):
            raise TypeError("NodeEnrollment node must be a DistributedNode.")
        if not isinstance(self.public_key_sha256, str):
            raise TypeError("NodeEnrollment public_key_sha256 must be a string.")
        if fullmatch(r"[0-9a-f]{64}", self.public_key_sha256) is None:
            raise ValueError("NodeEnrollment requires a lowercase SHA-256 hex pin.")
        if not isinstance(self.provisioned_at, datetime):
            raise TypeError("NodeEnrollment provisioned_at must be a datetime.")
        if (self.provisioned_at.tzinfo is None
                or self.provisioned_at.utcoffset() is None):
            raise ValueError("NodeEnrollment provisioned_at must be timezone-aware.")
        if not isinstance(self.recorded_by, str):
            raise TypeError("NodeEnrollment recorded_by must be a string.")
        if not self.recorded_by.strip():
            raise ValueError("NodeEnrollment recorded_by must not be empty.")


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
