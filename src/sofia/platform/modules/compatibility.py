"""Deterministic compatibility admission for signed module packages."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import re
from datetime import datetime

from .package import OperationProfileKind, SignedModuleManifest
from sofia.platform.resources import (
    ResourceSupply,
    evaluate_resource_requirements,
)


_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_ASSESSMENT_TOKEN = object()


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise ValueError("platform API version must be semantic X.Y.Z")
    return tuple(int(item) for item in value.split("."))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ModulePlatformTarget:
    os_arch: str
    platform_api_version: str
    available_devices: tuple[str, ...]
    resource_capacity: tuple[tuple[str, int], ...]
    allowed_isolation_profiles: tuple[str, ...]
    resource_supply: ResourceSupply | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.os_arch, str) or not self.os_arch.strip():
            raise ValueError("os_arch required")
        _version(self.platform_api_version)
        for values, label in ((self.available_devices, "available_devices"),
                              (self.allowed_isolation_profiles, "isolation profiles")):
            if type(values) is not tuple or any(
                not isinstance(item, str) or not item for item in values
            ) or len(set(values)) != len(values):
                raise ValueError(f"{label} must be unique text")
        if type(self.resource_capacity) is not tuple or any(
            not isinstance(name, str) or not name or type(amount) is not int or amount < 0
            for name, amount in self.resource_capacity
        ) or len({name for name, _ in self.resource_capacity}) != len(self.resource_capacity):
            raise ValueError("resource_capacity must be unique nonnegative pairs")
        if self.resource_supply is not None and not isinstance(
            self.resource_supply, ResourceSupply
        ):
            raise TypeError("resource_supply must be ResourceSupply or None")


@dataclass(frozen=True, slots=True)
class ModuleCompatibilityReport:
    module_id: str
    version: str
    package_digest: str
    profile: OperationProfileKind
    target: ModulePlatformTarget
    compatible: bool
    reasons: tuple[str, ...]
    authoritative: bool = False
    _producer_token: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.authoritative != (self._producer_token is _ASSESSMENT_TOKEN):
            raise PermissionError(
                "authoritative compatibility requires the reviewed evaluator"
            )


def evaluate_module_compatibility(
    manifest: SignedModuleManifest, *, profile: OperationProfileKind,
    target: ModulePlatformTarget,
    installed_dependencies: tuple[SignedModuleManifest, ...] = (),
    now: datetime | None = None,
) -> ModuleCompatibilityReport:
    if not isinstance(manifest, SignedModuleManifest):
        raise TypeError("manifest must be SignedModuleManifest")
    if not isinstance(target, ModulePlatformTarget):
        raise TypeError("target must be ModulePlatformTarget")
    selected = next((item for item in manifest.profiles if item.profile_id is profile), None)
    reasons: list[str] = []
    if selected is None:
        reasons.append("requested operation profile is not declared")
    if target.os_arch not in manifest.supported_os_arch:
        reasons.append("target OS/architecture is unsupported")
    api = _version(target.platform_api_version)
    if api < _version(manifest.api_minimum) or (
        manifest.api_maximum_exclusive is not None
        and api >= _version(manifest.api_maximum_exclusive)
    ):
        reasons.append("Platform API version is outside the signed range")
    if manifest.isolation_profile not in target.allowed_isolation_profiles:
        reasons.append("required isolation profile is unavailable")
    missing_devices = sorted(set(manifest.device_requirements) - set(target.available_devices))
    if missing_devices:
        reasons.append("required devices unavailable: " + ",".join(missing_devices))
    capacity = dict(target.resource_capacity)
    for name, amount in manifest.resources:
        if name not in capacity or capacity[name] < amount:
            reasons.append(f"module resource unavailable: {name}")
    if selected is not None:
        if (selected.allowed_host_classes
                and target.os_arch not in selected.allowed_host_classes):
            reasons.append("operation profile forbids target host class")
        missing_profile_devices = sorted(
            set(selected.allowed_device_classes) - set(target.available_devices)
        )
        if missing_profile_devices:
            reasons.append(
                "profile device classes unavailable: " + ",".join(missing_profile_devices)
            )
        for name, amount in selected.resource_envelope:
            if name not in capacity or capacity[name] < amount:
                reasons.append(f"profile resource unavailable: {name}")
        if selected.resource_requirements:
            if target.resource_supply is None or now is None:
                reasons.append("typed resource capability evidence is unavailable")
            else:
                assessment = evaluate_resource_requirements(
                    target.resource_supply, selected.resource_requirements, now=now,
                )
                reasons.extend(
                    f"resource requirement rejected: {identifier}: {reason}"
                    for identifier, reason in assessment.rejected
                )
                reasons.extend(
                    f"resource requirement unknown: {identifier}: {reason}"
                    for identifier, reason in assessment.unknown
                )
    by_id = {item.module_id: item for item in installed_dependencies}
    if len(by_id) != len(installed_dependencies):
        reasons.append("installed dependency identity is ambiguous")
    for requirement in manifest.dependencies:
        dependency = by_id.get(requirement.module_id)
        if dependency is None:
            reasons.append(f"dependency missing: {requirement.module_id}")
        elif not requirement.accepts(dependency.version):
            reasons.append(f"dependency version incompatible: {requirement.module_id}")
    return ModuleCompatibilityReport(
        manifest.module_id, manifest.version, manifest.package_identity_digest(),
        profile, target, not reasons, tuple(reasons), True, _ASSESSMENT_TOKEN,
    )
