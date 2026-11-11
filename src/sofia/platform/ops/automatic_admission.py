"""Signed installation provenance and policy-governed Fleet admission.

Discovery, LAN presence, hostname and reachability never establish trust. The
only automatic path requires an active owner-established high-autonomy policy,
a short-lived publisher signature over the exact installation identity and
node key, and a matching verified discovery record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.safe.autonomy_policy import (
    PROFILE_HIGH_AUTONOMY,
    AutonomyPolicy,
)

ATTESTATION_SCHEMA = "aegis.platform.installation-attestation.v1"
SIGNATURE_DOMAIN = b"aegis.platform.installation-attestation.v1\x00"
MAX_ATTESTATION_LIFETIME = timedelta(minutes=10)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_FIELDS = frozenset({
    "schema",
    "installation_identity_id",
    "node_id",
    "public_key_sha256",
    "release_manifest_digest",
    "signer_key_id",
    "issued_at",
    "expires_at",
})


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class InstallationAttestation:
    """Untrusted signed statement about one installation identity and key."""

    installation_identity_id: str
    node_id: UUID
    public_key_sha256: str
    release_manifest_digest: str
    signer_key_id: str
    issued_at: datetime
    expires_at: datetime
    signature: bytes

    def __post_init__(self) -> None:
        for name in ("installation_identity_id", "signer_key_id"):
            value = getattr(self, name)
            if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.node_id, UUID):
            raise TypeError("node_id must be a UUID")
        for name in ("public_key_sha256", "release_manifest_digest"):
            value = getattr(self, name)
            if type(value) is not str or _DIGEST.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")
        _aware(self.issued_at, "issued_at")
        _aware(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("attestation expiry must follow issuance")
        if self.expires_at - self.issued_at > MAX_ATTESTATION_LIFETIME:
            raise ValueError("attestation lifetime exceeds ten minutes")
        if type(self.signature) is not bytes or not self.signature:
            raise ValueError("attestation signature must be nonempty bytes")

    def signed_payload(self) -> dict:
        return {
            "schema": ATTESTATION_SCHEMA,
            "installation_identity_id": self.installation_identity_id,
            "node_id": str(self.node_id),
            "public_key_sha256": self.public_key_sha256,
            "release_manifest_digest": self.release_manifest_digest,
            "signer_key_id": self.signer_key_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def message(self) -> bytes:
        return SIGNATURE_DOMAIN + _canonical(self.signed_payload())

    def digest(self) -> str:
        return sha256(_canonical(self.signed_payload())).hexdigest()


@dataclass(frozen=True)
class VerifiedInstallationAttestation:
    installation_identity_id: str
    node_id: UUID
    public_key_sha256: str
    release_manifest_digest: str
    signer_key_id: str
    digest: str


@dataclass(frozen=True)
class AutomaticAdmissionGrant:
    policy_id: str
    policy_revision: int
    initial_permission_level: int
    attestation_digest: str
    signer_key_id: str


class InstallationAttestationVerifier:
    """Verify publisher signatures against an explicit owner-approved keyring."""

    def __init__(self, trusted_keys: dict[str, Path | bytes]) -> None:
        if not isinstance(trusted_keys, dict) or not trusted_keys:
            raise ValueError("at least one trusted installation signer is required")
        loaded: dict[str, Ed25519PublicKey] = {}
        for key_id, source in trusted_keys.items():
            if type(key_id) is not str or _IDENTIFIER.fullmatch(key_id) is None:
                raise ValueError("signer key IDs must be bounded identifiers")
            if isinstance(source, Path):
                raw = source.read_bytes()
            elif isinstance(source, bytes):
                raw = source
            else:
                raise TypeError("trusted signer keys must be Path or bytes")
            try:
                key = serialization.load_pem_public_key(raw)
            except (TypeError, ValueError):
                if len(raw) != 32:
                    raise
                key = Ed25519PublicKey.from_public_bytes(raw)
            if not isinstance(key, Ed25519PublicKey):
                raise TypeError(f"trusted signer {key_id!r} is not Ed25519")
            loaded[key_id] = key
        self._keys = loaded

    def verify(
        self,
        attestation: InstallationAttestation,
        *,
        policy: AutonomyPolicy,
        expected_node_id: UUID,
        expected_public_key_sha256: str,
        now: datetime | None = None,
    ) -> VerifiedInstallationAttestation:
        if not isinstance(attestation, InstallationAttestation):
            raise PermissionError("signed installation attestation required")
        if not isinstance(policy, AutonomyPolicy):
            raise PermissionError("active autonomy policy required")
        moment = _aware(now or datetime.now(timezone.utc), "now")
        if attestation.signer_key_id not in policy.admission_signer_key_ids:
            raise PermissionError("installation signer is not approved by policy")
        key = self._keys.get(attestation.signer_key_id)
        if key is None:
            raise PermissionError("installation signer is not independently trusted")
        try:
            key.verify(attestation.signature, attestation.message())
        except InvalidSignature as exc:
            raise PermissionError("installation attestation signature is invalid") from exc
        if attestation.node_id != expected_node_id:
            raise PermissionError("attestation node identity differs from discovery")
        if attestation.public_key_sha256 != expected_public_key_sha256:
            raise PermissionError("attestation key differs from discovery")
        if not attestation.issued_at <= moment < attestation.expires_at:
            raise PermissionError("installation attestation is not currently valid")
        if moment - attestation.issued_at > MAX_ATTESTATION_LIFETIME:
            raise PermissionError("installation attestation evidence is stale")
        return VerifiedInstallationAttestation(
            installation_identity_id=attestation.installation_identity_id,
            node_id=attestation.node_id,
            public_key_sha256=attestation.public_key_sha256,
            release_manifest_digest=attestation.release_manifest_digest,
            signer_key_id=attestation.signer_key_id,
            digest=attestation.digest(),
        )


def authorize_automatic_admission(
    policy: AutonomyPolicy | None,
    candidate: FleetHost,
    *,
    node_id: UUID,
    public_key_sha256: str,
    attestation: InstallationAttestation,
    verifier: InstallationAttestationVerifier,
    now: datetime | None = None,
) -> AutomaticAdmissionGrant:
    """Apply every automatic-admission boundary before any trust mutation."""
    if policy is None:
        raise PermissionError("automatic admission requires an active autonomy policy")
    if policy.profile != PROFILE_HIGH_AUTONOMY or not (
        policy.automatic_fleet_admission
    ):
        raise PermissionError("automatic Fleet admission is not enabled by policy")
    if not policy.signed_installation_provenance_required:
        raise PermissionError("automatic admission policy lacks signed provenance")
    if not isinstance(candidate, FleetHost) or (
        candidate.lifecycle is not HostLifecycle.CANDIDATE or candidate.trusted
    ):
        raise PermissionError("automatic admission requires an untrusted candidate")
    verified = verifier.verify(
        attestation,
        policy=policy,
        expected_node_id=node_id,
        expected_public_key_sha256=public_key_sha256,
        now=now,
    )
    initial = min(policy.max_initial_permission_level, 3)
    if initial < 1:
        raise PermissionError("automatic admission permission scope is invalid")
    return AutomaticAdmissionGrant(
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        initial_permission_level=initial,
        attestation_digest=verified.digest,
        signer_key_id=verified.signer_key_id,
    )


def recheck_automatic_grant(
    policy: AutonomyPolicy | None,
    candidate: FleetHost,
    grant: AutomaticAdmissionGrant,
) -> None:
    """Revalidate policy and grant state inside the commit transaction."""
    if policy is None or not isinstance(grant, AutomaticAdmissionGrant):
        raise PermissionError("automatic admission policy proof disappeared")
    if policy.profile != PROFILE_HIGH_AUTONOMY or not (
        policy.automatic_fleet_admission
    ):
        raise PermissionError("automatic Fleet admission is no longer enabled")
    if (
        policy.policy_id != grant.policy_id
        or policy.revision != grant.policy_revision
    ):
        raise PermissionError("automatic admission policy changed during admission")
    if grant.initial_permission_level > policy.max_initial_permission_level:
        raise PermissionError("automatic admission initial scope exceeds policy")
    if not isinstance(candidate, FleetHost) or (
        candidate.lifecycle is not HostLifecycle.CANDIDATE or candidate.trusted
    ):
        raise PermissionError("automatic admission candidate is no longer eligible")
