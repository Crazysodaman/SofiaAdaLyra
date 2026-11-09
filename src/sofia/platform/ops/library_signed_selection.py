"""D028 signed catalog item -> exact recipient transfer binding.

An independently verified publisher index is still NOT an owner grant or
proof of installed status. This read-only selection gate binds the immutable
catalog offer to the recipient's specific transfer tuple before acquiring
bytes over owner-enrolled TLS. No signer, listener, cache writer or installer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_signed_index import (
    VerifiedLibraryIndex, verify_signed_library_index, _utc,
)

_ITEM_KEYS = frozenset({
    "artifact_id", "kind", "version", "revision",
    "manifest_digest", "content_digest", "size_bytes", "publisher",
    "signer_key_id", "signature_scheme", "signature_receipt_ref",
    "target_os_arch", "sdk_range", "abi_range",
    "license_distribution", "data_class", "distribution_allowed",
})
_SOURCE_KEYS = frozenset({"kind", "source_id", "last_observed_at", "status"})


@dataclass(frozen=True, slots=True)
class SelectedSignedLibraryTransfer:
    index: VerifiedLibraryIndex
    transfer: PinnedChunkTransfer
    artifact_id: str
    version: str
    signer_key_id: str
    signature_receipt_ref: str

    def still_matches(self) -> bool:
        """Deny use after mutation of the verified catalog object."""
        return self.index.matches(self.index.catalog)


def verify_selected_signed_transfer(
    *,
    raw_signed_index: bytes,
    transfer: PinnedChunkTransfer,
    expected_artifact_id: str,
    trusted_publisher_public_key: bytes,
    expected_publisher_key_sha256: str,
    expected_catalog_generation: int,
    now: datetime,
    publisher_key_current: Callable[[str], bool],
) -> SelectedSignedLibraryTransfer:
    """Verify publisher signature, freshness, audience and one exact offer.

    This does not verify the signed *package* manifest. Recipient B1 must
    independently verify the installed trust root/signature and archive bytes
    again before admission, and the Platform service must enforce SAFE/STOP,
    source peer enrollment and current RUN generation on every chunk.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("typed pinned transfer required")
    if (type(expected_artifact_id) is not str
            or not 1 <= len(expected_artifact_id) <= 160):
        raise ChunkTransferRejected("explicit selected artifact ID required")
    index = verify_signed_library_index(
        raw_signed_index,
        trusted_publisher_public_key=trusted_publisher_public_key,
        expected_publisher_key_sha256=expected_publisher_key_sha256,
        expected_source_platform_id=transfer.source_platform_id,
        expected_target_platform_id=transfer.target_platform_id,
        expected_catalog_generation=expected_catalog_generation,
        minimum_catalog_revision=transfer.catalog_revision,
        now=now, publisher_key_current=publisher_key_current,
    )
    if index.catalog_revision != transfer.catalog_revision:
        raise ChunkTransferRejected("selected transfer catalog revision changed")
    source = index.catalog["source"]
    if (type(source) is not dict or set(source) != _SOURCE_KEYS
            or source["kind"] not in {"OWNER_SELECTED_HUB", "AUTHORIZED_PEER"}
            or source["source_id"] != transfer.source_platform_id
            or source["status"] != "CURRENT"):
        raise ChunkTransferRejected("signed index source is not selected enrolled peer")
    if index.expires_at <= now.astimezone(timezone.utc):
        raise ChunkTransferRejected("publisher index expired at selection")
    observed_at = _utc(source["last_observed_at"])
    moment = now.astimezone(timezone.utc)
    if observed_at > moment or moment - observed_at > timedelta(minutes=5):
        raise ChunkTransferRejected("signed peer source observation not current")
    page = index.catalog["page"]
    if (type(page) is not dict
            or set(page) != {"limit", "next_cursor", "cursor_state"}
            or page["cursor_state"] != "CURRENT"
            or type(page["limit"]) is not int or not 1 <= page["limit"] <= 128
            or len(index.catalog["items"]) > page["limit"]):
        raise ChunkTransferRejected("signed catalog page is stale or unbounded")
    matches = []
    for row in index.catalog["items"]:
        if type(row) is not dict or set(row) != _ITEM_KEYS:
            raise ChunkTransferRejected("unexpected signed catalog item schema")
        if row["artifact_id"] == expected_artifact_id:
            matches.append(row)
    if len(matches) != 1:
        raise ChunkTransferRejected("explicit signed artifact selection missing or ambiguous")
    row = matches[0]
    if (row["kind"] != transfer.artifact_kind
            or row["manifest_digest"] != transfer.manifest_sha256
            or row["content_digest"] != transfer.content_sha256
            or type(row["size_bytes"]) is not int
            or row["size_bytes"] != transfer.size_bytes
            or type(row["revision"]) is not int or row["revision"] < 1
            or row["license_distribution"] != transfer.license_distribution
            or row["data_class"] != transfer.data_class
            or row["license_distribution"] != "permitted"
            or row["data_class"] != "public"
            or row["distribution_allowed"] is not True
            or row["signature_scheme"] != "ed25519"):
        raise ChunkTransferRejected("signed selected artifact differs from pinned transfer")
    for field in ("version", "signer_key_id", "signature_receipt_ref"):
        if type(row[field]) is not str or not 1 <= len(row[field]) <= 160:
            raise ChunkTransferRejected("signed package identity field invalid")
    if not index.matches(index.catalog):
        raise ChunkTransferRejected("verified catalog mutated during selection")
    return SelectedSignedLibraryTransfer(
        index=index, transfer=transfer, artifact_id=expected_artifact_id,
        version=row["version"], signer_key_id=row["signer_key_id"],
        signature_receipt_ref=row["signature_receipt_ref"],
    )
