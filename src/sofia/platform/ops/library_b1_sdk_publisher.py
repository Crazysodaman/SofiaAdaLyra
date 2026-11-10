"""D028 personal Library: real independent B1 signed SDK package verifier.

The existing PlatformReleaseVerifier authenticates publisher identity,
source SHA, target, SDK ABI and anti-rollback floor BEFORE this adapter ever
inspects transferred bytes. Unlike the full installer, this verifies ONE
immutable SDK wheel from a signed release so a recipient need not download
all the other release assets merely to admit that wheel to B1 CAS.

The signed envelope is canonical metadata; its SHA-256 binds the exact signed
manifest, signature and signer ID in a PinnedChunkTransfer. A Hub does not
supply publisher trust, keys, rollback floor or owner approval. Only the
canonical installed B1/Fleet service can inject those authorities. The
result is cache eligible, never installed, enabled or executable.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.platform_install import (
    PlatformArtifact, PlatformKind,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_release import (
    PlatformReleaseRejected, PlatformReleaseVerifier, _component_wheel,
)
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget

SCHEMA = "aegis.library.b1.signed-sdk-envelope.v1"
MAX_ENVELOPE_BYTES = 160 * 1024
MAX_SDK_BYTES = 64 * 1024 * 1024


def canonical_signed_b1_sdk_envelope(
    *, payload: dict, signature_b64: str, signer_key_id: str,
) -> bytes:
    """Pure signed envelope serialization. Does NOT sign any content."""
    if not isinstance(payload, dict) or not isinstance(signature_b64, str):
        raise ChunkTransferRejected("bounded B1 signed release payload required")
    if type(signer_key_id) is not str or not 1 <= len(signer_key_id) <= 160:
        raise ChunkTransferRejected("exact B1 signing key ID required")
    try:
        raw = json.dumps(
            {"schema": SCHEMA, "payload": payload,
             "signature_b64": signature_b64, "signer_key_id": signer_key_id},
            sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ChunkTransferRejected("invalid B1 signed SDK envelope") from exc
    if not 1 <= len(raw) <= MAX_ENVELOPE_BYTES:
        raise ChunkTransferRejected("bounded signed SDK envelope required")
    return raw


class InstalledB1SignedSdkVerifier:
    """One signed SDK artifact, independently anchored to canonical B1."""

    def __init__(
        self, *,
        verifier: PlatformReleaseVerifier,
        installation: PlatformInstallationStore,
        signed_envelope: bytes,
        expected_source_sha: str,
        expected_target: PlatformReleaseTarget,
        trusted_signer_key_id: str,
        signer_current: Callable[[str], bool],
        expected_parent_manifest_sha256: str | None = None,
        state_schema_revision: int = 1,
    ) -> None:
        if not isinstance(verifier, PlatformReleaseVerifier):
            raise TypeError("independent installed B1 release verifier required")
        if not isinstance(installation, PlatformInstallationStore):
            raise TypeError("single canonical B1 receipt/floor store required")
        if (type(signed_envelope) is not bytes
                or not 1 <= len(signed_envelope) <= MAX_ENVELOPE_BYTES
                or type(trusted_signer_key_id) is not str
                or not trusted_signer_key_id
                or not callable(signer_current)):
            raise ChunkTransferRejected(
                "immutable bounded externally trusted B1 package identity required"
            )
        if not isinstance(expected_target, PlatformReleaseTarget):
            raise TypeError("installed recipient target required")
        self.verifier = verifier
        self.installation = installation
        self.raw = signed_envelope
        self.digest = sha256(signed_envelope).hexdigest()
        self.source_sha = expected_source_sha
        self.target = expected_target
        self.trusted_signer = trusted_signer_key_id
        self.signer_current = signer_current
        self.parent_digest = expected_parent_manifest_sha256
        self.state_revision = state_schema_revision
        self._manifest, self._asset = self._verify_signed_scope()

    def _verify_signed_scope(self):
        try:
            envelope = loads_strict_model_json(self.raw.decode("utf-8"))
        except (UnicodeError, ValueError, TypeError) as exc:
            raise ChunkTransferRejected(
                "unreviewed signed B1 envelope JSON"
            ) from exc
        if (type(envelope) is not dict
                or set(envelope) != {
                    "schema", "payload", "signature_b64", "signer_key_id",
                } or envelope["schema"] != SCHEMA
                or envelope["signer_key_id"] != self.trusted_signer
                or canonical_signed_b1_sdk_envelope(
                    payload=envelope["payload"],
                    signature_b64=envelope["signature_b64"],
                    signer_key_id=envelope["signer_key_id"],
                ) != self.raw):
            raise ChunkTransferRejected("noncanonical B1 signed SDK envelope")
        if self.signer_current(self.trusted_signer) is not True:
            raise ChunkTransferRejected("B1 release publisher revoked")
        floor = max(1, self.installation.revision_floor())
        manifest = self.verifier.verify_manifest_reference(
            envelope["payload"],
            signature_b64=envelope["signature_b64"],
            signer_key_id=self.trusted_signer,
            expected_source_sha=self.source_sha,
            expected_target=self.target,
            minimum_revision=floor,
            expected_parent_manifest_sha256=self.parent_digest,
            state_schema_revision=self.state_revision,
        )
        matching = tuple(
            asset for asset in manifest.assets if asset.kind == "sdk"
        )
        if len(matching) != 1 or not 1 <= matching[0].reference.size_bytes <= MAX_SDK_BYTES:
            raise ChunkTransferRejected("exact signed bounded SDK release asset required")
        if (self.installation.revision_floor() > manifest.revision
                or self.signer_current(self.trusted_signer) is not True):
            raise ChunkTransferRejected("B1 floor advanced or publisher revoked")
        return manifest, matching[0]

    @property
    def signed_manifest_sha256(self) -> str:
        """SHA-256 of exact complete signature-bearing B1 SDK envelope."""
        return self.digest

    def __call__(
        self, transfer: PinnedChunkTransfer, locally_received: Path,
    ) -> PlatformArtifact:
        """Re-verify exact signed B1 bytes, SDK wheel and current floor.

        A typed PlatformArtifact returned here is still NOT proof of owner
        permission to import, install or execute. The separate B1 handoff
        must consume an exact one-use SAFE approval before cache mutation.
        """
        if (not isinstance(transfer, PinnedChunkTransfer)
                or transfer.artifact_kind != "sdk"
                or transfer.manifest_sha256 != self.digest
                or transfer.content_sha256 != self._asset.reference.sha256
                or transfer.size_bytes != self._asset.reference.size_bytes
                or transfer.license_distribution != "permitted"
                or transfer.data_class != "public"
                or transfer.catalog_revision < self._manifest.revision):
            raise ChunkTransferRejected(
                "recipient transfer differs from independently signed B1 SDK"
            )
        current_manifest, current_asset = self._verify_signed_scope()
        if current_manifest != self._manifest or current_asset != self._asset:
            raise ChunkTransferRejected("signed B1 SDK policy changed during transfer")
        if not isinstance(locally_received, Path):
            raise ChunkTransferRejected("canonical quarantine file required")
        try:
            digest, data = read_artifact_file(
                locally_received, self._asset.reference.size_bytes,
                include_data=True,
            )
            if digest != transfer.content_sha256:
                raise ChunkTransferRejected("received SDK content SHA differs from signed B1")
            _component_wheel(
                locally_received, "sdk", self._manifest.version, data,
            )
        except (OSError, ValueError, TypeError, PlatformReleaseRejected) as exc:
            raise ChunkTransferRejected(
                "received signed SDK code violates B1 package policy"
            ) from exc
        if (self.signer_current(self.trusted_signer) is not True
                or self.installation.revision_floor() > self._manifest.revision):
            raise ChunkTransferRejected(
                "B1 signing root revoked or rollback floor advanced during SDK review"
            )
        return PlatformArtifact(
            artifact_id=self._manifest.release_id,
            version=self._manifest.version,
            platform=(
                PlatformKind.WINDOWS
                if self.target is PlatformReleaseTarget.WINDOWS_X86_64
                else PlatformKind.LINUX
            ),
            architecture="x86_64",
            sha256=transfer.content_sha256,
            signer_key_id=self.trusted_signer,
            signature_verified=True,
            source="independent-b1-signed-sdk-envelope",
        )
