"""Signed, non-executable Sofía module package contract (Manifest V1)."""
from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_MODULE = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class PackageManifestError(ValueError):
    pass


class OperationProfileKind(str, Enum):
    OBSERVE = "OBSERVE"
    SIMULATE = "SIMULATE"
    ADVISORY = "ADVISORY"
    EXECUTE_SCOPED = "EXECUTE_SCOPED"
    SUPERVISED = "SUPERVISED"


class PlacementMode(str, Enum):
    PORTABLE_STATELESS = "PORTABLE_STATELESS"
    CHECKPOINT_RESTART = "CHECKPOINT_RESTART"
    HOST_PINNED = "HOST_PINNED"
    CANONICAL_PINNED = "CANONICAL_PINNED"


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise PackageManifestError("version must be semantic X.Y.Z")
    return tuple(int(item) for item in value.split("."))  # type: ignore[return-value]


def _strings(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple or len(values) > 64 or any(
        not isinstance(item, str) or not item.strip() or len(item) > 200
        for item in values
    ) or len(set(values)) != len(values):
        raise PackageManifestError(f"{label} must be bounded unique text")


def _module_id(value: str) -> None:
    if not isinstance(value, str) or _MODULE.fullmatch(value) is None:
        raise PackageManifestError("invalid module_id")


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise PackageManifestError("artifact path must be portable relative POSIX text")
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or ".." in posix.parts or "." in posix.parts
            or posix.as_posix() != value):
        raise PackageManifestError("artifact path escapes package root")
    return value


@dataclass(frozen=True, slots=True)
class DependencyRequirement:
    module_id: str
    minimum_version: str
    maximum_version_exclusive: str | None = None

    def __post_init__(self) -> None:
        _module_id(self.module_id)
        minimum = _version(self.minimum_version)
        if self.maximum_version_exclusive is not None and (
            _version(self.maximum_version_exclusive) <= minimum
        ):
            raise PackageManifestError("dependency maximum must exceed minimum")

    def accepts(self, version: str) -> bool:
        candidate = _version(version)
        return candidate >= _version(self.minimum_version) and (
            self.maximum_version_exclusive is None
            or candidate < _version(self.maximum_version_exclusive)
        )


@dataclass(frozen=True, slots=True)
class ModuleOperationProfile:
    profile_id: OperationProfileKind
    profile_version: int
    available_capability_ids: tuple[str, ...]
    permission_ceiling: int
    data_classes: tuple[str, ...]
    resource_envelope: tuple[tuple[str, int], ...]
    allowed_host_classes: tuple[str, ...]
    allowed_device_classes: tuple[str, ...]
    required_approval_class: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, OperationProfileKind):
            raise TypeError("profile_id must be OperationProfileKind")
        if type(self.profile_version) is not int or self.profile_version < 1:
            raise PackageManifestError("profile_version must be positive")
        _strings(self.available_capability_ids, "profile capabilities")
        if any(_CAPABILITY.fullmatch(item) is None for item in self.available_capability_ids):
            raise PackageManifestError("invalid profile capability")
        if type(self.permission_ceiling) is not int or not 1 <= self.permission_ceiling <= 5:
            raise PackageManifestError("permission_ceiling must be in 1..5")
        for values, label in ((self.data_classes, "data classes"),
                              (self.allowed_host_classes, "host classes"),
                              (self.allowed_device_classes, "device classes")):
            _strings(values, label)
        if type(self.resource_envelope) is not tuple or any(
            not isinstance(name, str) or not name or type(amount) is not int or amount < 0
            for name, amount in self.resource_envelope
        ) or len({name for name, _ in self.resource_envelope}) != len(self.resource_envelope):
            raise PackageManifestError("invalid resource envelope")
        if not isinstance(self.required_approval_class, str) or not self.required_approval_class:
            raise PackageManifestError("required approval class required")


@dataclass(frozen=True, slots=True)
class ModuleMaintenanceProfile:
    schema: str
    module_id: str
    module_version: str
    profile_version: int
    artifact_digest: str
    support_status: str
    health_probe_ids: tuple[str, ...]
    retry_limit: int
    quarantine_threshold: int
    supported_versions: tuple[str, ...]
    maintenance_windows: tuple[str, ...]
    update_policy: str
    rollback_procedure: str
    escalation_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema != "sofia.module.maintenance.v1":
            raise PackageManifestError("unsupported maintenance schema")
        _module_id(self.module_id)
        _version(self.module_version)
        if type(self.profile_version) is not int or self.profile_version < 1:
            raise PackageManifestError("maintenance profile_version must be positive")
        if _DIGEST.fullmatch(self.artifact_digest) is None:
            raise PackageManifestError("maintenance artifact_digest must be SHA-256")
        if self.support_status not in {"supported", "deprecated", "end_of_life"}:
            raise PackageManifestError("invalid support status")
        for values, label in ((self.health_probe_ids, "health probes"),
                              (self.supported_versions, "supported versions"),
                              (self.maintenance_windows, "maintenance windows"),
                              (self.escalation_requirements, "escalations")):
            _strings(values, label)
        for version in self.supported_versions:
            _version(version)
        if type(self.retry_limit) is not int or not 0 <= self.retry_limit <= 20:
            raise PackageManifestError("retry_limit must be in 0..20")
        if type(self.quarantine_threshold) is not int or not 1 <= self.quarantine_threshold <= 50:
            raise PackageManifestError("quarantine_threshold must be in 1..50")
        for label, value in (("update_policy", self.update_policy),
                             ("rollback_procedure", self.rollback_procedure)):
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                raise PackageManifestError(f"{label} must be bounded nonempty text")


@dataclass(frozen=True, slots=True)
class SignedModuleManifest:
    schema_version: int
    module_id: str
    version: str
    kind: str
    publisher: str
    artifact_digests: tuple[tuple[str, str], ...]
    signature_b64: str
    trust_ref: str
    supported_os_arch: tuple[str, ...]
    api_minimum: str
    api_maximum_exclusive: str | None
    capability_schemas: tuple[tuple[str, str], ...]
    dependencies: tuple[DependencyRequirement, ...]
    isolation_profile: str
    resources: tuple[tuple[str, int], ...]
    device_requirements: tuple[str, ...]
    placement_mode: PlacementMode
    state_namespace: str | None
    migration_contract: str
    health_contract: str
    update_rollback_contract: str
    profiles: tuple[ModuleOperationProfile, ...]
    interoperability_contracts: tuple[str, ...]
    maintenance_profile: ModuleMaintenanceProfile

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise PackageManifestError("unsupported manifest schema_version")
        _module_id(self.module_id)
        _version(self.version)
        if self.kind not in {"release", "optional", "submodule", "adapter"}:
            raise PackageManifestError("invalid module kind")
        for label, value in (("publisher", self.publisher), ("trust_ref", self.trust_ref)):
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise PackageManifestError(f"{label} must be bounded nonempty text")
        try:
            if len(b64decode(self.signature_b64, validate=True)) != 64:
                raise PackageManifestError("Ed25519 signature must be 64 bytes")
        except Exception as exc:
            if isinstance(exc, PackageManifestError):
                raise
            raise PackageManifestError("signature must be canonical base64") from exc
        if type(self.artifact_digests) is not tuple or not self.artifact_digests:
            raise PackageManifestError("artifact digests required")
        paths = []
        for path, digest in self.artifact_digests:
            paths.append(_safe_relative(path))
            if _DIGEST.fullmatch(digest) is None:
                raise PackageManifestError("artifact digest must be SHA-256")
        if len(paths) != len(set(path.casefold() for path in paths)):
            raise PackageManifestError("artifact paths must be portable-unique")
        _strings(self.supported_os_arch, "supported os/arch")
        _version(self.api_minimum)
        if self.api_maximum_exclusive is not None and (
            _version(self.api_maximum_exclusive) <= _version(self.api_minimum)
        ):
            raise PackageManifestError("API maximum must exceed minimum")
        if type(self.capability_schemas) is not tuple or any(
            _CAPABILITY.fullmatch(name) is None or not schema
            for name, schema in self.capability_schemas
        ):
            raise PackageManifestError("invalid capability schemas")
        if len({name for name, _ in self.capability_schemas}) != len(self.capability_schemas):
            raise PackageManifestError("capability schemas must be unique")
        if type(self.dependencies) is not tuple or any(
            not isinstance(item, DependencyRequirement) for item in self.dependencies
        ) or len({item.module_id for item in self.dependencies}) != len(
            self.dependencies
        ) or self.module_id in {item.module_id for item in self.dependencies}:
            raise PackageManifestError("invalid dependency requirements")
        if type(self.resources) is not tuple or any(
            not isinstance(name, str) or not name
            or type(amount) is not int or amount < 0
            for name, amount in self.resources
        ) or len({name for name, _ in self.resources}) != len(self.resources):
            raise PackageManifestError("invalid module resources")
        _strings(self.device_requirements, "device requirements")
        _strings(self.interoperability_contracts, "interoperability contracts")
        if not isinstance(self.placement_mode, PlacementMode):
            raise TypeError("placement_mode must be PlacementMode")
        if self.state_namespace is not None and _CAPABILITY.fullmatch(self.state_namespace) is None:
            raise PackageManifestError("invalid state namespace")
        for label, value in (("isolation_profile", self.isolation_profile),
                             ("migration_contract", self.migration_contract),
                             ("health_contract", self.health_contract),
                             ("update_rollback_contract", self.update_rollback_contract)):
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                raise PackageManifestError(f"{label} must be bounded nonempty text")
        if type(self.profiles) is not tuple or not self.profiles or any(
            not isinstance(item, ModuleOperationProfile) for item in self.profiles
        ) or len({item.profile_id for item in self.profiles}) != len(self.profiles):
            raise PackageManifestError("operation profiles must be nonempty and unique")
        declared = {name for name, _ in self.capability_schemas}
        if any(not set(item.available_capability_ids).issubset(declared) for item in self.profiles):
            raise PackageManifestError("profile exposes undeclared capability")
        if not isinstance(self.maintenance_profile, ModuleMaintenanceProfile):
            raise TypeError("maintenance_profile required")
        if (
            self.maintenance_profile.module_id != self.module_id
            or self.maintenance_profile.module_version != self.version
        ):
            raise PackageManifestError(
                "maintenance profile identity does not match module"
            )
        if self.maintenance_profile.artifact_digest != self.package_identity_digest():
            raise PackageManifestError("maintenance digest does not match package identity")

    def package_identity_digest(self) -> str:
        return sha256(json.dumps({
            "artifacts": list(self.artifact_digests), "module_id": self.module_id,
            "publisher": self.publisher, "version": self.version,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def unsigned_document(self) -> dict[str, object]:
        def profile(item: ModuleOperationProfile) -> dict[str, object]:
            return {
                "allowed_device_classes": list(item.allowed_device_classes),
                "allowed_host_classes": list(item.allowed_host_classes),
                "available_capability_ids": list(item.available_capability_ids),
                "data_classes": list(item.data_classes),
                "permission_ceiling": item.permission_ceiling,
                "profile_id": item.profile_id.value,
                "profile_version": item.profile_version,
                "required_approval_class": item.required_approval_class,
                "resource_envelope": [list(pair) for pair in item.resource_envelope],
            }
        maintenance = self.maintenance_profile
        return {
            "api_maximum_exclusive": self.api_maximum_exclusive,
            "api_minimum": self.api_minimum,
            "artifact_digests": [list(item) for item in self.artifact_digests],
            "capability_schemas": [list(item) for item in self.capability_schemas],
            "dependencies": [{"module_id": item.module_id,
                "minimum_version": item.minimum_version,
                "maximum_version_exclusive": item.maximum_version_exclusive}
                for item in self.dependencies],
            "device_requirements": list(self.device_requirements),
            "health_contract": self.health_contract,
            "interoperability_contracts": list(self.interoperability_contracts),
            "isolation_profile": self.isolation_profile,
            "kind": self.kind,
            "maintenance_profile": {
                "artifact_digest": maintenance.artifact_digest,
                "escalation_requirements": list(maintenance.escalation_requirements),
                "health_probe_ids": list(maintenance.health_probe_ids),
                "maintenance_windows": list(maintenance.maintenance_windows),
                "module_id": maintenance.module_id,
                "module_version": maintenance.module_version,
                "profile_version": maintenance.profile_version,
                "quarantine_threshold": maintenance.quarantine_threshold,
                "retry_limit": maintenance.retry_limit,
                "rollback_procedure": maintenance.rollback_procedure,
                "schema": maintenance.schema,
                "support_status": maintenance.support_status,
                "supported_versions": list(maintenance.supported_versions),
                "update_policy": maintenance.update_policy,
            },
            "migration_contract": self.migration_contract,
            "module_id": self.module_id,
            "placement_mode": self.placement_mode.value,
            "profiles": [profile(item) for item in self.profiles],
            "publisher": self.publisher,
            "resources": [list(item) for item in self.resources],
            "schema_version": self.schema_version,
            "state_namespace": self.state_namespace,
            "supported_os_arch": list(self.supported_os_arch),
            "trust_ref": self.trust_ref,
            "update_rollback_contract": self.update_rollback_contract,
            "version": self.version,
        }

    def canonical_unsigned_bytes(self) -> bytes:
        return json.dumps(self.unsigned_document(), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class VerifiedModulePackage:
    manifest: SignedModuleManifest
    package_root: Path
    package_digest: str


def _object(value: object, *, label: str,
            keys: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys or any(
        not isinstance(key, str) for key in value
    ):
        raise PackageManifestError(f"{label} has invalid fields")
    return value


def _pairs(value: object, *, label: str) -> tuple[tuple[Any, Any], ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, list) or len(item) != 2 for item in value
    ):
        raise PackageManifestError(f"{label} must be pairs")
    return tuple((item[0], item[1]) for item in value)


def _list(value: object, *, label: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise PackageManifestError(f"{label} must be a list")
    return tuple(value)


def parse_signed_manifest(document: object) -> SignedModuleManifest:
    """Parse untrusted JSON data strictly without importing module code."""
    top = _object(document, label="manifest", keys=frozenset({
        "api_maximum_exclusive", "api_minimum", "artifact_digests",
        "capability_schemas", "dependencies", "device_requirements",
        "health_contract", "interoperability_contracts", "isolation_profile",
        "kind", "maintenance_profile", "migration_contract", "module_id",
        "placement_mode", "profiles", "publisher", "resources",
        "schema_version", "signature_b64", "state_namespace",
        "supported_os_arch", "trust_ref", "update_rollback_contract", "version",
    }))
    maintenance_doc = _object(
        top["maintenance_profile"], label="maintenance profile",
        keys=frozenset({
            "artifact_digest", "escalation_requirements", "health_probe_ids",
            "maintenance_windows", "module_id", "module_version",
            "profile_version", "quarantine_threshold", "retry_limit",
            "rollback_procedure", "schema", "support_status",
            "supported_versions", "update_policy",
        }),
    )
    profile_keys = frozenset({
        "allowed_device_classes", "allowed_host_classes",
        "available_capability_ids", "data_classes", "permission_ceiling",
        "profile_id", "profile_version", "required_approval_class",
        "resource_envelope",
    })
    try:
        profiles = tuple(
            ModuleOperationProfile(
                OperationProfileKind(profile["profile_id"]),
                profile["profile_version"],
                _list(profile["available_capability_ids"], label="profile capabilities"),
                profile["permission_ceiling"],
                _list(profile["data_classes"], label="profile data classes"),
                _pairs(profile["resource_envelope"], label="profile resources"),
                _list(profile["allowed_host_classes"], label="profile hosts"),
                _list(profile["allowed_device_classes"], label="profile devices"),
                profile["required_approval_class"],
            )
            for profile in (
                _object(item, label="operation profile", keys=profile_keys)
                for item in _list(top["profiles"], label="profiles")
            )
        )
        dependencies = tuple(
            DependencyRequirement(
                dependency["module_id"], dependency["minimum_version"],
                dependency["maximum_version_exclusive"],
            )
            for dependency in (
                _object(item, label="dependency", keys=frozenset({
                    "maximum_version_exclusive", "minimum_version", "module_id",
                }))
                for item in _list(top["dependencies"], label="dependencies")
            )
        )
        maintenance = ModuleMaintenanceProfile(
            maintenance_doc["schema"], maintenance_doc["module_id"],
            maintenance_doc["module_version"], maintenance_doc["profile_version"],
            maintenance_doc["artifact_digest"], maintenance_doc["support_status"],
            _list(maintenance_doc["health_probe_ids"], label="health probes"),
            maintenance_doc["retry_limit"], maintenance_doc["quarantine_threshold"],
            _list(maintenance_doc["supported_versions"], label="supported versions"),
            _list(maintenance_doc["maintenance_windows"], label="maintenance windows"),
            maintenance_doc["update_policy"], maintenance_doc["rollback_procedure"],
            _list(maintenance_doc["escalation_requirements"], label="escalations"),
        )
        return SignedModuleManifest(
            top["schema_version"], top["module_id"], top["version"], top["kind"],
            top["publisher"], _pairs(top["artifact_digests"], label="artifacts"),
            top["signature_b64"], top["trust_ref"],
            _list(top["supported_os_arch"], label="supported OS/arch"),
            top["api_minimum"], top["api_maximum_exclusive"],
            _pairs(top["capability_schemas"], label="capability schemas"),
            dependencies, top["isolation_profile"],
            _pairs(top["resources"], label="resources"),
            _list(top["device_requirements"], label="device requirements"),
            PlacementMode(top["placement_mode"]), top["state_namespace"],
            top["migration_contract"], top["health_contract"],
            top["update_rollback_contract"], profiles,
            _list(top["interoperability_contracts"], label="interoperability contracts"),
            maintenance,
        )
    except PackageManifestError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageManifestError("manifest contains invalid typed values") from exc


def verify_module_package(manifest: SignedModuleManifest, *, package_root: Path,
                          trusted_public_key: bytes) -> VerifiedModulePackage:
    """Verify exact files and signature without importing package code."""
    if not isinstance(manifest, SignedModuleManifest):
        raise TypeError("manifest must be SignedModuleManifest")
    if not isinstance(package_root, Path) or not package_root.is_dir():
        raise FileNotFoundError("module package root required")
    if package_root.is_symlink():
        raise PackageManifestError("module package root cannot be a symlink")
    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(
            b64decode(manifest.signature_b64, validate=True),
            manifest.canonical_unsigned_bytes(),
        )
    except Exception as exc:
        raise PackageManifestError("module package signature is invalid") from exc
    root = package_root.resolve(strict=True)
    for relative, expected in manifest.artifact_digests:
        target = package_root / PurePosixPath(relative)
        if target.is_symlink() or not target.is_file():
            raise PackageManifestError("declared artifact missing or redirected")
        try:
            target.resolve(strict=True).relative_to(root)
        except (OSError, ValueError) as exc:
            raise PackageManifestError("module artifact escapes package root") from exc
        if sha256(target.read_bytes()).hexdigest() != expected:
            raise PackageManifestError("module artifact digest mismatch")
    return VerifiedModulePackage(manifest, root, manifest.package_identity_digest())


def validate_dependency_graph(manifests: tuple[SignedModuleManifest, ...]) -> tuple[str, ...]:
    """Return dependency-first activation order or fail closed."""
    by_id = {item.module_id: item for item in manifests}
    if len(by_id) != len(manifests):
        raise PackageManifestError("duplicate module identity")
    graph: dict[str, tuple[str, ...]] = {}
    for manifest in manifests:
        dependencies = []
        for requirement in manifest.dependencies:
            dependency = by_id.get(requirement.module_id)
            if dependency is None:
                raise PackageManifestError(f"missing dependency: {requirement.module_id}")
            if not requirement.accepts(dependency.version):
                raise PackageManifestError(
                    f"dependency version incompatible: {requirement.module_id}"
                )
            dependencies.append(requirement.module_id)
        graph[manifest.module_id] = tuple(dependencies)
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []
    def visit(module_id: str) -> None:
        if module_id in visiting:
            raise PackageManifestError("module dependency cycle detected")
        if module_id in visited:
            return
        visiting.add(module_id)
        for dependency in graph[module_id]:
            visit(dependency)
        visiting.remove(module_id)
        visited.add(module_id)
        ordered.append(module_id)
    for module_id in sorted(graph):
        visit(module_id)
    return tuple(ordered)
