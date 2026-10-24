"""Deterministic compatibility admission for signed module packages."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .package import OperationProfileKind, SignedModuleManifest


_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


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


def evaluate_module_compatibility(
    manifest: SignedModuleManifest, *, profile: OperationProfileKind,
    target: ModulePlatformTarget,
    installed_dependencies: tuple[SignedModuleManifest, ...] = (),
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
        profile, target, not reasons, tuple(reasons), False,
    )
