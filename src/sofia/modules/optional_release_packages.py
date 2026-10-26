"""Exact-source optional-module package preparation for reviewed Platform signing.

This module never generates keys, signs on the owner's behalf, installs a module,
registers capabilities, changes a canonical database, or marks a module ready.
A draft is a reproducible signing *request*; only Platform may verify a signed
package, admit a reviewed factory and record authoritative lifecycle state.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Mapping

from .optional_release_audit import (
    EXPECTED_OPTIONAL_IDS,
    audit_optional_source_tree,
)

_PACKAGE_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_PROFILES = frozenset({"OBSERVE", "ADVISORY", "SIMULATE"})
_ALLOWED_RESOURCE_NAMES = frozenset({"cpu_millicores", "ram_mib", "gpu_mib"})
_EXPECTED_OPTIONAL_COUNT = len(EXPECTED_OPTIONAL_IDS)


class ReleasePreparationError(ValueError):
    """A source, identity, policy or package mismatch prevents release preparation."""


def _canonical(document: Mapping[str, object]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _bounded(value: object, label: str, limit: int = 200) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > limit:
        raise ReleasePreparationError(f"invalid {label}")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ReleasePreparationError(f"control characters in {label}")
    return value


def _safe_file(root: Path, relative: str) -> bytes:
    """Read a source file only if every path component is a real directory/file.

    This is a source preflight, not a race-proof sandbox boundary. Platform's
    verify_module_package must re-verify the copied bytes at installation.
    """
    if not isinstance(relative, str) or "\\" in relative or "\x00" in relative:
        raise ReleasePreparationError("invalid artifact path")
    candidate = PurePosixPath(relative)
    if (candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts
            or candidate.as_posix() != relative or not relative.startswith("src/sofia/modules/")):
        raise ReleasePreparationError("artifact path is outside module source boundary")
    position = root
    for part in candidate.parts[:-1]:
        position = position / part
        if not stat.S_ISDIR(position.lstat().st_mode):
            raise ReleasePreparationError("artifact parent is redirected or not a directory")
    path = position / candidate.name
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ReleasePreparationError("artifact is not an ordinary file")
    if path.stat().st_size > 512 * 1024:
        raise ReleasePreparationError("individual source artifact exceeds limit")
    return path.read_bytes()


@dataclass(frozen=True)
class OwnerReviewedReleasePolicy:
    """External operator inputs, never inferred or approved by module source.

    package_ids and capability_schema_refs must be explicitly reviewed. These
    mappings are not enrollment, trusted principal proofs, or SAFE approvals.
    """
    package_ids: Mapping[str, str]
    capability_schema_refs: Mapping[str, str]
    publisher: str
    trust_ref: str
    platform_api_minimum: str
    supported_os_arch: tuple[str, ...]
    isolation_profile: str
    allowed_host_classes: tuple[str, ...]
    data_classes: Mapping[str, tuple[str, ...]]
    review_receipt: str

    def __post_init__(self) -> None:
        if not isinstance(self.package_ids, Mapping) or not isinstance(self.capability_schema_refs, Mapping):
            raise ReleasePreparationError("reviewed package and capability mappings required")
        if not isinstance(self.data_classes, Mapping):
            raise ReleasePreparationError("per-module reviewed data class mapping required")
        if set(self.package_ids) - EXPECTED_OPTIONAL_IDS or set(self.data_classes) - EXPECTED_OPTIONAL_IDS:
            raise ReleasePreparationError("unknown optional catalog ID in policy")
        for label in ("publisher", "trust_ref", "isolation_profile", "review_receipt"):
            _bounded(getattr(self, label), label)
        if len(set(self.supported_os_arch)) != len(self.supported_os_arch):
            raise ReleasePreparationError("duplicate OS/arch requirements")
        if len(set(self.allowed_host_classes)) != len(self.allowed_host_classes):
            raise ReleasePreparationError("duplicate host classes")
        if not _SEMVER.fullmatch(self.platform_api_minimum):
            raise ReleasePreparationError("platform API minimum must be semantic")
        if not isinstance(self.supported_os_arch, tuple) or not self.supported_os_arch or any(
            not isinstance(value, str) or not value.strip() for value in self.supported_os_arch
        ):
            raise ReleasePreparationError("explicit reviewed OS/arch requirements required")
        if not isinstance(self.allowed_host_classes, tuple) or not self.allowed_host_classes or any(
            not isinstance(value, str) or not value.strip() for value in self.allowed_host_classes
        ):
            raise ReleasePreparationError("explicit reviewed allowed hosts required")
        for module_id, package_id in self.package_ids.items():
            if not isinstance(package_id, str) or not _PACKAGE_ID.fullmatch(package_id):
                raise ReleasePreparationError(f"invalid package ID for {module_id}")
        if len(set(self.package_ids.values())) != len(self.package_ids):
            raise ReleasePreparationError("package identity collision")
        for cap, schema in self.capability_schema_refs.items():
            if not isinstance(cap, str) or not _CAPABILITY.fullmatch(cap):
                raise ReleasePreparationError("invalid capability schema mapping key")
            _bounded(schema, "capability schema ref")
        for module_id, classes in self.data_classes.items():
            if type(classes) is not tuple or not classes or any(
                not isinstance(cls, str) or not cls.strip() for cls in classes
            ):
                raise ReleasePreparationError(f"reviewed data classes missing for {module_id}")


@dataclass(frozen=True)
class UnsignedReleaseDraft:
    catalog_id: str
    package_id: str
    capability_id: str
    artifact_digests: tuple[tuple[str, str], ...]
    manifest_unsigned: dict[str, object]
    source_revision_sha: str

    @property
    def signing_bytes(self) -> bytes:
        """Exact canonical Platform bytes; no signature exists here."""
        return _canonical(self.manifest_unsigned)

    @property
    def package_digest(self) -> str:
        return sha256(self.signing_bytes).hexdigest()

    def signature_request(self) -> dict[str, object]:
        return {
            "schema": "sofia.optional.release_signing_request.v1",
            "catalog_id": self.catalog_id,
            "package_id": self.package_id,
            "package_digest": self.package_digest,
            "source_revision_sha": self.source_revision_sha,
            "source_revision_trust": "caller_supplied_unverified",
            "unsigned_manifest": self.manifest_unsigned,
            "signature_present": False,
            "platform_readiness": "NOT_VERIFIED",
        }


def prepare_release_draft(
    repo_root: Path, *, catalog_id: str, policy: OwnerReviewedReleasePolicy,
    source_revision_sha: str,
) -> UnsignedReleaseDraft:
    """Require exact source and operator-reviewed policy; do not infer trust.

    The returned document is structurally compatible with Platform's
    SignedModuleManifest. It remains unsigned, unregistered and unapproved.
    """
    if catalog_id not in EXPECTED_OPTIONAL_IDS:
        raise ReleasePreparationError("not an optional catalog identity")
    if not isinstance(source_revision_sha, str) or not _DIGEST.fullmatch(source_revision_sha):
        raise ReleasePreparationError("exact SHA-256 source snapshot required")
    if catalog_id not in policy.package_ids or catalog_id not in policy.data_classes:
        raise ReleasePreparationError("missing owner-reviewed package/data mapping")
    root = Path(repo_root).resolve(strict=True)
    report = audit_optional_source_tree(root)
    if report["cross_module_issues"]:
        raise ReleasePreparationError("cross-module capability or source collision")
    candidate = next(row for row in report["candidates"] if row["module_id"] == catalog_id)
    if candidate["source_scope"] != "locally_parsed_ast" or candidate["source_issues"]:
        raise ReleasePreparationError("candidate source is unavailable or invalid")
    capability, version, profile = candidate["capability_id"], candidate["version"], candidate["profile"]
    if profile not in _ALLOWED_PROFILES:
        raise ReleasePreparationError("effect-capable profiles require separate release implementation")
    if capability not in policy.capability_schema_refs:
        raise ReleasePreparationError("missing reviewed capability parameter schema")
    source = candidate["source_path"]
    if not isinstance(source, str):
        raise ReleasePreparationError("source path missing")
    # Module initializer is an artifact, not an import side effect.
    initializer = str(PurePosixPath(source).parent / "__init__.py")
    artifact_digests = tuple(sorted((path, sha256(_safe_file(root, path)).hexdigest())
                                    for path in {source, initializer}))
    if dict(artifact_digests)[source] != candidate["source_sha256"]:
        raise ReleasePreparationError("source changed during preflight")
    resources = tuple(sorted(candidate["resources"].items()))
    if set(dict(resources)) != _ALLOWED_RESOURCE_NAMES or any(
        type(v) is not int or not 0 <= v <= 1_000_000 for _, v in resources
    ):
        raise ReleasePreparationError("module resource envelope is not reviewed")
    module_id = policy.package_ids[catalog_id]
    # Native Platform's artifact_set_identity_digest uses json.dumps's default
    # ensure_ascii=True. This differs from canonical_unsigned_bytes (False).
    artifact_identity = sha256(json.dumps({
        "artifacts": [list(pair) for pair in artifact_digests],
        "module_id": module_id, "publisher": policy.publisher, "version": version,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    # Empty health probes: we deliberately do not assert a live health endpoint.
    # A real adapter factory and runtime acceptance remain mandatory.
    maintenance = {
        "schema": "sofia.module.maintenance.v1", "module_id": module_id,
        "module_version": version, "profile_version": 1,
        "artifact_digest": artifact_identity, "support_status": "supported",
        "health_probe_ids": [], "retry_limit": 0, "quarantine_threshold": 1,
        "supported_versions": [version], "maintenance_windows": [],
        "update_policy": "No automatic upgrade; owner review and exact digest required",
        "rollback_procedure": "Platform lifecycle only; restore previous verified package digest after independent operator approval",
        "escalation_requirements": ["reviewed_factory_and_live_health_not_yet_verified"],
    }
    manifest = {
        "schema_version": 1, "module_id": module_id, "version": version,
        "kind": "optional", "publisher": policy.publisher,
        "artifact_digests": [list(pair) for pair in artifact_digests],
        "trust_ref": policy.trust_ref,
        "supported_os_arch": list(policy.supported_os_arch),
        "api_minimum": policy.platform_api_minimum,
        "api_maximum_exclusive": None,
        "capability_schemas": [[capability, policy.capability_schema_refs[capability]]],
        "dependencies": [], "isolation_profile": policy.isolation_profile,
        "resources": [list(pair) for pair in resources],
        "device_requirements": [], "placement_mode": "PORTABLE_STATELESS",
        "state_namespace": None,
        "migration_contract": "Stateless review/simulation only; no canonical database state or migrator",
        "health_contract": "No operational health observation exists until a reviewed adapter is installed and observed",
        "update_rollback_contract": "Operator-reviewed lifecycle change using exact digest and staged rollback evidence",
        "profiles": [{
            "profile_id": profile, "profile_version": 1,
            "available_capability_ids": [capability], "permission_ceiling": 1,
            "data_classes": list(policy.data_classes[catalog_id]),
            "resource_envelope": [list(pair) for pair in resources],
            "allowed_host_classes": list(policy.allowed_host_classes),
            "allowed_device_classes": [],
            "required_approval_class": "platform_safe_scoped",
        }],
        "interoperability_contracts": [],
        "maintenance_profile": maintenance,
    }
    return UnsignedReleaseDraft(catalog_id, module_id, capability,
                                artifact_digests, manifest, source_revision_sha)


def materialize_unsigned_draft(
    draft: UnsignedReleaseDraft, *, repo_root: Path, output_root: Path,
) -> Path:
    """Write a *new*, non-executable, unsigned package for offline review only.

    Caller controls the output directory; this does not enter Platform's store.
    On failure, no existing destination is overwritten. The output is not a
    verified package, and must never be passed as an activation receipt.
    """
    if not isinstance(draft, UnsignedReleaseDraft):
        raise TypeError("draft required")
    root = Path(repo_root).resolve(strict=True)
    output = Path(output_root).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("output directory must not exist")
    for parent in output.parents:
        if parent.is_symlink():
            raise ReleasePreparationError("redirected output parent")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        for path, expected in draft.artifact_digests:
            data = _safe_file(root, path)
            if sha256(data).hexdigest() != expected:
                raise ReleasePreparationError("artifact changed after draft preparation")
            destination = output / PurePosixPath(path)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(data)
        unsigned_path = output / "UNSIGNED_REVIEW_ONLY.json"
        with unsigned_path.open("x", encoding="utf-8") as handle:
            json.dump(draft.signature_request(), handle, sort_keys=True, indent=2)
            handle.write("\n")
    except BaseException:
        # Do not silently leave a partial staging candidate that resembles a valid bundle.
        import shutil
        shutil.rmtree(output)
        raise
    return output


def verify_operator_signature(
    draft: UnsignedReleaseDraft, *, signature_b64: str,
    package_root: Path, trusted_public_key: bytes,
):
    """Use *real* Platform manifest parsing + Ed25519/package verification.

    No trusted key is ever generated or stored here. A valid signature still
    does not constitute a reviewed adapter, approval or installed lifecycle.
    """
    from sofia.platform.modules.package import parse_signed_manifest, verify_module_package
    if not isinstance(signature_b64, str) or not signature_b64:
        raise ReleasePreparationError("external operator signature required")
    root = Path(package_root)
    if root.is_symlink() or not root.is_dir():
        raise ReleasePreparationError("package root is unavailable or redirected")
    seen = set()
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ReleasePreparationError("redirected package artifact")
        if entry.is_file():
            seen.add(entry.relative_to(root).as_posix())
    allowed = {path for path, _ in draft.artifact_digests} | {"UNSIGNED_REVIEW_ONLY.json"}
    if seen != allowed:
        raise ReleasePreparationError("undeclared or missing package artifact")
    manifest = parse_signed_manifest(dict(draft.manifest_unsigned, signature_b64=signature_b64))
    package = verify_module_package(manifest, package_root=root,
                                    trusted_public_key=trusted_public_key)
    if package.package_digest != draft.package_digest:
        raise ReleasePreparationError("signed package identity does not match draft")
    return package


def prepare_release_batch(
    repo_root: Path, *, policy: OwnerReviewedReleasePolicy,
    source_revision_sha: str,
) -> tuple[UnsignedReleaseDraft, ...]:
    """Fail the entire reviewed catalog if any source or policy is incomplete.

    No partial release is ever represented as a successfully prepared batch.
    """
    if set(policy.package_ids) != EXPECTED_OPTIONAL_IDS:
        raise ReleasePreparationError(
            f"all {_EXPECTED_OPTIONAL_COUNT} owner-reviewed package IDs required"
        )
    if set(policy.data_classes) != EXPECTED_OPTIONAL_IDS:
        raise ReleasePreparationError(
            f"all {_EXPECTED_OPTIONAL_COUNT} reviewed data classes required"
        )
    drafts = tuple(prepare_release_draft(
        repo_root, catalog_id=catalog_id, policy=policy,
        source_revision_sha=source_revision_sha,
    ) for catalog_id in sorted(EXPECTED_OPTIONAL_IDS))
    if len({draft.capability_id for draft in drafts}) != _EXPECTED_OPTIONAL_COUNT:
        raise ReleasePreparationError("duplicate capability in release batch")
    if len({draft.package_digest for draft in drafts}) != _EXPECTED_OPTIONAL_COUNT:
        raise ReleasePreparationError("duplicate release package identity")
    return drafts


def materialize_unsigned_batch(
    drafts: tuple[UnsignedReleaseDraft, ...], *, repo_root: Path,
    output_root: Path,
) -> Path:
    """Prepare a fresh full-catalog unsigned review directory, all-or-nothing."""
    if type(drafts) is not tuple or len(drafts) != _EXPECTED_OPTIONAL_COUNT or (
        set(item.catalog_id for item in drafts) != EXPECTED_OPTIONAL_IDS
        or len({item.package_id for item in drafts}) != _EXPECTED_OPTIONAL_COUNT
    ):
        raise ReleasePreparationError(
            f"exactly {_EXPECTED_OPTIONAL_COUNT} unique optional drafts required"
        )
    output = Path(output_root).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("output directory already exists")
    for parent in output.parents:
        if parent.is_symlink():
            raise ReleasePreparationError("redirected output parent")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        for draft in drafts:
            materialize_unsigned_draft(
                draft, repo_root=repo_root, output_root=output / draft.package_id,
            )
        with (output / "BATCH_UNSIGNED_REVIEW_ONLY.json").open("x", encoding="utf-8") as handle:
            json.dump({"schema": "sofia.optional.release_batch_request.v1",
                       "count": _EXPECTED_OPTIONAL_COUNT, "signed": False,
                       "platform_readiness": "NOT_VERIFIED",
                       "packages": [item.package_digest for item in drafts]}, handle,
                      sort_keys=True, indent=2)
            handle.write("\n")
    except BaseException:
        import shutil
        shutil.rmtree(output)
        raise
    return output
