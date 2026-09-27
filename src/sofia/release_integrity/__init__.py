"""Immutable release and verification contracts.

Release/Integrity is a cross-package control plane, not a roadmap package.
"""

from sofia.release_integrity.builder import (
    ReleaseBuildInputs,
    build_unsigned_manifest,
)
from sofia.release_integrity.manifest import (
    ArtifactDigest,
    CompatibilityWindow,
    ModelIdentity,
    ReleaseManifest,
    ReleaseSignature,
)
from sofia.release_integrity.verification import (
    ReleaseSignatureVerifier,
    ReleaseVerificationError,
)

__all__ = [
    "ArtifactDigest",
    "CompatibilityWindow",
    "ModelIdentity",
    "ReleaseBuildInputs",
    "ReleaseManifest",
    "ReleaseSignature",
    "ReleaseSignatureVerifier",
    "ReleaseVerificationError",
    "build_unsigned_manifest",
]
