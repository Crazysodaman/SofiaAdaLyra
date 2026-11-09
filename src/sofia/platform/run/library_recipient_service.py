"""D028 recipient transfer owned by the one installed Platform RUN session.

No new daemon, listener, cert authority, signer, credential store, index
author or installer. The canonical installed Platform owns receiver/cache,
its independent publisher key, current SAFE/STOP stores and enrolled mTLS
socket constructor. This coordinator only composes those existing owners.

A transport grant is NOT a B1 cache-admission grant. The per-chunk
CurrentRecipientPeerAuthorizer consumes no approval, checks the actual peer
certificate and re-reads SAFE on every chunk; a distinct one-use owner proof
is consumed by library_verified_handoff only when complete bytes were
independently publisher-verified. No install or Core activation follows.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import re
import ssl
from typing import TYPE_CHECKING

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_recipient_pipeline import (
    acquire_from_independently_signed_index,
)
from sofia.platform.ops.library_signed_selection import verify_selected_signed_transfer
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact
from sofia.platform.run.library_peer_gate import (
    CurrentRecipientPeerAuthorizer, LIBRARY_PEER_SCOPE, CAPABILITY,
)
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.safe.permissions import PermissionStore

if TYPE_CHECKING:
    from sofia.platform.run.platform_service import PlatformServiceSession

_SHA = re.compile(r"[0-9a-f]{64}\Z")


class HostedLibraryRecipient:
    """Bounded, owner-granted transfer session; no background work."""

    def __init__(
        self, *, service: "PlatformServiceSession",
        transfer: PinnedChunkTransfer, expected_artifact_id: str,
        receiver: ChunkedArtifactReceiver, cache: OfflineArtifactCache,
        open_enrolled_tls: Callable[[], ssl.SSLSocket],
        enrolled_source_certificate_sha256: str,
        verify_independent_package: Callable[
            [PinnedChunkTransfer, Path], PlatformArtifact
        ],
        package_signer_current: Callable[[str], bool],
        signed_catalog_source: Callable[[], InstalledSignedCatalogSource],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        from sofia.platform.run.platform_service import PlatformServiceSession
        if not isinstance(service, PlatformServiceSession):
            raise TypeError("installed PlatformServiceSession required")
        if (not isinstance(transfer, PinnedChunkTransfer)
                or transfer.artifact_kind not in {"platform_release", "sdk"}
                or not isinstance(receiver, ChunkedArtifactReceiver)
                or not isinstance(cache, OfflineArtifactCache)):
            raise ChunkTransferRejected("reviewed B1 transfer and canonical stores required")
        if (type(enrolled_source_certificate_sha256) is not str
                or _SHA.fullmatch(enrolled_source_certificate_sha256) is None):
            raise ChunkTransferRejected("independently enrolled source certificate pin required")
        if not all(callable(v) for v in (
            open_enrolled_tls, verify_independent_package,
            package_signer_current, signed_catalog_source,
        )):
            raise TypeError("installed publisher, TLS and B1 authorities required")
        if clock is not None and not callable(clock):
            raise TypeError("canonical service clock required")
        status = service.status()
        if (status.get("platform_id") != transfer.target_platform_id
                or status.get("generation") != transfer.generation
                or status.get("operator_stop") is not False):
            raise ChunkTransferRejected("recipient Platform identity, RUN or STOP mismatch")
        self.service = service
        self.transfer = transfer
        self.artifact_id = expected_artifact_id
        self.receiver = receiver
        self.cache = cache
        self.open_tls = open_enrolled_tls
        self.cert_sha256 = enrolled_source_certificate_sha256
        self.verify_package = verify_independent_package
        self.package_signer_current = package_signer_current
        self.signed_catalog_source = signed_catalog_source
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.permissions = PermissionStore(service.storage.path)
        self.peer = CurrentRecipientPeerAuthorizer(
            permissions=self.permissions, stop=service.stop,
            current_status=service.status, signed_transfer=transfer,
        )
        # Signed catalog must be independently verified before reserving any
        # transfer bytes. Never allow an absent index or a UI-provided key.
        source = self._source()
        now = self._now()
        self.original_offer = verify_selected_signed_transfer(
            raw_signed_index=source.raw_signed_index,
            transfer=transfer, expected_artifact_id=expected_artifact_id,
            trusted_publisher_public_key=source.trusted_publisher_public_key,
            expected_publisher_key_sha256=source.expected_publisher_key_sha256,
            expected_catalog_generation=source.expected_catalog_generation,
            now=now, publisher_key_current=source.publisher_key_current,
        )

    def _now(self) -> datetime:
        moment = self.clock()
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ChunkTransferRejected("aware current recipient clock required")
        return moment.astimezone(timezone.utc)

    def _source(self) -> InstalledSignedCatalogSource:
        source = self.signed_catalog_source()
        if not isinstance(source, InstalledSignedCatalogSource):
            raise ChunkTransferRejected("independently installed publisher catalog required")
        if (source.expected_source_platform_id != self.transfer.source_platform_id
                or source.minimum_catalog_revision > self.transfer.catalog_revision):
            raise ChunkTransferRejected("installed publisher source or rollback floor changed")
        if hasattr(self, "original_offer"):
            if (source.expected_publisher_key_sha256
                    != self.original_offer.index.publisher_key_sha256
                    or source.expected_catalog_generation
                    != self.original_offer.index.catalog_generation
                    or not self.original_offer.still_matches()):
                raise ChunkTransferRejected("pinned publisher root, epoch or signed selection changed")
        return source

    def _current(
        self, transfer: PinnedChunkTransfer, *, required_chunk_bytes: int = 1,
    ) -> bool:
        """Only exact signed enrolled scope, current RUN and owner STOP-free."""
        try:
            status = self.service.status()
            if (transfer != self.transfer
                    or status.get("platform_id") != transfer.target_platform_id
                    or status.get("generation") != transfer.generation
                    or status.get("operator_stop") is not False
                    or self.service.stop.current().active):
                return False
            now = self._now()
            expected = {
                "source_platform_id": transfer.source_platform_id,
                "target_platform_id": transfer.target_platform_id,
                "certificate_sha256": self.cert_sha256,
                "manifest_digest": transfer.manifest_sha256,
                "content_digest": transfer.content_sha256,
                "artifact_kind": transfer.artifact_kind,
                "catalog_revision": transfer.catalog_revision,
                "license_distribution": transfer.license_distribution,
                "data_class": transfer.data_class,
            }
            for grant in self.permissions.grants(active_only=False):
                if (grant.capability != CAPABILITY or type(grant.scope) is not dict
                        or set(grant.scope) != LIBRARY_PEER_SCOPE):
                    continue
                limit_chunk = grant.scope.get("max_chunk_bytes")
                limit_total = grant.scope.get("max_total_bytes")
                if (type(limit_chunk) is not int
                        or not 1 <= limit_chunk <= 1024 * 1024
                        or type(required_chunk_bytes) is not int
                        or not 1 <= required_chunk_bytes <= limit_chunk
                        or type(limit_total) is not int
                        or limit_total < transfer.size_bytes):
                    continue
                scope = {
                    **expected, "max_chunk_bytes": limit_chunk,
                    "max_total_bytes": limit_total,
                }
                if grant.matches(scope, now=now):
                    return True
            return False
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError):
            return False

    def _publisher_current(self, transfer: PinnedChunkTransfer) -> bool:
        try:
            source = self._source()
            return (
                transfer == self.transfer
                and source.publisher_key_current(source.expected_publisher_key_sha256)
                is True
                and self.package_signer_current(self.original_offer.signer_key_id)
                is True
                and self._current(transfer) is True
            )
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError):
            return False

    def acquire(
        self, *, approval_id: str,
        start_offset: int = 0, chunk_bytes: int = 1024 * 1024,
        max_chunks: int = 128,
    ) -> dict[str, object]:
        """One foreground, bounded action under existing owner SAFE scopes."""
        if type(approval_id) is not str or not approval_id.strip():
            raise PermissionError("separate one-use owner cache approval required")
        if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= 1024 * 1024:
            raise ChunkTransferRejected("bounded installed recipient chunk size required")
        if type(max_chunks) is not int or not 1 <= max_chunks <= 10000:
            raise ChunkTransferRejected("bounded installed recipient chunk budget required")
        if not self._current(
            self.transfer, required_chunk_bytes=min(chunk_bytes, self.transfer.size_bytes),
        ):
            raise PermissionError("current source peer enrollment, chunk scope or recipient STOP denied")
        source = self._source()
        if not self._publisher_current(self.transfer):
            raise ChunkTransferRejected("independent publisher or package signer revoked")

        def verified_package(t: PinnedChunkTransfer, path: Path) -> PlatformArtifact:
            if not self._publisher_current(t):
                raise ChunkTransferRejected("package publisher or owner grant revoked")
            proven = self.verify_package(t, path)
            if (not isinstance(proven, PlatformArtifact)
                    or proven.signer_key_id != self.original_offer.signer_key_id
                    or proven.sha256 != t.content_sha256
                    or proven.artifact_id != self.original_offer.artifact_id
                    or proven.version != self.original_offer.version):
                raise ChunkTransferRejected("independent B1 signature differs from selection")
            return proven

        return acquire_from_independently_signed_index(
            raw_signed_index=source.raw_signed_index,
            transfer=self.transfer, expected_artifact_id=self.artifact_id,
            trusted_publisher_public_key=source.trusted_publisher_public_key,
            expected_publisher_key_sha256=source.expected_publisher_key_sha256,
            expected_catalog_generation=source.expected_catalog_generation,
            publisher_key_current=source.publisher_key_current,
            receiver=self.receiver, cache=self.cache,
            open_enrolled_tls=self.open_tls,
            expected_peer_certificate_sha256=self.cert_sha256,
            authorize_peer=self.peer,
            publisher_current=self._publisher_current,
            current_host_admit=self._current,
            verify_independent_publisher=verified_package,
            canonical_safe_state=self.service.storage.path,
            approval_id=approval_id,
            start_offset=start_offset, chunk_bytes=chunk_bytes,
            max_chunks=max_chunks, now=self._now(), current_time=self._now,
            read_current_signed_index=lambda: self._source().raw_signed_index,
        )
