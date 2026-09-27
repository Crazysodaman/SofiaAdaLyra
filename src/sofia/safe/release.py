from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

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

    Signature, lineage and anti-rollback evidence are computed here from the
    immutable candidate and the previously accepted manifest. Callers do not
    supply boolean trust claims.
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
        active_manifest: ReleaseManifest | None,
        verified_at: datetime,
    ) -> ReleaseActivationEvidence:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if active_manifest is not None and not isinstance(
            active_manifest,
            ReleaseManifest,
        ):
            raise TypeError(
                "active_manifest must be a ReleaseManifest or None"
            )
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("signature must be nonempty bytes")
        if not isinstance(signer_key_id, str) or not signer_key_id.strip():
            raise ValueError("signer_key_id must be nonempty")
        if not isinstance(verified_at, datetime):
            raise TypeError("verified_at must be a datetime")
        if verified_at.tzinfo is None or verified_at.utcoffset() is None:
            raise ValueError("verified_at must be timezone-aware")
        moment = verified_at.astimezone(timezone.utc)

        signature_verified = self._verifier.verify(
            manifest=manifest,
            signature=signature,
            signer_key_id=signer_key_id,
        )

        if active_manifest is None:
            lineage_verified = (
                manifest.parent_release_id is None
                and manifest.parent_manifest_sha256 is None
            )
            anti_rollback_verified = True
        else:
            lineage_verified = (
                manifest.parent_release_id == active_manifest.release_id
                and manifest.parent_manifest_sha256
                == active_manifest.manifest_sha256
            )
            anti_rollback_verified = (
                manifest.release_id != active_manifest.release_id
                and manifest.created_at.astimezone(timezone.utc)
                > active_manifest.created_at.astimezone(timezone.utc)
            )

        evidence = ReleaseActivationEvidence(
            release_id=manifest.release_id,
            manifest_sha256=manifest.manifest_sha256,
            signer_key_id=signer_key_id,
            signature_verified=signature_verified is True,
            lineage_verified=lineage_verified,
            anti_rollback_verified=anti_rollback_verified,
            verified_at=moment,
        )
        if not evidence.accepted:
            raise ReleaseVerificationError(
                "release activation evidence did not satisfy protected policy"
            )
        return evidence
