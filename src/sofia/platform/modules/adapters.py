"""Trusted, non-discovering adapter reconstruction for signed modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import re

from sofia.platform.capability.model import Capability
from sofia.platform.capability.system import CapabilityHandler
from sofia.platform.run.supervisor import ManagedRuntimeBackend, ProcessState

from .compatibility import ModulePlatformTarget
from .package import OperationProfileKind, VerifiedModulePackage


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AdapterFactoryContract:
    factory_id: str
    module_id: str
    package_digests: frozenset[str]
    component_ids: frozenset[str]
    interface_versions: tuple[str, ...]
    profiles: frozenset[OperationProfileKind]
    required_permissions: frozenset[str]
    isolation_profile: str
    resource_requirements: tuple[tuple[str, int], ...]
    host_bindings: frozenset[str]
    device_bindings: frozenset[str]
    safe_inspection: bool
    safe_shutdown: bool
    start_effect_replay_safe: bool

    def __post_init__(self) -> None:
        for label, value in (
            ("factory_id", self.factory_id),
            ("module_id", self.module_id),
            ("isolation_profile", self.isolation_profile),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if not self.package_digests or any(
            _DIGEST.fullmatch(item) is None for item in self.package_digests
        ):
            raise ValueError("exact compatible package digests required")
        for label, values in (
            ("component_ids", self.component_ids),
            ("required_permissions", self.required_permissions),
            ("host_bindings", self.host_bindings),
            ("device_bindings", self.device_bindings),
        ):
            if not isinstance(values, frozenset) or any(
                not isinstance(item, str) or _ID.fullmatch(item) is None
                for item in values
            ):
                raise ValueError(f"{label} must be bounded identifiers")
        if not self.component_ids:
            raise ValueError("at least one component contract is required")
        if not self.interface_versions or any(
            not isinstance(item, str) or not item.strip()
            for item in self.interface_versions
        ):
            raise ValueError("interface versions required")
        if not self.profiles or any(
            not isinstance(item, OperationProfileKind) for item in self.profiles
        ):
            raise ValueError("operation profiles required")
        if any(
            not isinstance(name, str) or not name
            or type(amount) is not int or amount < 0
            for name, amount in self.resource_requirements
        ):
            raise ValueError("resource requirements must be nonnegative pairs")
        for field in ("safe_inspection", "safe_shutdown", "start_effect_replay_safe"):
            if type(getattr(self, field)) is not bool:
                raise TypeError(f"{field} must be bool")


@dataclass(frozen=True, slots=True)
class AdapterInspection:
    module_id: str
    package_digest: str
    component_id: str
    host_identity: str
    state: ProcessState
    ready: bool
    evidence_ref: str
    observed_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("module_id", self.module_id),
            ("component_id", self.component_id),
            ("host_identity", self.host_identity),
            ("evidence_ref", self.evidence_ref),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if _DIGEST.fullmatch(self.package_digest) is None:
            raise ValueError("package_digest must be SHA-256")
        if not isinstance(self.state, ProcessState):
            raise TypeError("state must be ProcessState")
        if type(self.ready) is not bool or (
            self.ready and self.state is not ProcessState.RUNNING
        ):
            raise ValueError("only a running component may be ready")
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")


class ReviewedModuleAdapter(ManagedRuntimeBackend, ABC):
    """Host-created adapter; reconstruction and inspection must be effect-free."""

    @abstractmethod
    def inspect(self) -> AdapterInspection:
        raise NotImplementedError

    @abstractmethod
    def capability_registrations(
        self,
    ) -> tuple[tuple[Capability, CapabilityHandler], ...]:
        raise NotImplementedError


class ReviewedAdapterFactory(ABC):
    @property
    @abstractmethod
    def contract(self) -> AdapterFactoryContract:
        raise NotImplementedError

    @property
    @abstractmethod
    def platform_target(self) -> ModulePlatformTarget:
        raise NotImplementedError

    @abstractmethod
    def reconstruct_for_inspection(
        self, *, package: VerifiedModulePackage,
        profile: OperationProfileKind, component_id: str, host_identity: str,
    ) -> ReviewedModuleAdapter:
        """Build an inert adapter object; it must not start an external effect."""
        raise NotImplementedError


class AdapterFactoryRegistry:
    """In-memory trusted-construction registry; never scans or imports packages."""

    def __init__(self) -> None:
        self._factories: dict[str, ReviewedAdapterFactory] = {}

    def register(self, factory: ReviewedAdapterFactory) -> None:
        if not isinstance(factory, ReviewedAdapterFactory):
            raise TypeError("factory must implement ReviewedAdapterFactory")
        contract = factory.contract
        if contract.factory_id in self._factories:
            if self._factories[contract.factory_id] is factory:
                return
            raise ValueError("adapter factory identity already registered")
        self._factories[contract.factory_id] = factory

    def contracts(self) -> tuple[AdapterFactoryContract, ...]:
        return tuple(
            self._factories[key].contract for key in sorted(self._factories)
        )

    def resolve(
        self, *, module_id: str, package_digest: str,
        profile: OperationProfileKind, component_id: str,
        host_identity: str,
    ) -> ReviewedAdapterFactory:
        matches = []
        for factory in self._factories.values():
            contract = factory.contract
            if (
                contract.module_id == module_id
                and package_digest in contract.package_digests
                and component_id in contract.component_ids
                and profile in contract.profiles
                and (not contract.host_bindings or host_identity in contract.host_bindings)
            ):
                matches.append(factory)
        if not matches:
            raise LookupError("no reviewed adapter factory matches exact module context")
        if len(matches) != 1:
            raise RuntimeError("adapter factory ownership is ambiguous")
        return matches[0]
