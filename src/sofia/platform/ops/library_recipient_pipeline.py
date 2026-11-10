"""D028 recipient pipeline: exact selected peer bytes -> signed cache admission.

Internal Platform service orchestration, not an exposed network or UI API.
The selected publisher-signed transfer, current enrolled mTLS connector,
current SAFE/STOP scopes, independent B1 release verifier and one-use owner
proof ALL originate from the canonical installed service. A Hub never supplies
any of them. Installation and activation are separate later operations.

A bounded transfer may legitimately end partially: this is reported as
RECEIVING with zero verified bytes. A caller can explicitly resume with the
returned offset and the same signed transfer and enrolled certificate pin.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import ssl
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import MAX_CHUNK
from sofia.platform.ops.library_tls_resumable_fetch import fetch_resumable_chunks
from sofia.platform.ops.library_verified_handoff import admit_signed_transferred_asset
from sofia.platform.ops.library_signed_selection import (
    verify_selected_signed_transfer, verify_renewed_recipient_offer,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact


def acquire_selected_signed_platform_asset(
    *,
    transfer: PinnedChunkTransfer,
    receiver: ChunkedArtifactReceiver,
    cache: OfflineArtifactCache,
    open_enrolled_tls: Callable[[], ssl.SSLSocket],
    expected_peer_certificate_sha256: str,
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    current_host_admit: Callable[[PinnedChunkTransfer], bool],
    verify_independent_publisher: Callable[[PinnedChunkTransfer, Path], PlatformArtifact],
    canonical_safe_state: Path | str,
    approval_id: str,
    start_offset: int = 0,
    chunk_bytes: int = MAX_CHUNK,
    max_chunks: int = 128,
    now: datetime | None = None,
) -> dict[str, object]:
    """Run one bounded acquisition attempt, fail closed on missing authority.

    No automatic retry, hidden WAN fallback, installer call, Core startup,
    receipt fabrication, or garbage collection. Do not call this outside the
    service until owner-approved D028-00 authenticated wire contracts exist.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("selected signed transfer is required")
    if transfer.artifact_kind not in {"platform_release", "sdk"}:
        raise ChunkTransferRejected("selected artifact uses separate module/model pipeline")
    if not isinstance(receiver, ChunkedArtifactReceiver) or not isinstance(cache, OfflineArtifactCache):
        raise ChunkTransferRejected("canonical recipient stores required")
    if not callable(current_host_admit) or current_host_admit(transfer) is not True:
        raise PermissionError("current SAFE/STOP enrolled recipient denied")
    if not callable(publisher_current) or publisher_current(transfer) is not True:
        raise ChunkTransferRejected("signed publisher is not current")

    # A complete artifact may survive a crash or a denied B1 owner approval
    # with its immutable signed transfer scope deliberately retained. Do NOT
    # redownload it, invent a new TLS grant or discard it because the peer
    # is temporarily offline. Recheck the signed plan, current SAFE/STOP,
    # publisher signature, whole-object digest and independent one-use B1
    # owner approval through the exact existing admission path.
    def current_signed_plan(t: PinnedChunkTransfer) -> bool:
        return (
            t == transfer
            and publisher_current(t) is True
            and current_host_admit(t) is True
        )

    if receiver.pending_signed_cache_admission(
        transfer, authorize=current_signed_plan,
    ):
        if type(start_offset) is not int or start_offset not in (
            0, transfer.size_bytes,
        ):
            raise ChunkTransferRejected(
                "completed quarantine retry cursor differs from signed transfer"
            )
        admission = admit_signed_transferred_asset(
            transfer=transfer, receiver=receiver, cache=cache,
            canonical_safe_state=canonical_safe_state, approval_id=approval_id,
            verify_independent_publisher=verify_independent_publisher,
            publisher_current=publisher_current,
            current_host_admit=current_host_admit, now=now,
        )
        return {
            **admission,
            "source_platform_id": transfer.source_platform_id,
            "catalog_revision": transfer.catalog_revision,
            "received_bytes": transfer.size_bytes,
            "verified_bytes": transfer.size_bytes,
            "total_bytes": transfer.size_bytes,
            "network_attempted": False,
            "reused_complete_quarantine": True,
        }

    received = fetch_resumable_chunks(
        transfer=transfer, receiver=receiver,
        open_enrolled_tls=open_enrolled_tls,
        expected_peer_certificate_sha256=expected_peer_certificate_sha256,
        authorize_peer=authorize_peer, publisher_current=publisher_current,
        chunk_bytes=chunk_bytes, max_chunks=max_chunks,
        start_offset=start_offset,
    )
    if received < transfer.size_bytes:
        # Bytes are present only in quarantine; do not claim independent
        # signed verification, B1 cache receipt, or installed state.
        return {
            "schema": "aegis.platform.library.recipient-progress.v1",
            "content_digest": transfer.content_sha256,
            "manifest_digest": transfer.manifest_sha256,
            "source_platform_id": transfer.source_platform_id,
            "target_platform_id": transfer.target_platform_id,
            "catalog_revision": transfer.catalog_revision,
            "received_bytes": received,
            "verified_bytes": 0,
            "total_bytes": transfer.size_bytes,
            "cache_state": "RECEIVING",
            "install_executed": False,
            "installed": None,
            "active": None,
            "owner_proof_consumed": False,
        }
    if received != transfer.size_bytes:
        raise ChunkTransferRejected("transfer exceeded signed selected content")
    admission = admit_signed_transferred_asset(
        transfer=transfer, receiver=receiver, cache=cache,
        canonical_safe_state=canonical_safe_state, approval_id=approval_id,
        verify_independent_publisher=verify_independent_publisher,
        publisher_current=publisher_current,
        current_host_admit=current_host_admit,
        now=now,
    )
    return {
        **admission,
        "received_bytes": received,
        "verified_bytes": received,
        "total_bytes": transfer.size_bytes,
        "source_platform_id": transfer.source_platform_id,
        "catalog_revision": transfer.catalog_revision,
    }



def acquire_from_independently_signed_index(
    *,
    raw_signed_index: bytes,
    expected_artifact_id: str,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    expected_catalog_generation: int,
    publisher_key_current: Callable[[str], bool],
    transfer: PinnedChunkTransfer,
    receiver: ChunkedArtifactReceiver,
    cache: OfflineArtifactCache,
    open_enrolled_tls: Callable[[], ssl.SSLSocket],
    expected_peer_certificate_sha256: str,
    authorize_peer: Callable,
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    current_host_admit: Callable[[PinnedChunkTransfer], bool],
    verify_independent_publisher: Callable[[PinnedChunkTransfer, Path], PlatformArtifact],
    canonical_safe_state: Path | str,
    approval_id: str,
    start_offset: int = 0,
    chunk_bytes: int = MAX_CHUNK,
    max_chunks: int = 128,
    now: datetime | None = None,
    current_time: Callable[[], datetime] | None = None,
    read_current_signed_index: Callable[[], bytes] | None = None,
) -> dict[str, object]:
    """Verify publisher-signed selection and run bounded B1 acquisition.

    This deliberately requires separate publisher index trust, transport
    enrollment, package-signature verification and owner SAFE/STOP authority.
    None of those can be replaced by a Hub-provided boolean or UI selection.
    """
    moment = datetime.now(timezone.utc) if now is None else now
    if current_time is not None and not callable(current_time):
        raise ChunkTransferRejected("canonical service clock required")
    if read_current_signed_index is not None and not callable(read_current_signed_index):
        raise ChunkTransferRejected("installed signed catalog renewal supplier required")
    offer = verify_selected_signed_transfer(
        raw_signed_index=raw_signed_index, transfer=transfer,
        expected_artifact_id=expected_artifact_id,
        trusted_publisher_public_key=trusted_publisher_public_key,
        expected_publisher_key_sha256=expected_publisher_key_sha256,
        expected_catalog_generation=expected_catalog_generation,
        now=moment, publisher_key_current=publisher_key_current,
    )
    if not offer.still_matches():
        raise ChunkTransferRejected("independently signed catalog changed after review")

    # A large transfer may span multiple short-lived signed catalog pages.
    # Keep a single immutable transfer pin, reauthenticate refreshed publisher
    # index ONLY as its freshness nears expiry. Never accept newly selected
    # items, changed signatures/receipts, a different recipient or generation.
    active_offer = offer
    active_raw = raw_signed_index

    def _clock() -> datetime:
        checked = (datetime.now(timezone.utc) if current_time is None
                   else current_time())
        if not isinstance(checked, datetime) or checked.utcoffset() is None:
            raise ChunkTransferRejected("aware canonical recipient clock required")
        return checked.astimezone(timezone.utc)

    def current_publisher(t: PinnedChunkTransfer) -> bool:
        nonlocal active_offer, active_raw
        try:
            checked_at = _clock()
            if (t != transfer or publisher_key_current(expected_publisher_key_sha256) is not True
                    or publisher_current(t) is not True
                    or not offer.still_matches() or not active_offer.still_matches()):
                return False
            fresh_until = datetime.fromisoformat(
                active_offer.index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            if (read_current_signed_index is not None
                    and checked_at + timedelta(seconds=15)
                    >= min(active_offer.index.expires_at, fresh_until)):
                new_raw = read_current_signed_index()
                if type(new_raw) is not bytes:
                    return False
                if new_raw != active_raw:
                    newer = verify_renewed_recipient_offer(
                        # Compare against latest accepted signed page, not
                        # original: otherwise a reissued older page could
                        # roll back freshness after two successful renewals.
                        original=active_offer,
                        renewed_signed_index=new_raw,
                        trusted_publisher_public_key=trusted_publisher_public_key,
                        expected_publisher_key_sha256=expected_publisher_key_sha256,
                        expected_catalog_generation=expected_catalog_generation,
                        now=checked_at, publisher_key_current=publisher_key_current,
                    )
                    active_offer, active_raw = newer, new_raw
                    fresh_until = datetime.fromisoformat(
                        newer.index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
            return (checked_at < active_offer.index.expires_at
                    and checked_at < fresh_until
                    and offer.still_matches()
                    and active_offer.still_matches())
        except (ValueError, TypeError, PermissionError, RuntimeError, OSError):
            # A bad renewal does not become a "best effort" unsigned transfer.
            return False

    def verified_package(t: PinnedChunkTransfer, received: Path) -> PlatformArtifact:
        if not offer.still_matches() or current_publisher(t) is not True:
            raise ChunkTransferRejected("publisher revoked before package verification")
        artifact = verify_independent_publisher(t, received)
        if (not isinstance(artifact, PlatformArtifact)
                or artifact.sha256 != offer.transfer.content_sha256
                or artifact.signer_key_id != offer.signer_key_id
                or artifact.version != offer.version
                or artifact.artifact_id != offer.artifact_id):
            raise ChunkTransferRejected("independently signed B1 package differs from catalog")
        return artifact

    result = acquire_selected_signed_platform_asset(
        transfer=offer.transfer,
        receiver=receiver, cache=cache, open_enrolled_tls=open_enrolled_tls,
        expected_peer_certificate_sha256=expected_peer_certificate_sha256,
        authorize_peer=authorize_peer, publisher_current=current_publisher,
        current_host_admit=current_host_admit,
        verify_independent_publisher=verified_package,
        canonical_safe_state=canonical_safe_state, approval_id=approval_id,
        start_offset=start_offset, chunk_bytes=chunk_bytes,
        max_chunks=max_chunks, now=moment,
    )
    if current_publisher(transfer) is not True:
        raise ChunkTransferRejected("publisher revoked before signed acquisition receipt")
    return {
        **result,
        "selected_artifact_id": offer.artifact_id,
        "signed_index_sha256": active_offer.index.signed_index_sha256,
        "publisher_key_sha256": active_offer.index.publisher_key_sha256,
    }
