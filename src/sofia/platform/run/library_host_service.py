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
    verify_selected_signed_transfer,
)
from sofia.platform.ops.library_tls_hub import ApprovedLibraryHub
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact
from sofia.platform.run.library_source_gate import (
    CurrentLibraryHubAuthority, CurrentLibrarySourcePeerAuthorizer,
)
from sofia.platform.safe.permissions import PermissionStore

if TYPE_CHECKING:
    from sofia.platform.run.platform_service import PlatformServiceSession


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

        self.service = service
        self.transfer = transfer
        self.artifact = artifact
        self.cache = cache
        self._publisher_key_current = publisher_key_current
        self._package_signer_current = package_signer_current
        self._source_generation = generation
        self._expected_key_sha = expected_publisher_key_sha256

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
                return (t == self.transfer
                        and isinstance(at, datetime) and at.utcoffset() is not None
                        and at.astimezone(timezone.utc) < self._offer.index.expires_at
                        and at.astimezone(timezone.utc) < datetime.fromisoformat(
                            self._offer.index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
                        ).astimezone(timezone.utc)
                        and self._offer.still_matches()
                        and self._publisher_key_current(self._expected_key_sha) is True
                        and self._package_signer_current(self.artifact.signer_key_id) is True
                        and self._hub_grant() is True)
            except (ValueError, PermissionError, RuntimeError, OSError):
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
                self.cache.resolve(self.artifact)
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
