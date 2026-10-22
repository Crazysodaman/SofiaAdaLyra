"""Sofía's module manifest layer: typed validation, trust, health.

Manifest documents found on disk are untrusted candidates. Only the
owner-session registry turns them into verified entries, after checking
the implementation is actually present in authorized codebase inspection
evidence. Discovery, validation, and health projection never execute
candidate code and never grant authority.
"""
from sofia.modules.manifest import (
    ManifestCandidate,
    ModuleManifest,
    ModuleManifestError,
    discover_candidates,
    parse_manifest,
)
from sofia.modules.registry import (
    ModuleHealth,
    ModuleHealthReport,
    ModuleRegistryError,
    ModuleRegistryService,
    ModuleRegistryStore,
    ModuleRegistration,
    TrustState,
)

__all__ = [
    "ManifestCandidate",
    "ModuleManifest",
    "ModuleManifestError",
    "discover_candidates",
    "parse_manifest",
    "ModuleHealth",
    "ModuleHealthReport",
    "ModuleRegistryError",
    "ModuleRegistryService",
    "ModuleRegistryStore",
    "ModuleRegistration",
    "TrustState",
]
