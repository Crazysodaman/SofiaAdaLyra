"""D028-00/02 exact complete publisher-signed module manifest verification.

The existing legacy package_identity_digest() is a hash of unsigned policy
and remains unchanged for older SDK receipts. Artifact Library manifest_digest
instead pins the complete canonical signed manifest bytes including signature.
The archive content SHA-256 remains a *third* independent digest.

A recipient MUST obtain the 32-byte Ed25519 public key and its key fingerprint
from an independently provisioned B/D trust root, never the remote Hub/index.
No package files are read, installed, imported or activated here. A verified
manifest is still not an authorized CAS/install or dependency receipt.
"""
from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.modules.package import (
    PackageManifestError, SignedModuleManifest, parse_signed_manifest,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MANIFEST = 128 * 1024


class SignedModuleLibraryRejected(PermissionError):
    """Independent current publisher signature/identity is unavailable."""


def _unique_properties(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise SignedModuleLibraryRejected("duplicate signed module manifest property")
        out[key] = value
    return out


@dataclass(frozen=True, slots=True)
class IndependentlyVerifiedModuleManifest:
    manifest: SignedModuleManifest
    publisher_signed_manifest_sha256: str
    unsigned_policy_identity_sha256: str
    artifact_set_identity_sha256: str
    publisher_public_key_sha256: str
    trust_ref: str

    def still_matches(self, candidate_bytes: bytes) -> bool:
        """Only exact signed bytes match, never just an unsigned policy hash."""
        return (
            type(candidate_bytes) is bytes
            and sha256(candidate_bytes).hexdigest()
            == self.publisher_signed_manifest_sha256
        )


def verify_publisher_signed_module_manifest(
    *, raw_signed_manifest: bytes,
    expected_signed_manifest_sha256: str,
    independent_publisher_public_key: bytes,
    expected_publisher_public_key_sha256: str,
    expected_trust_ref: str,
    publisher_current: Callable[[str], bool],
) -> IndependentlyVerifiedModuleManifest:
    if (type(raw_signed_manifest) is not bytes
            or not 1 <= len(raw_signed_manifest) <= _MAX_MANIFEST
            or type(expected_signed_manifest_sha256) is not str
            or _SHA.fullmatch(expected_signed_manifest_sha256) is None
            or sha256(raw_signed_manifest).hexdigest()
            != expected_signed_manifest_sha256):
        raise SignedModuleLibraryRejected("exact complete signed manifest bytes required")
    if (type(independent_publisher_public_key) is not bytes
            or len(independent_publisher_public_key) != 32
            or type(expected_publisher_public_key_sha256) is not str
            or _SHA.fullmatch(expected_publisher_public_key_sha256) is None
            or sha256(independent_publisher_public_key).hexdigest()
            != expected_publisher_public_key_sha256
            or type(expected_trust_ref) is not str
            or not 1 <= len(expected_trust_ref) <= 200):
        raise SignedModuleLibraryRejected("independent publisher root and trust_ref required")
    if (not callable(publisher_current)
            or publisher_current(expected_trust_ref) is not True):
        raise SignedModuleLibraryRejected("publisher signing root revoked")
    try:
        document = json.loads(
            raw_signed_manifest.decode("utf-8"),
            object_pairs_hook=_unique_properties,
            parse_constant=lambda _: (_ for _ in ()).throw(
                SignedModuleLibraryRejected("nonfinite signed manifest value")
            ),
        )
        manifest = parse_signed_manifest(document)
    except (UnicodeError, ValueError, TypeError, RecursionError,
            PackageManifestError) as exc:
        raise SignedModuleLibraryRejected("invalid signed module payload") from exc
    if manifest.trust_ref != expected_trust_ref:
        raise SignedModuleLibraryRejected("signed manifest refers to another publisher trust root")
    canonical = manifest.canonical_signed_bytes()
    if canonical != raw_signed_manifest:
        raise SignedModuleLibraryRejected("manifest is not exact canonical signed bytes")
    try:
        signature = b64decode(manifest.signature_b64, validate=True)
    except (ValueError, Base64Error) as exc:
        raise SignedModuleLibraryRejected("invalid signed module Ed25519 encoding") from exc
    if len(signature) != 64:
        raise SignedModuleLibraryRejected("signed module Ed25519 signature length invalid")
    try:
        Ed25519PublicKey.from_public_bytes(independent_publisher_public_key).verify(
            signature, manifest.canonical_unsigned_bytes(),
        )
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise SignedModuleLibraryRejected("independent module publisher signature invalid") from exc
    if publisher_current(expected_trust_ref) is not True:
        raise SignedModuleLibraryRejected("publisher revoked during manifest signature validation")
    if manifest.publisher_signed_manifest_digest() != expected_signed_manifest_sha256:
        raise SignedModuleLibraryRejected("signed module manifest digest changed")
    return IndependentlyVerifiedModuleManifest(
        manifest=manifest,
        publisher_signed_manifest_sha256=expected_signed_manifest_sha256,
        unsigned_policy_identity_sha256=manifest.package_identity_digest(),
        artifact_set_identity_sha256=manifest.artifact_set_identity_digest(),
        publisher_public_key_sha256=expected_publisher_public_key_sha256,
        trust_ref=expected_trust_ref,
    )
