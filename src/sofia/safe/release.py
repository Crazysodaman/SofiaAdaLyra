from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sofia.dev.release import ReleaseManifest


class ReleaseVerificationError(RuntimeError):
    pass


class ReleaseSignatureVerifier(ABC):
    """Protected boundary implemented by the independently trusted verifier."""

    @abstractmethod
    def verify(
        self,
        *,
        manifest: ReleaseManifest,
        signature: bytes,
        signer_key_id: str,
    ) -> bool:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ReleaseActivationEvidence:
    release_id: str
    manifest_sha256: str
    signer_key_id: str
    signature_verified: bool
    lineage_verified: bool
    anti_rollback_verified: bool
    verified_at: datetime

    @property
    def accepted(self) -> bool:
        return (
            self.signature_verified
            and self.lineage_verified
            and self.anti_rollback_verified
        )


class ReleaseActivationGuard:
    """
    Fail-closed release trust boundary.

    Lineage and anti-rollback decisions are supplied by protected policy
    evidence; normal self-update code cannot manufacture them here.
    """

    def __init__(self, verifier: ReleaseSignatureVerifier) -> None:
        if not isinstance(verifier, ReleaseSignatureVerifier):
            raise TypeError("verifier must be a ReleaseSignatureVerifier")
        self._verifier = verifier

    def verify(
        self,
        *,
        manifest: ReleaseManifest,
        signature: bytes,
        signer_key_id: str,
        lineage_verified: bool,
        anti_rollback_verified: bool,
        verified_at: datetime,
    ) -> ReleaseActivationEvidence:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("signature must be nonempty bytes")
        if not isinstance(signer_key_id, str) or not signer_key_id.strip():
            raise ValueError("signer_key_id must be nonempty")
        if not isinstance(lineage_verified, bool):
            raise TypeError("lineage_verified must be boolean")
        if not isinstance(anti_rollback_verified, bool):
            raise TypeError("anti_rollback_verified must be boolean")
        if not isinstance(verified_at, datetime):
            raise TypeError("verified_at must be a datetime")
        if verified_at.tzinfo is None or verified_at.utcoffset() is None:
            raise ValueError("verified_at must be timezone-aware")

        signature_verified = self._verifier.verify(
            manifest=manifest,
            signature=signature,
            signer_key_id=signer_key_id,
        )
        evidence = ReleaseActivationEvidence(
            release_id=manifest.release_id,
            manifest_sha256=manifest.manifest_sha256,
            signer_key_id=signer_key_id,
            signature_verified=signature_verified is True,
            lineage_verified=lineage_verified,
            anti_rollback_verified=anti_rollback_verified,
            verified_at=verified_at,
        )
        if not evidence.accepted:
            raise ReleaseVerificationError(
                "release activation evidence did not satisfy protected policy"
            )
        return evidence
