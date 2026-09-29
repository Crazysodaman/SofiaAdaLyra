"""Bounded Fleet agent bootstrap planning and execution.

Discovery/reachability does not imply install authority. Automatic install is
allowed only when an independently configured bootstrap path and standing or
operator-approved install authority are both present.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from re import fullmatch
from typing import Protocol

from sofia.distributed.version import FleetProtocolVersion


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
    protocol_version: str = "1.0"
    signer_key_id: str | None = None

    def __post_init__(self) -> None:
        if not self.package_id.strip() or not self.version.strip() or not self.source.strip():
            raise ValueError("agent package identity, version and source required")
        if fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("agent package requires lowercase SHA-256")
        FleetProtocolVersion.parse(self.protocol_version)
        if self.signer_key_id is not None and (
            not isinstance(self.signer_key_id, str)
            or not self.signer_key_id.strip()
        ):
            raise ValueError("signer_key_id must be None or nonempty")


@dataclass(frozen=True)
class BootstrapCandidate:
    host_id: str
    platform: str
    architecture: str
    discovery_source: str
    inside_approved_scope: bool
    trusted_bootstrap_available: bool
    installed_agent_version: str | None = None
    installed_agent_sha256: str | None = None
    installed_protocol_version: str | None = None
    installed_signer_key_id: str | None = None
    installed_signature_verified: bool = False
    agent_present: bool = False

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
        if self.installed_agent_sha256 is not None and fullmatch(
            r"[0-9a-f]{64}", self.installed_agent_sha256
        ) is None:
            raise ValueError("installed_agent_sha256 must be lowercase SHA-256")
        if self.installed_protocol_version is not None:
            FleetProtocolVersion.parse(self.installed_protocol_version)
        if self.installed_signer_key_id is not None and (
            not isinstance(self.installed_signer_key_id, str)
            or not self.installed_signer_key_id.strip()
        ):
            raise ValueError("installed_signer_key_id must be None or nonempty")
        if not isinstance(self.installed_signature_verified, bool):
            raise TypeError("installed_signature_verified must be boolean")
        if not isinstance(self.agent_present, bool):
            raise TypeError("agent_present must be boolean")


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
    protocol_version: str = "1.0"
    signer_key_id: str | None = None
    signature_verified: bool = False


class AgentInstaller(Protocol):
    def install(self, candidate: BootstrapCandidate, package: AgentPackage) -> InstallReceipt: ...


class FleetBootstrapPlanner:
    def plan(
        self,
        candidate: BootstrapCandidate,
        package: AgentPackage,
        *,
        authority: InstallAuthority,
    ) -> BootstrapPlan:
        if not isinstance(candidate, BootstrapCandidate):
            raise TypeError("BootstrapCandidate required")
        if not isinstance(package, AgentPackage):
            raise TypeError("AgentPackage required")
        if not isinstance(authority, InstallAuthority):
            raise TypeError("InstallAuthority required")

        if not candidate.inside_approved_scope:
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.REJECTED,
                "candidate is outside approved discovery/bootstrap scope",
            )

        installed_protocol_ok = False
        if candidate.installed_protocol_version is not None:
            installed_protocol_ok = FleetProtocolVersion.parse(
                candidate.installed_protocol_version
            ).compatible_with(
                FleetProtocolVersion.parse(package.protocol_version)
            )

        if candidate.agent_present and installed_protocol_ok:
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.READY_FOR_ENROLLMENT,
                (
                    "Fleet agent is already present with a compatible "
                    "protocol; package drift is a maintenance concern"
                ),
            )

        signer_ok = (
            package.signer_key_id is None
            or (
                candidate.installed_signature_verified
                and candidate.installed_signer_key_id == package.signer_key_id
            )
        )

        if (
            candidate.installed_agent_version == package.version
            and candidate.installed_agent_sha256 == package.sha256
            and installed_protocol_ok
            and signer_ok
        ):
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.READY_FOR_ENROLLMENT,
                "installed Fleet agent independently matches artifact and protocol",
            )

        if (
            candidate.trusted_bootstrap_available
            and authority in (InstallAuthority.OPERATOR_APPROVED, InstallAuthority.STANDING_POLICY)
        ):
            return BootstrapPlan(
                candidate,
                package,
                BootstrapDisposition.AUTO_INSTALL,
                "trusted bootstrap path and explicit install authority are present",
            )

        current = (
            f"current agent {candidate.installed_agent_version}"
            if candidate.installed_agent_version
            else "no Fleet agent"
        )
        return BootstrapPlan(
            candidate,
            package,
            BootstrapDisposition.ASK_OPERATOR,
            "automatic installation lacks a trusted authorized bootstrap path",
            (
                f"{candidate.host_id} has {current}. Install/authorize "
                f"{package.package_id} {package.version} from {package.source}, "
                "then Sofía can verify and enroll the machine."
            ),
        )


class FleetBootstrapExecutor:
    """Execute only an AUTO_INSTALL plan through a typed installer boundary."""

    def execute(self, plan: BootstrapPlan, installer: AgentInstaller) -> InstallReceipt:
        if not isinstance(plan, BootstrapPlan):
            raise TypeError("BootstrapPlan required")
        if plan.disposition is not BootstrapDisposition.AUTO_INSTALL:
            raise PermissionError("bootstrap plan does not authorize automatic installation")
        receipt = installer.install(plan.candidate, plan.package)
        if not isinstance(receipt, InstallReceipt):
            raise TypeError("installer must return InstallReceipt")
        if (
            receipt.host_id != plan.candidate.host_id
            or receipt.package_id != plan.package.package_id
            or receipt.version != plan.package.version
            or receipt.sha256 != plan.package.sha256
            or receipt.verified is not True
            or not FleetProtocolVersion.parse(
                receipt.protocol_version
            ).compatible_with(
                FleetProtocolVersion.parse(plan.package.protocol_version)
            )
            or (
                plan.package.signer_key_id is not None
                and (
                    receipt.signature_verified is not True
                    or receipt.signer_key_id != plan.package.signer_key_id
                )
            )
        ):
            raise RuntimeError("installed Fleet agent did not verify against the approved package")
        return receipt
