"""D028 owner-approved signed LAN Hub under ONE canonical Platform session.

The Rust-owned Platform service is still the only supervisor/identity owner.
This internal integration creates no Hub unless an existing live service,
independently verified signed publisher catalog/package, separately pinned
recipient TLS identity, exact owner-issued Hub-serve standing grant and owner-
issued recipient peer-fetch standing grant are all available.

The service owns this listener and closes it before releasing its RUN lease.
No Core or module is required. No automatic network discovery, owner approval,
certificate/key minting, install or cache mutation is performed here.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import ssl
from typing import TYPE_CHECKING

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_signed_selection import (
    SelectedSignedLibraryTransfer, verify_selected_signed_transfer,
    verify_renewed_recipient_offer,
)
from sofia.platform.ops.library_tls_hub import ApprovedLibraryHub
from sofia.platform.ops.library_cached_source import VerifiedLibraryCacheSource
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact
from sofia.platform.run.library_source_gate import (
    CurrentLibraryHubAuthority, CurrentLibrarySourcePeerAuthorizer,
)
from sofia.platform.safe.permissions import PermissionStore

if TYPE_CHECKING:
    from sofia.platform.run.platform_service import PlatformServiceSession


def verify_renewed_serving_offer(
    *,
    original: SelectedSignedLibraryTransfer,
    raw_signed_index: bytes,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    expected_catalog_generation: int,
    publisher_key_current: Callable[[str], bool],
    now: datetime,
) -> SelectedSignedLibraryTransfer:
    """Only a newly signed SAME-artifact catalog can extend a Hub session.

    The old selected package's manifest/content digest, publisher signer,
    distribution receipt, target, source, exact revision and catalog generation
    must remain identical; a new signature or issued_at is allowed.
    """
    # Delegate the signed identity, epoch and strictly advancing freshness
    # contract to the same verifier used by the recipient; never weaken the
    # Hub's replay policy by inventing a second almost-matching version.
    renewed = verify_renewed_recipient_offer(
        original=original, renewed_signed_index=raw_signed_index,
        trusted_publisher_public_key=trusted_publisher_public_key,
        expected_publisher_key_sha256=expected_publisher_key_sha256,
        expected_catalog_generation=expected_catalog_generation,
        now=now, publisher_key_current=publisher_key_current,
    )
    if renewed.index.catalog["source"]["kind"] != "OWNER_SELECTED_HUB":
        raise ChunkTransferRejected(
            "renewal changed immutable signed Hub offer or publisher identity"
        )
    return renewed

class HostedLibraryHub:
    """Bound, explicitly opened service child, never a second supervisor."""

    def __init__(
        self, *,
        service: "PlatformServiceSession",
        bind_host: str, port: int, tls_context: ssl.SSLContext,
        transfer: PinnedChunkTransfer,
        raw_signed_index: bytes, expected_artifact_id: str,
        trusted_publisher_public_key: bytes,
        expected_publisher_key_sha256: str,
        expected_catalog_generation: int,
        publisher_key_current: Callable[[str], bool],
        package_signer_current: Callable[[str], bool],
        verify_independent_package: Callable[
            [PinnedChunkTransfer, Path], PlatformArtifact
        ],
        artifact: PlatformArtifact,
        cache: OfflineArtifactCache,
        expected_recipient_certificate_sha256: str,
        read_current_signed_index: Callable[[], bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: int = 10,
    ) -> None:
        from sofia.platform.run.platform_service import PlatformServiceSession
        if not isinstance(service, PlatformServiceSession):
            raise TypeError("canonical installed PlatformServiceSession required")
        if (not isinstance(artifact, PlatformArtifact)
                or not isinstance(cache, OfflineArtifactCache)
                or not isinstance(transfer, PinnedChunkTransfer)):
            raise ChunkTransferRejected("independently verified B1 asset, cache and signed transfer required")
        for callback in (publisher_key_current, package_signer_current, verify_independent_package):
            if not callable(callback):
                raise ChunkTransferRejected("independent trusted publisher/package checks required")
        if clock is not None and not callable(clock):
            raise TypeError("trusted installed service clock required")
        if read_current_signed_index is not None and not callable(read_current_signed_index):
            raise TypeError("installed publisher catalog renewal supplier required")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        instant = self._clock()
        if not isinstance(instant, datetime) or instant.utcoffset() is None:
            raise ChunkTransferRejected("trusted current service clock required")
        status = service.status()
        source_id = status["platform_id"]
        generation = status["generation"]
        if (transfer.source_platform_id != source_id
                or transfer.target_platform_id == source_id
                or status["operator_stop"] is not False):
            raise ChunkTransferRejected("source Hub service not enrolled, active, or STOP-free")

        self._offer = verify_selected_signed_transfer(
            raw_signed_index=raw_signed_index,
            transfer=transfer, expected_artifact_id=expected_artifact_id,
            trusted_publisher_public_key=trusted_publisher_public_key,
            expected_publisher_key_sha256=expected_publisher_key_sha256,
            expected_catalog_generation=expected_catalog_generation,
            now=instant, publisher_key_current=publisher_key_current,
        )
        if self._offer.index.catalog["source"]["kind"] != "OWNER_SELECTED_HUB":
            raise ChunkTransferRejected("only an owner-selected Hub catalog can authorize Hub serving")
        if (artifact.artifact_id != self._offer.artifact_id
                or artifact.version != self._offer.version
                or artifact.signer_key_id != self._offer.signer_key_id
                or artifact.sha256 != transfer.content_sha256):
            raise ChunkTransferRejected("B1 signed package identity differs from publisher catalog")

        # A cache entry is never trusted just because its filename is a SHA.
        # The *installed* B1 verifier must independently verify the package
        # under its current trusted root. The Hub does not accept a verifier
        # or artifact description from its remote TLS client.
        path = cache.resolve(artifact)
        proven = verify_independent_package(transfer, path)
        if (not isinstance(proven, PlatformArtifact) or proven != artifact
                or package_signer_current(artifact.signer_key_id) is not True):
            raise ChunkTransferRejected("current independently trusted B1 package verification unavailable")
        # Re-resolve and FULLY digest ONCE at signed selection, then the B1
        # immutable inode guard and chunk reader check before/after EACH read.
        # An 8GiB asset must not be SHA256-rehashed 8192 times.
        self._verified_cache = VerifiedLibraryCacheSource(
            cache=cache, artifact=artifact,
        )
        self._verified_cache.current_path(transfer)

        self.service = service
        self.transfer = transfer
        self.artifact = artifact
        self.cache = cache
        self._publisher_key_current = publisher_key_current
        self._package_signer_current = package_signer_current
        self._source_generation = generation
        self._expected_key_sha = expected_publisher_key_sha256
        self._trusted_public_key = trusted_publisher_public_key
        self._expected_catalog_generation = expected_catalog_generation
        self._read_index = read_current_signed_index
        self._latest_offer = self._offer

        permissions = PermissionStore(service.storage.path)
        self._hub_grant = CurrentLibraryHubAuthority(
            permissions=permissions, stop=service.stop,
            current_status=service.status,
            source_platform_id=source_id, source_generation=generation,
            bind_host=bind_host, bind_port=port, clock=self._clock,
        )

        def current_publisher(t: PinnedChunkTransfer) -> bool:
            try:
                at = self._clock()
                if (t != self.transfer or not isinstance(at, datetime)
                        or at.utcoffset() is None
                        or self._publisher_key_current(self._expected_key_sha) is not True
                        or self._package_signer_current(self.artifact.signer_key_id) is not True
                        or self._hub_grant() is not True
                        or not self._offer.still_matches()):
                    return False
                # A multi-GiB LAN transfer outlives one short-lived index.
                # Owner's installed B1 publisher may renew the SAME signed
                # artifact selection. Each renewal independently authenticates
                # exact publisher root, target, source, manifest/content SHA,
                # signer/receipt identity, epoch, revocation and license.
                # If no trusted renewal source is installed, expiry denies.
                candidate = self._latest_offer
                if self._read_index is not None:
                    current_bytes = self._read_index()
                    if type(current_bytes) is not bytes:
                        return False
                    from hashlib import sha256
                    if sha256(current_bytes).hexdigest() != candidate.index.signed_index_sha256:
                        candidate = verify_renewed_serving_offer(
                            original=candidate,
                            raw_signed_index=current_bytes,
                            trusted_publisher_public_key=self._trusted_public_key,
                            expected_publisher_key_sha256=self._expected_key_sha,
                            expected_catalog_generation=self._expected_catalog_generation,
                            now=at,
                            publisher_key_current=self._publisher_key_current,
                        )
                        self._latest_offer = candidate
                index = candidate.index
                fresh_until = datetime.fromisoformat(
                    index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                moment = at.astimezone(timezone.utc)
                return (candidate.artifact_id == self._offer.artifact_id
                        and candidate.signer_key_id == self._offer.signer_key_id
                        and candidate.signature_receipt_ref == self._offer.signature_receipt_ref
                        and candidate.version == self._offer.version
                        and index.catalog["source"]["kind"] == "OWNER_SELECTED_HUB"
                        and index.source_platform_id == self.transfer.source_platform_id
                        and index.target_platform_id == self.transfer.target_platform_id
                        and index.catalog_revision == self.transfer.catalog_revision
                        and moment < index.expires_at
                        and moment < fresh_until
                        and candidate.still_matches())
            except (ValueError, TypeError, PermissionError, RuntimeError, OSError):
                return False

        self._current_publisher = current_publisher
        self._peer = CurrentLibrarySourcePeerAuthorizer(
            permissions=permissions, hub_enabled=self._hub_grant,
            signed_transfer=transfer,
            expected_recipient_certificate_sha256=expected_recipient_certificate_sha256,
            publisher_current=current_publisher, clock=self._clock,
        )
        self._hub = ApprovedLibraryHub(
            bind_host=bind_host, port=port, tls_context=tls_context,
            owner_enabled=self._hub_grant,
            lookup_transfer=lambda digest: (
                self.transfer if digest == self.transfer.content_sha256
                and current_publisher(self.transfer) else None
            ),
            authorize_peer=self._peer,
            publisher_current=current_publisher,
            resolve_verified_cache=lambda t: (
                self._verified_cache.current_path(t)
                if t == self.transfer and current_publisher(t) else
                (_ for _ in ()).throw(
                    ChunkTransferRejected("Hub B1 asset or publisher no longer current")
                )
            ),
            timeout_seconds=timeout_seconds,
        )
        self._closed = False
        self.endpoint = self._hub.open()

    def _require_current(self) -> None:
        if self._closed or self._hub_grant() is not True or not self._current_publisher(self.transfer):
            self.close()
            raise ChunkTransferRejected("owner-approved Hub session STOP, revoked or stale")

    def serve_once(self) -> int:
        """Handle one bounded TLS connection, then return to Platform owner."""
        self._require_current()
        try:
            return self._hub.serve_once()
        except Exception:
            # A per-client invalid frame does not create a new grant; a
            # withdrawn owner Hub approval must tear down the listener now.
            if not self._hub_grant():
                self.close()
            raise

    def serve_bounded(self, *, max_connections: int) -> int:
        if type(max_connections) is not int or not 1 <= max_connections <= 10000:
            raise ChunkTransferRejected("explicit bounded owner Hub connection budget required")
        total = 0
        for _ in range(max_connections):
            total += self.serve_once()
        return total

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._hub.close()

    def __enter__(self) -> "HostedLibraryHub":
        self._require_current()
        return self

    def __exit__(self, *_):
        self.close()
