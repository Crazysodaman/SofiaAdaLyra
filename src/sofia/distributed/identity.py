"""Batch 22B: in-memory node enrollment and public-key pin comparison.

An enrolled ID and matching hash are not authenticated peer identity.
The bytes presented for comparison must come from a separately authenticated
transport/proof-of-possession mechanism, which this module does NOT provide.
Enrollment itself grants no network access, capability, or authorization.
No secret or private key is stored. Persistence and rotation are future work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from re import fullmatch
from uuid import UUID

from sofia.distributed.model import DistributedNode


def fingerprint_public_key(public_key: bytes) -> str:
    """Hash public-key bytes; hashing alone does not authenticate a peer."""
    if type(public_key) is not bytes:
        raise TypeError("Public key must be immutable bytes.")
    if not public_key:
        raise ValueError("Public key must not be empty.")
    return sha256(public_key).hexdigest()


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


class NodeIdentityRegistry:
    """In-memory, append-only pins; not discovery, authentication or authority."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, NodeEnrollment] = {}
        self._ids_by_pin: dict[str, UUID] = {}

    def enroll(self, enrollment: NodeEnrollment) -> None:
        if not isinstance(enrollment, NodeEnrollment):
            raise TypeError("Enrollment must be a NodeEnrollment.")
        node_id = enrollment.node.node_id
        if node_id in self._by_id:
            raise ValueError("Node ID is already enrolled; implicit rotation is forbidden.")
        if enrollment.public_key_sha256 in self._ids_by_pin:
            raise ValueError("Public-key pin is already bound to another node.")
        self._by_id[node_id] = enrollment
        self._ids_by_pin[enrollment.public_key_sha256] = node_id

    def get(self, node_id: UUID) -> NodeEnrollment | None:
        if not isinstance(node_id, UUID):
            raise TypeError("Node ID must be a UUID.")
        return self._by_id.get(node_id)

    def matches_pinned_public_key(self, node_id: UUID, presented_key: bytes) -> bool:
        """Compare a pin only. This does NOT prove possession or identity."""
        enrollment = self.get(node_id)
        digest = fingerprint_public_key(presented_key)
        if enrollment is None:
            return False
        return compare_digest(enrollment.public_key_sha256, digest)
