"""AG-D028 read-only selective module closure over existing signed module contracts.

This is a *preview*, not a catalog/index, authority, installer, cache, offer,
signature verifier, or mutable lifecycle. Inputs must originate from the
canonical module verifier; its public VerifiedModulePackage dataclass by itself
does not prove current publisher trust/revocation. Before acquisition/staging,
the target Platform must independently reverify exact bytes, trust, license,
OS/ABI and current SAFE/STOP approval through Team A/B's existing boundaries.

No data is fetched, opened, imported, installed, started, offered, or deleted.
No Core identity/private state is inspected or inferred from module metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.platform.modules.compatibility import (
    ModulePlatformTarget, evaluate_module_compatibility,
)
from sofia.platform.modules.package import (
    DependencyRequirement, OperationProfileKind, SignedModuleManifest,
    VerifiedModulePackage, validate_dependency_graph,
)

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ITEMS = 128
_MAX_SELECTION = 32


class ModuleLibraryPreviewRejected(ValueError):
    """Ambiguous, conflicting or incompatible requested module closure."""


@dataclass(frozen=True, slots=True)
class ModuleLibraryPreviewItem:
    module_id: str
    version: str
    package_digest: str
    existing_same_digest: bool
    replaces_existing_version: bool
    stage_required: bool
    # Rights must come from a separately signed artifact catalog policy.
    peer_distribution_approved: bool = False


@dataclass(frozen=True, slots=True)
class ModuleLibraryPreview:
    """Dependency-first steps; no execution, trust or install authority."""

    selected: tuple[tuple[str, str], ...]
    items: tuple[ModuleLibraryPreviewItem, ...]
    requires_independent_publisher_reverification: bool = True
    requires_separate_host_install_approval: bool = True
    requires_separate_activation_approval: bool = True
    executable: bool = False


def plan_module_library_preview(
    *,
    selected: tuple[tuple[str, str], ...],
    candidates: tuple[VerifiedModulePackage, ...],
    installed: tuple[VerifiedModulePackage, ...],
    target: ModulePlatformTarget,
    profile: OperationProfileKind = OperationProfileKind.OBSERVE,
) -> ModuleLibraryPreview:
    """Produce exact digest-pinned dependency closure without filesystem effects.

    An installed package may satisfy a dependency. If its version is wrong,
    an explicit replacement must be selected; there is no silent upgrade.
    If multiple candidate releases satisfy a dependency, select/pin one
    explicitly rather than choose latest by filename or untrusted index order.
    The caller may preview a group but every subsequent operation must use
    distinct canonical SAFE approvals and the existing B1/module installer.
    """
    if not isinstance(target, ModulePlatformTarget):
        raise TypeError("canonical ModulePlatformTarget required")
    if not isinstance(profile, OperationProfileKind):
        raise TypeError("canonical OperationProfileKind required")
    if type(selected) is not tuple or not 1 <= len(selected) <= _MAX_SELECTION:
        raise ModuleLibraryPreviewRejected("select 1..32 exact module identities")
    if type(candidates) is not tuple or not 1 <= len(candidates) <= _MAX_ITEMS:
        raise ModuleLibraryPreviewRejected("bounded reviewed candidate set required")
    if type(installed) is not tuple or len(installed) > _MAX_ITEMS:
        raise ModuleLibraryPreviewRejected("bounded installed inventory required")

    wanted: dict[str, str] = {}
    for row in selected:
        if (type(row) is not tuple or len(row) != 2
                or any(type(part) is not str for part in row)):
            raise ModuleLibraryPreviewRejected("exact module ID and SHA256 required")
        module_id, digest = row
        if not module_id or _DIGEST.fullmatch(digest) is None:
            raise ModuleLibraryPreviewRejected("invalid requested module digest")
        if module_id in wanted:
            raise ModuleLibraryPreviewRejected("duplicate requested module identity")
        wanted[module_id] = digest

    index: dict[str, list[VerifiedModulePackage]] = {}
    seen: set[tuple[str, str]] = set()
    for package in candidates:
        if not isinstance(package, VerifiedModulePackage):
            raise TypeError("reviewed candidate module package required")
        manifest = package.manifest
        if (not isinstance(manifest, SignedModuleManifest)
                or type(package.package_digest) is not str
                or package.package_digest != manifest.package_identity_digest()):
            raise ModuleLibraryPreviewRejected("candidate module identity digest mismatch")
        key = (manifest.module_id, package.package_digest)
        if key in seen:
            raise ModuleLibraryPreviewRejected("duplicate indexed candidate release")
        seen.add(key)
        index.setdefault(manifest.module_id, []).append(package)

    on_host: dict[str, VerifiedModulePackage] = {}
    for package in installed:
        if not isinstance(package, VerifiedModulePackage):
            raise TypeError("canonical installed package projection required")
        manifest = package.manifest
        if (not isinstance(manifest, SignedModuleManifest)
                or package.package_digest != manifest.package_identity_digest()
                or manifest.module_id in on_host):
            raise ModuleLibraryPreviewRejected("invalid or duplicate installed identity")
        on_host[manifest.module_id] = package

    def candidate(module_id: str, requirement: DependencyRequirement | None):
        releases = index.get(module_id, ())
        pinned = wanted.get(module_id)
        if pinned is not None:
            matches = [item for item in releases if item.package_digest == pinned]
            if len(matches) != 1:
                raise ModuleLibraryPreviewRejected(
                    "requested exact module digest is unavailable: " + module_id
                )
            found = matches[0]
            if requirement is not None and not requirement.accepts(found.manifest.version):
                raise ModuleLibraryPreviewRejected(
                    "pinned module violates dependent version range: " + module_id
                )
            return found

        existing = on_host.get(module_id)
        if existing is not None:
            if requirement is not None and not requirement.accepts(existing.manifest.version):
                raise ModuleLibraryPreviewRejected(
                    "installed dependency requires explicitly selected update: " + module_id
                )
            return existing
        matches = [
            item for item in releases
            if requirement is None or requirement.accepts(item.manifest.version)
        ]
        if not matches:
            raise ModuleLibraryPreviewRejected("missing signed dependency: " + module_id)
        if len(matches) != 1:
            raise ModuleLibraryPreviewRejected(
                "ambiguous dependency release; pin exact digest: " + module_id
            )
        return matches[0]

    chosen: dict[str, VerifiedModulePackage] = {}
    visiting: set[str] = set()

    def walk(module_id: str, requirement: DependencyRequirement | None = None) -> None:
        if module_id in visiting:
            raise ModuleLibraryPreviewRejected("module dependency cycle detected")
        found = chosen.get(module_id)
        if found is not None:
            if requirement is not None and not requirement.accepts(found.manifest.version):
                raise ModuleLibraryPreviewRejected(
                    "conflicting dependency ranges: " + module_id
                )
            return
        package = candidate(module_id, requirement)
        if len(chosen) >= _MAX_ITEMS:
            raise ModuleLibraryPreviewRejected("module dependency closure exceeds bound")
        visiting.add(module_id)
        try:
            for dependency in package.manifest.dependencies:
                walk(dependency.module_id, dependency)
        finally:
            visiting.remove(module_id)
        chosen[module_id] = package

    for module_id in sorted(wanted):
        walk(module_id)

    # Reuse the canonical dependency and cycle validator rather than invent
    # different graph/version semantics for the library.
    manifests = tuple(item.manifest for item in chosen.values())
    try:
        dependency_first = validate_dependency_graph(manifests)
    except ValueError as exc:
        raise ModuleLibraryPreviewRejected("invalid signed dependency graph") from exc

    items: list[ModuleLibraryPreviewItem] = []
    for module_id in dependency_first:
        package = chosen[module_id]
        manifest = package.manifest
        current = on_host.get(module_id)
        present = current is not None and current.package_digest == package.package_digest
        if not present:
            # The reviewed compatibility evaluator is an advisory *preview*,
            # not a forged grant. Prospective dependencies are passed only to
            # evaluate their exact versions and resource constraints.
            dependencies = tuple(chosen[req.module_id].manifest for req in manifest.dependencies)
            report = evaluate_module_compatibility(
                manifest, profile=profile, target=target,
                installed_dependencies=dependencies,
            )
            if not report.compatible:
                raise ModuleLibraryPreviewRejected(
                    "module incompatible: " + module_id + ": " + "; ".join(report.reasons)
                )
        items.append(ModuleLibraryPreviewItem(
            module_id=module_id, version=manifest.version,
            package_digest=package.package_digest,
            existing_same_digest=present,
            replaces_existing_version=current is not None and not present,
            stage_required=not present,
        ))
    return ModuleLibraryPreview(selected, tuple(items))
