"""Authenticated-evidence bridge from NET enrollment into OPS fleet trust."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from re import fullmatch
from uuid import UUID

from sofia.distributed.identity import NodeEnrollment
from sofia.ops.bootstrap import AgentPackage, InstalledAgentEvidence
from sofia.ops.protocol import FleetProtocolWindow

from .fleet import FleetRegistry
from .model import FleetHost, HostLifecycle


@dataclass(frozen=True)
class MachineNodeBinding:
    host_id: str
    node_id: UUID
    verified_at: datetime
    source: str

    def __post_init__(self):
        if not self.host_id.strip() or not self.source.strip():
            raise ValueError("machine/node binding evidence required")
        if self.verified_at.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware")


@dataclass(frozen=True)
class AuthenticatedPeerEvidence:
    node_id: UUID
    public_key_sha256: str
    observed_at: datetime
    verifier: str

    def __post_init__(self):
        if fullmatch(r"[0-9a-f]{64}", self.public_key_sha256) is None:
            raise ValueError(
                "peer key fingerprint must be lowercase SHA-256"
            )
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.verifier.strip():
            raise ValueError("independent verifier identity required")


class FleetEnrollmentService:
    def __init__(self, registry: FleetRegistry) -> None:
        self.registry = registry

    def enroll(
        self,
        candidate: FleetHost,
        *,
        binding: MachineNodeBinding,
        enrollment: NodeEnrollment,
        peer: AuthenticatedPeerEvidence,
        agent: InstalledAgentEvidence,
        approved_package: AgentPackage,
        controller_protocol: FleetProtocolWindow,
    ) -> FleetHost:
        if candidate.lifecycle is not HostLifecycle.CANDIDATE:
            raise ValueError("fleet enrollment starts from a candidate")
        if candidate.trusted:
            raise ValueError(
                "candidate must enter authenticated enrollment untrusted"
            )
        if candidate.host_id != binding.host_id:
            raise PermissionError("binding is for a different machine")
        if (
            binding.node_id != enrollment.node.node_id
            or peer.node_id != enrollment.node.node_id
        ):
            raise PermissionError(
                "machine binding, enrollment and authenticated peer disagree"
            )
        if peer.public_key_sha256 != enrollment.public_key_sha256:
            raise PermissionError(
                "authenticated peer key does not match enrolled key pin"
            )
        if not isinstance(agent, InstalledAgentEvidence):
            raise TypeError("InstalledAgentEvidence required")
        if not isinstance(approved_package, AgentPackage):
            raise TypeError("AgentPackage required")
        if not isinstance(controller_protocol, FleetProtocolWindow):
            raise TypeError("FleetProtocolWindow required")
        if not agent.matches(
            approved_package,
            controller_protocol=controller_protocol,
        ):
            raise PermissionError(
                "installed Fleet agent is not independently attested to the "
                "approved artifact/protocol"
            )

        trusted = replace(candidate, trusted=True)
        self.registry.register_candidate(trusted)
        return self.registry.transition(
            trusted.host_id,
            HostLifecycle.ENROLLED,
        )
