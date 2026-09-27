"""Bounded Fleet agent bootstrap planning and execution.

Discovery/reachability does not imply install authority. An installed agent is
not enrollment-ready merely because it reports the expected version: exact
artifact identity and protocol compatibility require independently verified
evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from re import fullmatch
from typing import Protocol

from sofia.ops.protocol import FleetProtocolVersion, FleetProtocolWindow


class InstallAuthority(str, Enum):
    NONE = "none"
    OPERATOR_APPROVED = "operator_approved"
    STANDING_POLICY = "standing_policy"


class BootstrapDisposition(str, Enum):
    READY_FOR_ENROLLMENT = "ready_for_enrollment"
    AUTO_INSTALL = "auto_install"
    ASK_OPERATOR = "ask_operator"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AgentPackage:
    package_id: str
    version: str
    sha256: str
    source: str
    protocol: FleetProtocolVersion = FleetProtocolVersion(1, 0)

    def __post_init__(self) -> None:
        if not self.package_id.strip() or not self.version.strip() or not self.source.strip():
            raise ValueError("agent package identity, version and source required")
        if fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("agent package requires lowercase SHA-256")
        if not isinstance(self.protocol, FleetProtocolVersion):
            raise TypeError("agent package protocol must be FleetProtocolVersion")


@dataclass(frozen=True)
class InstalledAgentEvidence:
    """Independent observation of the bytes and protocol actually installed."""

    package_id: str
    version: str
    sha256: str
    protocol: FleetProtocolVersion
    observed_at: datetime
    verifier: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.package_id.strip() or not self.version.strip():
            raise ValueError("installed agent identity and version required")
        if fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("installed agent requires lowercase SHA-256")
        if not isinstance(self.protocol, FleetProtocolVersion):
            raise TypeError("installed agent protocol must be FleetProtocolVersion")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("installed agent observation must be timezone-aware")
        if not isinstance(self.verifier, str) or not self.verifier.strip():
            raise ValueError("independent installed-agent verifier required")
        if not isinstance(self.verified, bool):
            raise TypeError("installed agent verified must be boolean")

    def matches(
        self,
        package: AgentPackage,
        *,
        controller_protocol: FleetProtocolWindow,
    ) -> bool:
        if not isinstance(package, AgentPackage):
            raise TypeError("AgentPackage required")
        if not isinstance(controller_protocol, FleetProtocolWindow):
            raise TypeError("FleetProtocolWindow required")
        return (
            self.verified is True
            and self.package_id == package.package_id
            and self.version == package.version
            and self.sha256 == package.sha256
            and self.protocol == package.protocol
            and controller_protocol.accepts(self.protocol)
        )


@dataclass(frozen=True)
class BootstrapCandidate:
    host_id: str
    platform: str
    architecture: str
    discovery_source: str
    inside_approved_scope: bool
    trusted_bootstrap_available: bool
    installed_agent_version: str | None = None
    installed_agent_evidence: InstalledAgentEvidence | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.host_id, self.platform, self.architecture, self.discovery_source)
        ):
            raise ValueError("candidate identity/platform/source required")
        if not isinstance(self.inside_approved_scope, bool):
            raise TypeError("inside_approved_scope must be boolean")
        if not isinstance(self.trusted_bootstrap_available, bool):
            raise TypeError("trusted_bootstrap_available must be boolean")
        if self.installed_agent_version is not None and (
            not isinstance(self.installed_agent_version, str)
            or not self.installed_agent_version.strip()
        ):
            raise ValueError("installed_agent_version must be nonempty when set")
        if self.installed_agent_evidence is not None:
            if not isinstance(
                self.installed_agent_evidence,
                InstalledAgentEvidence,
            ):
                raise TypeError(
                    "installed_agent_evidence must be InstalledAgentEvidence"
                )
            if (
                self.installed_agent_version is not None
                and self.installed_agent_version
                != self.installed_agent_evidence.version
            ):
                raise ValueError(
                    "reported installed version conflicts with attested evidence"
                )

    @property
    def observed_agent_version(self) -> str | None:
        if self.installed_agent_evidence is not None:
            return self.installed_agent_evidence.version
        return self.installed_agent_version


@dataclass(frozen=True)
class BootstrapPlan:
    candidate: BootstrapCandidate
    package: AgentPackage
    disposition: BootstrapDisposition
    reason: str
    operator_message: str | None = None


@dataclass(frozen=True)
class InstallReceipt:
    host_id: str
    package_id: str
    version: str
    sha256: str
    verified: bool
    protocol: FleetProtocolVersion = FleetProtocolVersion(1, 0)
    verifier: str = "installer"

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, FleetProtocolVersion):
            raise TypeError("receipt protocol must be FleetProtocolVersion")
        if not isinstance(self.verifier, str) or not self.verifier.strip():
            raise ValueError("receipt verifier required")


class AgentInstaller(Protocol):
    def install(self, candidate: BootstrapCandidate, package: AgentPackage) -> InstallReceipt: ...


class FleetBootstrapPlanner:
    def plan(
        self,
        candidate: BootstrapCandidate,
        package: AgentPackage,
        *,
        authority: InstallAuthority,
        controller_protocol: FleetProtocolWindow = FleetProtocolWindow(
            FleetProtocolVersion(1, 0),
            FleetProtocolVersion(1, 0),
        ),
    ) -> BootstrapPlan:
        if not isinstance(candidate, BootstrapCandidate):
            raise TypeError("BootstrapCandidate required")
        if not isinstance(package, AgentPackage):
            raise TypeError("AgentPackage required")
        if not isinstance(authority, InstallAuthority):
            raise TypeError("InstallAuthority required")
        if not isinstance(controller_protocol, FleetProtocolWindow):
            raise TypeError("FleetProtocolWindow required")

        if not candidate.inside_approved_scope:
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.REJECTED,
                "candidate is outside approved discovery/bootstrap scope",
            )

        evidence = candidate.installed_agent_evidence
        if (
            evidence is not None
            and evidence.matches(
                package,
                controller_protocol=controller_protocol,
            )
        ):
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.READY_FOR_ENROLLMENT,
                "installed Fleet agent artifact and protocol are independently verified",
            )

        if not controller_protocol.accepts(package.protocol):
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.REJECTED,
                "approved Fleet agent package is protocol-incompatible with controller",
            )

        if (
            candidate.trusted_bootstrap_available
            and authority in (
                InstallAuthority.OPERATOR_APPROVED,
                InstallAuthority.STANDING_POLICY,
            )
        ):
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.AUTO_INSTALL,
                (
                    "trusted bootstrap path and explicit install authority are "
                    "present; install/repair is required before enrollment"
                ),
            )

        current = (
            f"current agent {candidate.observed_agent_version}"
            if candidate.observed_agent_version
            else "no independently verified Fleet agent"
        )
        return BootstrapPlan(
            candidate,
            package,
            BootstrapDisposition.ASK_OPERATOR,
            (
                "automatic installation lacks a trusted authorized bootstrap "
                "path or the installed artifact lacks independent attestation"
            ),
            (
                f"{candidate.host_id} has {current}. Install/authorize "
                f"{package.package_id} {package.version} from {package.source}, "
                "then Sofía can independently verify its digest/protocol and enroll."
            ),
        )


class FleetBootstrapExecutor:
    """Execute only an AUTO_INSTALL plan through a typed installer boundary."""

    def execute(
        self,
        plan: BootstrapPlan,
        installer: AgentInstaller,
    ) -> InstallReceipt:
        if not isinstance(plan, BootstrapPlan):
            raise TypeError("BootstrapPlan required")
        if plan.disposition is not BootstrapDisposition.AUTO_INSTALL:
            raise PermissionError(
                "bootstrap plan does not authorize automatic installation"
            )
        receipt = installer.install(plan.candidate, plan.package)
        if not isinstance(receipt, InstallReceipt):
            raise TypeError("installer must return InstallReceipt")
        if (
            receipt.host_id != plan.candidate.host_id
            or receipt.package_id != plan.package.package_id
            or receipt.version != plan.package.version
            or receipt.sha256 != plan.package.sha256
            or receipt.protocol != plan.package.protocol
            or receipt.verified is not True
        ):
            raise RuntimeError(
                "installed Fleet agent did not verify against the approved package"
            )
        return receipt
