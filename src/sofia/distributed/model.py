"""Batch 22A: immutable evidence contracts for known remote machines.

Identity is assigned independently of hostnames, addresses, network status,
and Sofía's runtime ID. No object here grants authority or executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class NodeReachability(str, Enum):
    UNKNOWN = "unknown"
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    DEGRADED = "degraded"


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
class NodeObservation:
    """Time-stamped reachability evidence for one *known* node.

    UNREACHABLE means an observed attempt failed; it is not a claim the
    machine is powered off. UNKNOWN is an explicit absence of a conclusion.
    Authentication and per-action authorization belong to later boundaries.
    """

    node_id: UUID
    observed_at: datetime
    source: str
    reachability: NodeReachability
    endpoint: NodeEndpoint | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, UUID):
            raise TypeError("NodeObservation node_id must be a UUID.")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("NodeObservation observed_at must be a datetime.")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("NodeObservation observed_at must be timezone-aware.")
        if not isinstance(self.source, str):
            raise TypeError("NodeObservation source must be a string.")
        if not self.source.strip():
            raise ValueError("NodeObservation source must not be empty.")
        if not isinstance(self.reachability, NodeReachability):
            raise TypeError("NodeObservation reachability must be a NodeReachability.")
        if self.endpoint is not None and not isinstance(self.endpoint, NodeEndpoint):
            raise TypeError("NodeObservation endpoint must be a NodeEndpoint or None.")
        if not isinstance(self.evidence, tuple):
            raise TypeError("NodeObservation evidence must be a tuple.")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("NodeObservation evidence must contain nonempty strings.")
        if self.reachability is not NodeReachability.UNKNOWN and not self.evidence:
            raise ValueError("An observed reachability conclusion requires evidence.")
