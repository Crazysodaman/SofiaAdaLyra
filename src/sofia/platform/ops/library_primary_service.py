"""Service-owned, Core-free Library primary and private Hub adapter.

This composes the existing independently verified B1 CAS, signed owner catalog
publisher, guarded mTLS Hub, current SAFE/STOP Hub/peer gates and the one
governed retention owner. It does not create a Core, a second identity store,
owner approval, publisher key, signer, public listener or cache mutation.

The canonical installed Platform service supplies its own current RUN status
callback plus its real Platform-local SQLite, PermissionStore and
OperatorStopStore. A caller-supplied ``status`` mapping is only an observation
of that service; it is never an owner grant. Importing this module starts no
listener and grants nothing.

One logical Library has at most one writable primary epoch. ``claim_primary``
reuses :class:`LibraryPrimaryLeaseStore`; a fenced, expired, read-only replica
or second-host claim is refused. Hub serving and catalog publication require a
current writer lease on every action, not merely at construction.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import ssl

from sofia.platform.ops.library_cached_source import VerifiedLibraryCacheSource
from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_owner_catalog_publish import (
    OwnerPublishedAsset, publish_signed_owner_catalog,
)
from sofia.platform.ops.library_primary_lease import (
    LibraryPrimaryDenied, LibraryPrimaryLeaseStore, LibraryPrimaryRole,
    PrimaryFenceReceipt,
)
from sofia.platform.ops.library_retention_gc import (
    GovernedLibraryRetention, LibraryRetentionDenied,
)
from sofia.platform.ops.library_signed_index import (
    SignedLibraryIndexRejected,
)
from sofia.platform.ops.library_signed_selection import (
    SelectedSignedLibraryTransfer, verify_renewed_recipient_offer,
    verify_selected_signed_transfer,
)
from sofia.platform.ops.library_tls_hub import ApprovedLibraryHub
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact
from sofia.platform.run.library_source_gate import (
    CurrentLibraryHubAuthority, CurrentLibrarySourcePeerAuthorizer,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.local_store import PlatformLocalStore

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX = 2**53 - 1
_TRANSFER_KINDS = frozenset({
    "platform_release", "sdk", "core_runtime", "core_definition",
    "module", "model", "asset", "rollback",
})


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ChunkTransferRejected(f"aware {label} required")
    return value.astimezone(timezone.utc)


class LibraryPrimaryService:
    """One Core-free owner-approved primary whose Hub serves verified CAS bytes.

    The constructor performs no network bind and no lease claim. A caller must
    explicitly ``claim_primary`` and then ``open_hub``. ``publish_catalog`` and
    ``fence_primary`` are the only catalog-role mutations exposed here.
    """

    def __init__(
        self, *,
        storage: PlatformLocalStore,
        logical_library_id: str,
        host_identity: str,
        platform_id: str,
        status: Callable[[], Mapping[str, object]],
        permissions: PermissionStore,
        stop: OperatorStopStore,
        trusted_publisher_public_key: bytes,
        expected_publisher_key_sha256: str,
        publisher_key_current: Callable[[str], bool],
        expected_catalog_generation: int,
        cache: OfflineArtifactCache,
        artifact: PlatformArtifact,
        package_signer_current: Callable[[str], bool],
        verify_independent_package: Callable[
            [PinnedChunkTransfer, Path], PlatformArtifact
        ],
        retention: GovernedLibraryRetention | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(storage, PlatformLocalStore):
            raise ChunkTransferRejected("existing Platform-local SQLite state required")
        if not isinstance(permissions, PermissionStore) or not isinstance(
            stop, OperatorStopStore
        ):
            raise ChunkTransferRejected("canonical SAFE and STOP stores required")
        if not callable(status):
            raise ChunkTransferRejected("service-owned current status callback required")
        for callback in (
            publisher_key_current, package_signer_current,
            verify_independent_package,
        ):
            if not callable(callback):
                raise ChunkTransferRejected(
                    "independent publisher and package checks required"
                )
        if (type(trusted_publisher_public_key) is not bytes
                or len(trusted_publisher_public_key) != 32):
            raise ChunkTransferRejected("independent 32-byte Ed25519 publisher key required")
        if (type(expected_publisher_key_sha256) is not str
                or _SHA.fullmatch(expected_publisher_key_sha256) is None
                or sha256(trusted_publisher_public_key).hexdigest()
                != expected_publisher_key_sha256):
            raise ChunkTransferRejected("independent trusted publisher root differs")
        if (type(expected_catalog_generation) is not int
                or not 1 <= expected_catalog_generation <= _MAX):
            raise ChunkTransferRejected("current bounded catalog generation required")
        if not isinstance(cache, OfflineArtifactCache):
            raise ChunkTransferRejected("single canonical B1 CAS required")
        if (not isinstance(artifact, PlatformArtifact)
                or artifact.signature_verified is not True):
            raise ChunkTransferRejected("independently verified B1 artifact required")
        if retention is not None and not isinstance(
            retention, GovernedLibraryRetention
        ):
            raise ChunkTransferRejected("canonical governed retention owner required")
        if clock is not None and not callable(clock):
            raise ChunkTransferRejected("trusted primary service clock required")

        self.storage = storage
        self.logical_library_id = logical_library_id
        self.host_identity = host_identity
        self.platform_id = platform_id
        self._status = status
        self.permissions = permissions
        self.stop = stop
        self.cache = cache
        self.artifact = artifact
        self.retention = retention
        self._trusted_public_key = trusted_publisher_public_key
        self._key_sha256 = expected_publisher_key_sha256
        self._publisher_current = publisher_key_current
        self._package_signer_current = package_signer_current
        self._verify_package = verify_independent_package
        self._catalog_generation = expected_catalog_generation
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lease = LibraryPrimaryLeaseStore(
            storage, logical_library_id=logical_library_id,
        )

        self._record: LibraryPrimaryRole | None = None
        self._token: str | None = None
        self._hub: ApprovedLibraryHub | None = None
        self._hub_grant: CurrentLibraryHubAuthority | None = None
        self._peer: CurrentLibrarySourcePeerAuthorizer | None = None
        self._verified_cache: VerifiedLibraryCacheSource | None = None
        self.transfer: PinnedChunkTransfer | None = None
        self._offer: SelectedSignedLibraryTransfer | None = None
        self._latest_offer: SelectedSignedLibraryTransfer | None = None
        self._read_index: Callable[[], bytes] | None = None
        self.endpoint: tuple[str, int] | None = None
        self._closed = False
        self._served_chunks = 0
        self._served_bytes = 0

    # -- service and role state ------------------------------------------------

    def _now(self, now: datetime | None = None) -> datetime:
        return _aware(self._clock() if now is None else now, "primary service clock")

    def _current_status(self) -> Mapping[str, object]:
        state = self._status()
        if (not isinstance(state, Mapping)
                or state.get("platform_id") != self.platform_id
                or type(state.get("generation")) is not int
                or not 1 <= state["generation"] <= _MAX
                or state.get("operator_stop") is not False
                or self.stop.current().active):
            raise ChunkTransferRejected(
                "current STOP-free primary Platform service status required"
            )
        return state

    def _require_writer(self, now: datetime | None = None) -> datetime:
        if self._record is None or self._token is None:
            raise LibraryPrimaryDenied("primary writer has not been claimed")
        moment = self._now(now)
        record = self._lease.require_writer(
            host_identity=self.host_identity,
            platform_id=self.platform_id,
            epoch=self._record.primary_epoch,
            writer_token=self._token,
            now=moment,
        )
        if record.primary_epoch != self._record.primary_epoch:
            raise LibraryPrimaryDenied(
                "primary epoch changed while writer token is held; re-claim required"
            )
        self._record = record
        return moment

    def _hub_current(self) -> bool:
        """Current writer + service RUN + independent publisher/package trust."""
        try:
            self._require_writer()
            self._current_status()
            if self._publisher_current(self._key_sha256) is not True:
                return False
            if self._package_signer_current(self.artifact.signer_key_id) is not True:
                return False
            return True
        except (
            LibraryPrimaryDenied, ChunkTransferRejected, PermissionError,
            RuntimeError, ValueError, OSError, TypeError,
        ):
            return False

    def claim_primary(
        self, *, lease_seconds: int = 60, writer_token: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Claim or renew the one writable epoch; never auto-promote a peer."""
        moment = self._now(now)
        self._current_status()
        record, token = self._lease.claim_primary(
            host_identity=self.host_identity,
            platform_id=self.platform_id,
            now=moment,
            lease_seconds=lease_seconds,
            writer_token=writer_token,
        )
        if record.read_only_replica or record.role != "PRIMARY":
            raise LibraryPrimaryDenied("claimed role is not writable primary")
        self._record = record
        self._token = token
        return self.status(now=moment)

    def fence_primary(
        self, *, reason: str = "OWNER_VERIFIED_OLD_PRIMARY_FENCED",
        now: datetime | None = None,
    ) -> PrimaryFenceReceipt:
        """Fence this exact writer epoch and return durable owner evidence."""
        moment = self._require_writer(now)
        if self._record is None or self._token is None:
            raise LibraryPrimaryDenied("primary writer has not been claimed")
        receipt = self._lease.fence_primary(
            host_identity=self.host_identity,
            platform_id=self.platform_id,
            epoch=self._record.primary_epoch,
            writer_token=self._token,
            now=moment,
            reason=reason,
        )
        self._record = None
        self._token = None
        self.close()
        return receipt

    # -- signed catalog --------------------------------------------------------

    def publish_catalog(
        self, *, transfer: PinnedChunkTransfer,
        selected_assets: tuple[OwnerPublishedAsset, ...] | list[OwnerPublishedAsset],
        expected_artifact_id: str, sign_external: Callable[[bytes], bytes],
        lifetime_seconds: int = 120, now: datetime | None = None,
    ) -> bytes:
        """Sign and self-verify only the exact selected public licensed asset."""
        moment = self._require_writer(now)
        self._current_status()
        if not isinstance(transfer, PinnedChunkTransfer):
            raise ChunkTransferRejected("typed signed transfer required")
        if transfer.artifact_kind not in _TRANSFER_KINDS:
            raise ChunkTransferRejected("reviewed artifact class required")
        if transfer.source_platform_id != self.platform_id:
            raise ChunkTransferRejected("transfer source is not this primary")
        if transfer.target_platform_id == self.platform_id:
            raise ChunkTransferRejected("primary cannot publish to itself")
        if (type(expected_artifact_id) is not str
                or not 1 <= len(expected_artifact_id) <= 160):
            raise ChunkTransferRejected("explicit selected artifact ID required")
        if (type(selected_assets) not in (tuple, list)
                or not 1 <= len(selected_assets) <= 32
                or any(
                    not isinstance(asset, OwnerPublishedAsset)
                    for asset in selected_assets
                )):
            raise ChunkTransferRejected("bounded independently verified assets required")
        matches = [
            asset for asset in selected_assets
            if asset.artifact_id == expected_artifact_id
        ]
        if len(matches) != 1:
            raise ChunkTransferRejected("selected asset missing or ambiguous")
        selected = matches[0]
        if (selected.content_digest != transfer.content_sha256
                or selected.manifest_digest != transfer.manifest_sha256
                or selected.size_bytes != transfer.size_bytes
                or selected.revision > transfer.catalog_revision
                or selected.kind != transfer.artifact_kind
                or selected.license_distribution != transfer.license_distribution
                or selected.data_class != transfer.data_class
                or selected.distribution_allowed is not True):
            raise ChunkTransferRejected(
                "selected signed asset differs from pinned transfer"
            )
        if not callable(sign_external):
            raise ChunkTransferRejected("approved external Ed25519 signer required")

        published = publish_signed_owner_catalog(
            source_platform_id=self.platform_id,
            target_platform_id=transfer.target_platform_id,
            trusted_publisher_public_key=self._trusted_public_key,
            catalog_generation=self._catalog_generation,
            catalog_revision=transfer.catalog_revision,
            selected_assets=tuple(selected_assets),
            sign_external=sign_external,
            owner_hub_current=self._hub_current,
            publisher_current=self._publisher_current,
            time_now=self._clock,
            lifetime_seconds=lifetime_seconds,
        )
        offer = verify_selected_signed_transfer(
            raw_signed_index=published,
            transfer=transfer,
            expected_artifact_id=expected_artifact_id,
            trusted_publisher_public_key=self._trusted_public_key,
            expected_publisher_key_sha256=self._key_sha256,
            expected_catalog_generation=self._catalog_generation,
            now=moment,
            publisher_key_current=self._publisher_current,
        )
        self._offer = offer
        self._latest_offer = offer
        return published

    # -- private Hub -----------------------------------------------------------

    def open_hub(
        self, *, bind_host: str, port: int, tls_context: ssl.SSLContext,
        transfer: PinnedChunkTransfer, raw_signed_index: bytes,
        expected_artifact_id: str,
        expected_recipient_certificate_sha256: str,
        read_current_signed_index: Callable[[], bytes] | None = None,
        timeout_seconds: int = 10, now: datetime | None = None,
    ) -> "LibraryPrimaryService":
        """Open one explicitly owner-approved private LAN Hub listener."""
        if self._hub is not None:
            raise ChunkTransferRejected("one private Hub is already open")
        moment = self._require_writer(now)
        state = self._current_status()
        if not isinstance(transfer, PinnedChunkTransfer):
            raise ChunkTransferRejected("typed signed transfer required")
        if transfer.source_platform_id != self.platform_id:
            raise ChunkTransferRejected("Hub is not the transfer's signed source")
        if transfer.target_platform_id == self.platform_id:
            raise ChunkTransferRejected("Hub requires a distinct enrolled recipient")
        if (state.get("generation") is None
                or type(state["generation"]) is not int):
            raise ChunkTransferRejected("current Hub RUN generation required")
        if read_current_signed_index is not None and not callable(
            read_current_signed_index
        ):
            raise ChunkTransferRejected("installed catalog renewal supplier required")
        if (self._publisher_current(self._key_sha256) is not True
                or self._package_signer_current(self.artifact.signer_key_id) is not True):
            raise ChunkTransferRejected("publisher or package signer revoked")

        offer = verify_selected_signed_transfer(
            raw_signed_index=raw_signed_index,
            transfer=transfer,
            expected_artifact_id=expected_artifact_id,
            trusted_publisher_public_key=self._trusted_public_key,
            expected_publisher_key_sha256=self._key_sha256,
            expected_catalog_generation=self._catalog_generation,
            now=moment,
            publisher_key_current=self._publisher_current,
        )
        if offer.index.catalog["source"]["kind"] != "OWNER_SELECTED_HUB":
            raise ChunkTransferRejected(
                "only an owner-selected Hub catalog can authorize Hub serving"
            )
        if (self.artifact.artifact_id != offer.artifact_id
                or self.artifact.version != offer.version
                or self.artifact.signer_key_id != offer.signer_key_id
                or self.artifact.sha256 != transfer.content_sha256):
            raise ChunkTransferRejected(
                "B1 signed package identity differs from publisher catalog"
            )

        path = self.cache.resolve(self.artifact)
        proven = self._verify_package(transfer, path)
        if (not isinstance(proven, PlatformArtifact) or proven != self.artifact
                or self._package_signer_current(self.artifact.signer_key_id) is not True):
            raise ChunkTransferRejected(
                "current independently trusted B1 package verification unavailable"
            )
        verified_cache = VerifiedLibraryCacheSource(
            cache=self.cache, artifact=self.artifact,
        )
        verified_cache.current_path(transfer)

        grant = CurrentLibraryHubAuthority(
            permissions=self.permissions, stop=self.stop,
            current_status=self._status,
            source_platform_id=self.platform_id,
            source_generation=state["generation"],
            bind_host=bind_host, bind_port=port, clock=self._clock,
        )

        def current_publisher(candidate: PinnedChunkTransfer) -> bool:
            try:
                self._require_writer()
                self._current_status()
                if (candidate != self.transfer
                        or self._publisher_current(self._key_sha256) is not True
                        or self._package_signer_current(self.artifact.signer_key_id)
                        is not True
                        or grant() is not True
                        or not offer.still_matches()):
                    return False
                selected = self._latest_offer or offer
                if self._read_index is not None:
                    current_bytes = self._read_index()
                    if type(current_bytes) is not bytes:
                        return False
                    if sha256(current_bytes).hexdigest() != (
                        selected.index.signed_index_sha256
                    ):
                        selected = verify_renewed_recipient_offer(
                            original=selected,
                            renewed_signed_index=current_bytes,
                            trusted_publisher_public_key=self._trusted_public_key,
                            expected_publisher_key_sha256=self._key_sha256,
                            expected_catalog_generation=self._catalog_generation,
                            now=self._now(),
                            publisher_key_current=self._publisher_current,
                        )
                        self._latest_offer = selected
                index = selected.index
                fresh_until = datetime.fromisoformat(
                    index.catalog["catalog_fresh_until"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                instant = self._now()
                return (
                    selected.artifact_id == offer.artifact_id
                    and selected.signer_key_id == offer.signer_key_id
                    and selected.signature_receipt_ref == offer.signature_receipt_ref
                    and selected.version == offer.version
                    and index.catalog["source"]["kind"] == "OWNER_SELECTED_HUB"
                    and index.source_platform_id == transfer.source_platform_id
                    and index.target_platform_id == transfer.target_platform_id
                    and index.catalog_revision == transfer.catalog_revision
                    and instant < index.expires_at
                    and instant < fresh_until
                    and selected.still_matches()
                )
            except (
                LibraryPrimaryDenied, ChunkTransferRejected, PermissionError,
                RuntimeError, ValueError, TypeError, OSError,
                SignedLibraryIndexRejected,
            ):
                return False

        peer = CurrentLibrarySourcePeerAuthorizer(
            permissions=self.permissions, hub_enabled=grant,
            signed_transfer=transfer,
            expected_recipient_certificate_sha256=(
                expected_recipient_certificate_sha256
            ),
            publisher_current=current_publisher, clock=self._clock,
        )
        hub = ApprovedLibraryHub(
            bind_host=bind_host, port=port, tls_context=tls_context,
            owner_enabled=grant,
            lookup_transfer=lambda digest: (
                transfer if digest == transfer.content_sha256
                and current_publisher(transfer) else None
            ),
            authorize_peer=peer,
            publisher_current=current_publisher,
            resolve_verified_cache=lambda t: (
                verified_cache.current_path(t)
                if t == transfer and current_publisher(t) else
                (_ for _ in ()).throw(
                    ChunkTransferRejected(
                        "Hub asset or publisher no longer current"
                    )
                )
            ),
            timeout_seconds=timeout_seconds,
        )

        self.transfer = transfer
        self._offer = offer
        self._latest_offer = offer
        self._read_index = read_current_signed_index
        self._verified_cache = verified_cache
        self._hub_grant = grant
        self._peer = peer
        self._hub = hub
        try:
            self.endpoint = hub.open()
        except BaseException:
            self.transfer = None
            self._offer = None
            self._latest_offer = None
            self._read_index = None
            self._verified_cache = None
            self._hub_grant = None
            self._peer = None
            self._hub = None
            self.endpoint = None
            raise
        self._closed = False
        return self

    def serve_once(self, *, now: datetime | None = None) -> int:
        """Serve one bounded mTLS chunk after rechecking the primary writer."""
        if self._hub is None or self._hub_grant is None or self.transfer is None:
            raise ChunkTransferRejected("private Hub was not explicitly opened")
        if self._closed:
            raise ChunkTransferRejected("private Hub session closed")
        self._require_writer(now)
        if self._hub_grant() is not True:
            self.close()
            raise ChunkTransferRejected(
                "owner Hub role revoked or STOP before serving"
            )
        try:
            size = self._hub.serve_once()
        except Exception:
            if self._hub_grant() is not True:
                self.close()
            raise
        self._served_chunks += 1
        self._served_bytes += size
        return size

    def serve_bounded(
        self, *, max_connections: int, now: datetime | None = None,
    ) -> int:
        """Serve an explicit bounded number of separately authorized chunks."""
        if type(max_connections) is not int or not 1 <= max_connections <= 10000:
            raise ChunkTransferRejected("bounded Hub connection budget required")
        total = 0
        for _ in range(max_connections):
            if self._closed:
                break
            total += self.serve_once(now=now)
        return total

    def serving_status(self) -> dict[str, object]:
        """Truthful local worker observation; never an owner grant."""
        if self._hub is None:
            state = "CLOSED"
        elif self._closed:
            state = "CLOSED"
        else:
            state = "OPEN_IDLE"
        return {
            "schema": "aegis.library.primary-hub.v1",
            "state": state,
            "served_chunks": self._served_chunks,
            "served_bytes": self._served_bytes,
            "installed": None,
            "core_started": None,
            "owner_approved": None,
        }

    def close(self) -> None:
        hub = self._hub
        self._hub = None
        self._hub_grant = None
        self._peer = None
        self.transfer = None
        self._verified_cache = None
        self.endpoint = None
        self._closed = True
        if hub is not None:
            hub.close()

    # -- governed retention ----------------------------------------------------

    def retention_preview(self, *, content_sha256: str) -> dict[str, object]:
        """Read-only GC preview through the canonical governed retention owner."""
        if self.retention is None:
            raise LibraryRetentionDenied("no governed retention owner composed")
        self._require_writer()
        return self.retention.preview(content_sha256=content_sha256)

    def retention_delete_one(
        self, *, content_sha256: str, expected_pin_graph_sha256: str,
        approval_id: str, now: datetime | None = None,
    ) -> dict[str, object]:
        """Delete one unpinned CAS blob only while this primary is current."""
        if self.retention is None:
            raise LibraryRetentionDenied("no governed retention owner composed")
        moment = self._require_writer(now)
        result = self.retention.delete_one(
            content_sha256=content_sha256,
            expected_pin_graph_sha256=expected_pin_graph_sha256,
            approval_id=approval_id, now=moment,
        )
        self._require_writer()
        return result

    # -- strict status ---------------------------------------------------------

    def status(self, *, now: datetime | None = None) -> dict[str, object]:
        """Redacted strict JSON; no writer token, private path or certificate."""
        moment = self._now(now)
        primary = self._lease.status(now=moment)
        worker = self.serving_status()
        return {
            "schema": "aegis.library.primary-service-status.v1",
            "logical_library_id": self.logical_library_id,
            "platform_id": self.platform_id,
            "host_identity": self.host_identity,
            "owner_mode": "SINGLE_OWNER_PRIVATE",
            "role": primary["role"],
            "state": primary["state"],
            "primary_epoch": primary["primary_epoch"],
            "catalog_revision": primary["catalog_revision"],
            "read_only": primary["read_only"],
            "writer_claimed": self._record is not None and self._token is not None,
            "hub_state": worker["state"],
            "served_chunks": worker["served_chunks"],
            "served_bytes": worker["served_bytes"],
            "retention_composed": self.retention is not None,
            "install_executed": False,
            "core_activated": False,
        }


__all__ = ["LibraryPrimaryService"]
