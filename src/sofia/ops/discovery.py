"""Bounded Fleet discovery evidence and candidate registration.

Discovery is observation only. It may create or refresh an UNTRUSTED candidate,
but it never enrolls, trusts, approves an endpoint, grants a capability, installs
software, or decommissions a host.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sofia.ops.bootstrap import BootstrapCandidate
from sofia.ops.model import FleetHost, HostLifecycle


@dataclass(frozen=True, slots=True)
class FleetDiscoveryEvidence:
    host_id: str
    hostname: str
    platform: str
    architecture: str
    observed_at: datetime
    source: str
    inside_approved_scope: bool
    trusted_bootstrap_available: bool = False
    installed_agent_version: str | None = None
    installed_agent_sha256: str | None = None
    installed_protocol_version: str | None = None
    installed_signer_key_id: str | None = None
    installed_signature_verified: bool = False

    def __post_init__(self) -> None:
        for name in (
            "host_id",
            "hostname",
            "platform",
            "architecture",
            "source",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if type(self.inside_approved_scope) is not bool:
            raise TypeError("inside_approved_scope must be boolean")
        if type(self.trusted_bootstrap_available) is not bool:
            raise TypeError("trusted_bootstrap_available must be boolean")
        if type(self.installed_signature_verified) is not bool:
            raise TypeError("installed_signature_verified must be boolean")

    def bootstrap_candidate(self) -> BootstrapCandidate:
        return BootstrapCandidate(
            host_id=self.host_id,
            platform=self.platform,
            architecture=self.architecture,
            discovery_source=self.source,
            inside_approved_scope=self.inside_approved_scope,
            trusted_bootstrap_available=self.trusted_bootstrap_available,
            installed_agent_version=self.installed_agent_version,
            installed_agent_sha256=self.installed_agent_sha256,
            installed_protocol_version=self.installed_protocol_version,
            installed_signer_key_id=self.installed_signer_key_id,
            installed_signature_verified=self.installed_signature_verified,
        )


class FleetDiscoverySource(Protocol):
    def discover(self) -> tuple[FleetDiscoveryEvidence, ...]: ...


@dataclass(frozen=True, slots=True)
class FleetDiscoveryResult:
    observed: tuple[FleetDiscoveryEvidence, ...]
    created_host_ids: tuple[str, ...]
    existing_host_ids: tuple[str, ...]
    rejected_host_ids: tuple[str, ...]


class FleetDiscoveryCoordinator:
    """Convert bounded observations into durable untrusted Fleet candidates."""

    def __init__(self, registry) -> None:
        if not hasattr(registry, "host") or not hasattr(registry, "register_candidate"):
            raise TypeError("registry must support host() and register_candidate()")
        self.registry = registry

    def ingest(
        self,
        observations: tuple[FleetDiscoveryEvidence, ...],
    ) -> FleetDiscoveryResult:
        if not isinstance(observations, tuple):
            raise TypeError("observations must be a tuple")
        created = []
        existing = []
        rejected = []
        seen: dict[str, FleetDiscoveryEvidence] = {}

        for observation in observations:
            if not isinstance(observation, FleetDiscoveryEvidence):
                raise TypeError(
                    "observations must contain FleetDiscoveryEvidence"
                )
            previous = seen.get(observation.host_id)
            if previous is not None and (
                previous.hostname.casefold() != observation.hostname.casefold()
                or previous.platform.casefold() != observation.platform.casefold()
                or previous.architecture.casefold()
                != observation.architecture.casefold()
            ):
                raise ValueError(
                    f"conflicting discovery evidence for host_id={observation.host_id}"
                )
            seen[observation.host_id] = observation

        for observation in seen.values():
            if not observation.inside_approved_scope:
                rejected.append(observation.host_id)
                continue

            known = self.registry.host(observation.host_id)
            if known is not None:
                if (
                    known.platform.casefold() != observation.platform.casefold()
                    or known.architecture.casefold()
                    != observation.architecture.casefold()
                ):
                    raise ValueError(
                        f"discovery conflicts with durable Fleet identity: "
                        f"{observation.host_id}"
                    )
                existing.append(observation.host_id)
                continue

            candidate = FleetHost(
                host_id=observation.host_id,
                platform=observation.platform,
                architecture=observation.architecture,
                lifecycle=HostLifecycle.CANDIDATE,
                trusted=False,
                telemetry=None,
                tags=(
                    "discovered",
                    f"source:{observation.source}",
                    f"hostname:{observation.hostname}",
                ),
                node_id=None,
            )
            self.registry.register_candidate(candidate)
            created.append(observation.host_id)

        return FleetDiscoveryResult(
            observed=tuple(seen.values()),
            created_host_ids=tuple(sorted(created)),
            existing_host_ids=tuple(sorted(existing)),
            rejected_host_ids=tuple(sorted(rejected)),
        )

    def run(self, source: FleetDiscoverySource) -> FleetDiscoveryResult:
        if not hasattr(source, "discover") or not callable(source.discover):
            raise TypeError("source must provide discover()")
        observations = source.discover()
        return self.ingest(observations)
