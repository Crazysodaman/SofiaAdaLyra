"""Higher-trust verification boundary for immutable release manifests."""

from __future__ import annotations

from abc import ABC, abstractmethod

from sofia.release_integrity.manifest import ReleaseManifest


class ReleaseVerificationError(RuntimeError):
    """A release cannot be trusted or activated."""


class ReleaseSignatureVerifier(ABC):
    """Verify signatures without exposing signing authority to normal runtime."""

    @abstractmethod
    def verify(self, manifest: ReleaseManifest) -> bool:
        raise NotImplementedError

    def require_verified(self, manifest: ReleaseManifest) -> None:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if manifest.signature is None:
            raise ReleaseVerificationError("release manifest is unsigned")
        if not self.verify(manifest):
            raise ReleaseVerificationError(
                "release signature verification failed"
            )
