"""Bounded Fleet discovery evidence and candidate registration.

Discovery is observation only. It may create or refresh an UNTRUSTED candidate,
but it never enrolls, trusts, approves an endpoint, grants a capability, installs
software, or decommissions a host.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from re import fullmatch
from typing import Callable, Protocol
from uuid import UUID

from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import NodeEndpoint, NodeTransport
from sofia.ops.bootstrap import (
    AgentInstaller,
    AgentPackage,
    BootstrapCandidate,
    BootstrapDisposition,
    BootstrapPlan,
    FleetBootstrapExecutor,
    FleetBootstrapPlanner,
    InstallAuthority,
    InstallReceipt,
)
from sofia.ops.enrollment import (
    AuthenticatedPeerEvidence,
    FleetEnrollmentService,
    MachineNodeBinding,
)
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
    observed_node_id: UUID | None = None
    observed_public_key_sha256: str | None = None
    observed_endpoint_hostname: str | None = None
    observed_endpoint_port: int | None = None

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
        if self.observed_node_id is not None and not isinstance(
            self.observed_node_id,
            UUID,
        ):
            raise TypeError("observed_node_id must be UUID or None")
        if self.observed_public_key_sha256 is not None and fullmatch(
            r"[0-9a-f]{64}",
            self.observed_public_key_sha256,
        ) is None:
            raise ValueError(
                "observed_public_key_sha256 must be lowercase SHA-256"
            )
        if self.observed_endpoint_hostname is not None and (
            not isinstance(self.observed_endpoint_hostname, str)
            or not self.observed_endpoint_hostname.strip()
        ):
            raise ValueError(
                "observed_endpoint_hostname must be nonempty or None"
            )
        if self.observed_endpoint_port is not None and (
            type(self.observed_endpoint_port) is not int
            or not 1 <= self.observed_endpoint_port <= 65535
        ):
            raise ValueError(
                "observed_endpoint_port must be in 1..65535 or None"
            )

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
            agent_present=(
                self.observed_node_id is not None
                and self.observed_public_key_sha256 is not None
            ),
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

    def __init__(
        self,
        registry,
        *,
        candidate_notifier: Callable[
            [FleetHost, FleetDiscoveryEvidence],
            None,
        ] | None = None,
    ) -> None:
        if not hasattr(registry, "host") or not hasattr(registry, "register_candidate"):
            raise TypeError("registry must support host() and register_candidate()")
        if candidate_notifier is not None and not callable(candidate_notifier):
            raise TypeError("candidate_notifier must be callable or None")
        self.registry = registry
        self.candidate_notifier = candidate_notifier

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

            tags = tuple(
                value
                for value in (
                    "discovered",
                    f"source:{observation.source}",
                    f"hostname:{observation.hostname}",
                    (
                        "observed-node:"
                        f"{observation.observed_node_id}"
                        if observation.observed_node_id is not None
                        else None
                    ),
                    (
                        "observed-key:"
                        f"{observation.observed_public_key_sha256}"
                        if observation.observed_public_key_sha256
                        else None
                    ),
                )
                if value is not None
            )
            known = self.registry.host(observation.host_id)
            if known is not None:
                platform_matches = (
                    known.platform.casefold()
                    == observation.platform.casefold()
                )
                architecture_matches = (
                    known.architecture.casefold()
                    == observation.architecture.casefold()
                )
                can_refine = (
                    known.lifecycle is HostLifecycle.CANDIDATE
                    and not known.trusted
                    and (
                        known.platform.casefold() == "unknown"
                        or platform_matches
                    )
                    and (
                        known.architecture.casefold() == "unknown"
                        or architecture_matches
                    )
                )
                if not platform_matches or not architecture_matches:
                    if not can_refine:
                        raise ValueError(
                            f"discovery conflicts with durable Fleet identity: "
                            f"{observation.host_id}"
                        )
                    self.registry.refine_candidate_identity(
                        observation.host_id,
                        platform=observation.platform,
                        architecture=observation.architecture,
                        tags=tags,
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
                tags=tags,
                node_id=None,
            )
            self.registry.register_candidate(candidate)
            created.append(observation.host_id)
            if self.candidate_notifier is not None:
                self.candidate_notifier(candidate, observation)

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


@dataclass(frozen=True, slots=True)
class FleetDiscoveryEnrollmentResult:
    enrolled_host_ids: tuple[str, ...]
    pending_host_ids: tuple[str, ...]


class FleetDiscoveryEnrollmentReconciler:
    """Enroll only candidates whose discovered identity matches preapproved state."""

    def __init__(
        self,
        *,
        enrollment_service: FleetEnrollmentService,
        identity_registry: DurableNodeIdentityRegistry,
        endpoint_policy: DurableEndpointPolicy,
    ) -> None:
        if not isinstance(enrollment_service, FleetEnrollmentService):
            raise TypeError("enrollment_service must be FleetEnrollmentService")
        if not isinstance(identity_registry, DurableNodeIdentityRegistry):
            raise TypeError(
                "identity_registry must be DurableNodeIdentityRegistry"
            )
        if not isinstance(endpoint_policy, DurableEndpointPolicy):
            raise TypeError("endpoint_policy must be DurableEndpointPolicy")
        self.enrollment_service = enrollment_service
        self.identity_registry = identity_registry
        self.endpoint_policy = endpoint_policy

    def reconcile(
        self,
        discovery: FleetDiscoveryResult,
    ) -> FleetDiscoveryEnrollmentResult:
        if not isinstance(discovery, FleetDiscoveryResult):
            raise TypeError("discovery must be FleetDiscoveryResult")
        enrolled = []
        pending = []

        for observation in discovery.observed:
            host = self.enrollment_service.registry.host(
                observation.host_id
            )
            if (
                host is None
                or host.lifecycle is not HostLifecycle.CANDIDATE
                or host.trusted
                or observation.observed_node_id is None
                or not observation.observed_public_key_sha256
                or not observation.observed_endpoint_hostname
                or observation.observed_endpoint_port is None
            ):
                if host is not None and host.lifecycle is HostLifecycle.CANDIDATE:
                    pending.append(observation.host_id)
                continue

            enrollment = self.identity_registry.get(
                observation.observed_node_id
            )
            if (
                enrollment is None
                or enrollment.public_key_sha256
                != observation.observed_public_key_sha256
            ):
                pending.append(observation.host_id)
                continue

            endpoint = NodeEndpoint(
                observation.observed_endpoint_hostname,
                observation.observed_endpoint_port,
                NodeTransport.HTTPS,
            )
            if not self.endpoint_policy.permits(
                observation.observed_node_id,
                endpoint,
            ):
                pending.append(observation.host_id)
                continue

            binding = MachineNodeBinding(
                host_id=observation.host_id,
                node_id=observation.observed_node_id,
                verified_at=observation.observed_at,
                source=observation.source,
            )
            peer = AuthenticatedPeerEvidence(
                node_id=observation.observed_node_id,
                public_key_sha256=observation.observed_public_key_sha256,
                observed_at=observation.observed_at,
                verifier="mtls-agent-discovery",
            )
            self.enrollment_service.enroll(
                host,
                binding=binding,
                enrollment=enrollment,
                peer=peer,
            )
            enrolled.append(observation.host_id)

        return FleetDiscoveryEnrollmentResult(
            enrolled_host_ids=tuple(sorted(set(enrolled))),
            pending_host_ids=tuple(sorted(set(pending))),
        )



@dataclass(frozen=True, slots=True)
class FleetDiscoveryBootstrapResult:
    plans: tuple[BootstrapPlan, ...]
    receipts: tuple[InstallReceipt, ...]
    ready_host_ids: tuple[str, ...]
    installed_host_ids: tuple[str, ...]
    operator_host_ids: tuple[str, ...]
    rejected_host_ids: tuple[str, ...]


class FleetDiscoveryBootstrapCoordinator:
    """Plan bootstrap for discovered candidates and execute only typed authority."""

    def __init__(
        self,
        *,
        package: AgentPackage,
        authority: InstallAuthority,
        installer_factory: Callable[
            [FleetDiscoveryEvidence],
            AgentInstaller | None,
        ] | None = None,
        operator_notifier: Callable[[BootstrapPlan], None] | None = None,
    ) -> None:
        if not isinstance(package, AgentPackage):
            raise TypeError("package must be AgentPackage")
        if not isinstance(authority, InstallAuthority):
            raise TypeError("authority must be InstallAuthority")
        if installer_factory is not None and not callable(installer_factory):
            raise TypeError("installer_factory must be callable or None")
        if operator_notifier is not None and not callable(operator_notifier):
            raise TypeError("operator_notifier must be callable or None")
        self.package = package
        self.authority = authority
        self.installer_factory = installer_factory
        self.operator_notifier = operator_notifier
        self.planner = FleetBootstrapPlanner()
        self.executor = FleetBootstrapExecutor()

    def reconcile(
        self,
        discovery: FleetDiscoveryResult,
    ) -> FleetDiscoveryBootstrapResult:
        if not isinstance(discovery, FleetDiscoveryResult):
            raise TypeError("discovery must be FleetDiscoveryResult")
        plans = []
        receipts = []
        ready = []
        installed = []
        operator = []
        rejected = []

        for observation in discovery.observed:
            plan = self.planner.plan(
                observation.bootstrap_candidate(),
                self.package,
                authority=self.authority,
            )
            plans.append(plan)

            if plan.disposition is BootstrapDisposition.READY_FOR_ENROLLMENT:
                ready.append(observation.host_id)
                continue

            if plan.disposition is BootstrapDisposition.REJECTED:
                rejected.append(observation.host_id)
                continue

            if plan.disposition is BootstrapDisposition.ASK_OPERATOR:
                operator.append(observation.host_id)
                if self.operator_notifier is not None:
                    self.operator_notifier(plan)
                continue

            if plan.disposition is BootstrapDisposition.AUTO_INSTALL:
                if self.installer_factory is None:
                    # A standing policy without a concrete typed installer is
                    # not sufficient execution authority. Surface it instead.
                    operator.append(observation.host_id)
                    if self.operator_notifier is not None:
                        self.operator_notifier(
                            BootstrapPlan(
                                plan.candidate,
                                plan.package,
                                BootstrapDisposition.ASK_OPERATOR,
                                (
                                    "automatic bootstrap is authorized in policy "
                                    "but no trusted installer is configured"
                                ),
                                plan.operator_message
                                or (
                                    f"{observation.host_id} needs a configured "
                                    "trusted bootstrap installer."
                                ),
                            )
                        )
                    continue
                installer = self.installer_factory(observation)
                if installer is None:
                    operator.append(observation.host_id)
                    if self.operator_notifier is not None:
                        self.operator_notifier(
                            BootstrapPlan(
                                plan.candidate,
                                plan.package,
                                BootstrapDisposition.ASK_OPERATOR,
                                (
                                    "trusted installer factory did not provide "
                                    "an installer for this candidate"
                                ),
                                (
                                    f"{observation.host_id} requires operator "
                                    "bootstrap or installer configuration."
                                ),
                            )
                        )
                    continue
                receipt = self.executor.execute(plan, installer)
                receipts.append(receipt)
                installed.append(observation.host_id)

        return FleetDiscoveryBootstrapResult(
            plans=tuple(plans),
            receipts=tuple(receipts),
            ready_host_ids=tuple(sorted(set(ready))),
            installed_host_ids=tuple(sorted(set(installed))),
            operator_host_ids=tuple(sorted(set(operator))),
            rejected_host_ids=tuple(sorted(set(rejected))),
        )
