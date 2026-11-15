"""Service-owned recipient / read-only replica Library adapter.

This composes the existing authenticated TLS chunk/resumable fetch, publisher
signature/license verification, quarantine admission, one
:class:`LibraryPrimaryLeaseStore` role record and the durable
:class:`LibraryReplicaStateStore`. It opens no listener, mints no certificate,
signs no catalog and installs nothing.

A Platform recorded as ``READ_REPLICA`` can never claim primary write
authority, advance the catalog revision or accept a write through this adapter.
Owner-approved manual promotion is delegated to the existing lease store and
still requires exact durable old-primary fence evidence plus a current owner
SAFE callback.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_primary_lease import (
    LibraryPrimaryLeaseStore, LibraryPrimaryRole, PrimaryFenceReceipt,
)
from sofia.platform.ops.library_replica import (
    LibraryReplica, LibraryReplicaDenied, LibraryReplicaStateStore,
)
from sofia.platform.run.library_peer_gate import CurrentRecipientPeerAuthorizer
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.local_store import PlatformLocalStore

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX = 2**53 - 1


class LibraryRecipientService:
    """Read-only recipient composition with explicit local Library role.

    The constructor records nothing and transfers nothing. Call
    ``mark_read_only`` for a replica host, then ``sync_index``/``sync_object``.
    A writable primary host normally uses :class:`LibraryPrimaryService`; this
    adapter intentionally has no catalog-write or primary-claim method.
    """

    def __init__(
        self, *,
        storage: PlatformLocalStore,
        logical_library_id: str,
        host_identity: str,
        replica_platform_id: str,
        primary_platform_id: str,
        receiver: ChunkedArtifactReceiver,
        trusted_publisher_public_key: bytes,
        expected_publisher_key_sha256: str,
        expected_catalog_generation: int,
        minimum_catalog_revision: int,
        authenticate_primary: Callable[[str], bool],
        publisher_key_current: Callable[[str], bool],
        source_allowed: Callable[[PinnedChunkTransfer], bool],
        permissions: PermissionStore,
        stop: OperatorStopStore,
        status: Callable[[], Mapping[str, object]],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(storage, PlatformLocalStore):
            raise LibraryReplicaDenied("existing Platform-local SQLite state required")
        if not isinstance(receiver, ChunkedArtifactReceiver):
            raise LibraryReplicaDenied("canonical quarantine receiver required")
        if not isinstance(permissions, PermissionStore) or not isinstance(
            stop, OperatorStopStore
        ):
            raise LibraryReplicaDenied("canonical SAFE and STOP stores required")
        if not callable(status):
            raise LibraryReplicaDenied("service-owned current status callback required")
        if (type(trusted_publisher_public_key) is not bytes
                or len(trusted_publisher_public_key) != 32):
            raise LibraryReplicaDenied(
                "independent 32-byte Ed25519 publisher key required"
            )
        if (type(expected_publisher_key_sha256) is not str
                or _SHA.fullmatch(expected_publisher_key_sha256) is None
                or sha256(trusted_publisher_public_key).hexdigest()
                != expected_publisher_key_sha256):
            raise LibraryReplicaDenied("independent trusted publisher root differs")
        for value, label in (
            (expected_catalog_generation, "catalog generation"),
            (minimum_catalog_revision, "minimum catalog revision"),
        ):
            if type(value) is not int or not 1 <= value <= _MAX:
                raise LibraryReplicaDenied(f"current bounded {label} required")
        for callback in (authenticate_primary, publisher_key_current, source_allowed):
            if not callable(callback):
                raise LibraryReplicaDenied("canonical replica authority callbacks required")
        if clock is not None and not callable(clock):
            raise LibraryReplicaDenied("trusted replica service clock required")

        self.storage = storage
        self.logical_library_id = logical_library_id
        self.host_identity = host_identity
        self.replica_platform_id = replica_platform_id
        self.primary_platform_id = primary_platform_id
        self.permissions = permissions
        self.stop = stop
        self.receiver = receiver
        self._status = status
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lease = LibraryPrimaryLeaseStore(
            storage, logical_library_id=logical_library_id,
        )
        self.replica_state = LibraryReplicaStateStore(
            storage, logical_library_id=logical_library_id,
            replica_platform_id=replica_platform_id,
            primary_platform_id=primary_platform_id,
        )

        def stop_active() -> bool:
            try:
                state = self._status()
                return (
                    not isinstance(state, Mapping)
                    or state.get("operator_stop") is not False
                    or self.stop.current().active
                )
            except (OSError, RuntimeError, ValueError, PermissionError, TypeError):
                return True

        self.replica = LibraryReplica(
            state_store=self.replica_state, receiver=receiver,
            logical_library_id=logical_library_id,
            replica_platform_id=replica_platform_id,
            primary_platform_id=primary_platform_id,
            trusted_publisher_public_key=trusted_publisher_public_key,
            expected_publisher_key_sha256=expected_publisher_key_sha256,
            expected_catalog_generation=expected_catalog_generation,
            minimum_catalog_revision=minimum_catalog_revision,
            authenticate_primary=authenticate_primary,
            publisher_key_current=publisher_key_current,
            stop_active=stop_active,
            source_allowed=source_allowed,
            clock=self._clock,
        )

    # -- service and role state ------------------------------------------------

    def _now(self, now: datetime | None = None) -> datetime:
        moment = self._clock() if now is None else now
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise LibraryReplicaDenied("aware replica service clock required")
        return moment.astimezone(timezone.utc)

    def _current_status(self) -> Mapping[str, object]:
        state = self._status()
        if (not isinstance(state, Mapping)
                or state.get("platform_id") != self.replica_platform_id
                or type(state.get("generation")) is not int
                or not 1 <= state["generation"] <= _MAX
                or state.get("operator_stop") is not False
                or self.stop.current().active):
            raise LibraryReplicaDenied(
                "current STOP-free replica Platform service status required"
            )
        return state

    def _role_record(self) -> LibraryPrimaryRole | None:
        return self._lease.current()

    def _require_not_fenced(self) -> LibraryPrimaryRole | None:
        record = self._role_record()
        if record is not None and (record.is_fenced or record.role == "FENCED"):
            raise LibraryReplicaDenied(
                "stale or fenced primary epoch cannot be used by this replica"
            )
        return record

    def mark_read_only(
        self, *, primary_epoch: int, catalog_revision: int,
        lease_seconds: int = 60, now: datetime | None = None,
    ) -> dict[str, object]:
        """Record this installed Platform as a read-only replica of one primary."""
        moment = self._now(now)
        self._current_status()
        current = self._role_record()
        if current is not None and (
            current.role == "PRIMARY" or current.is_primary
        ):
            raise LibraryReplicaDenied(
                "a current writable primary cannot be reclassified as replica"
            )
        if current is not None and (current.is_fenced or current.role == "FENCED"):
            raise LibraryReplicaDenied(
                "fenced primary evidence cannot be replaced by a replica record"
            )
        record = self._lease.mark_read_only_replica(
            host_identity=self.host_identity,
            platform_id=self.replica_platform_id,
            primary_platform_id=self.primary_platform_id,
            primary_epoch=primary_epoch,
            catalog_revision=catalog_revision,
            now=moment, lease_seconds=lease_seconds,
        )
        if not record.read_only_replica:
            raise LibraryReplicaDenied("read-only replica role was not committed")
        if self.replica_state.current() is None:
            self.replica_state.record_state(state="UNKNOWN", now=moment)
        return self.status(now=moment)

    # -- authenticated read-only synchronization -------------------------------

    def sync_index(
        self, raw_signed_index: bytes, *, now: datetime | None = None,
        primary_epoch: int | None = None,
    ) -> Any:
        """Verify and persist one signed index without any catalog write."""
        moment = self._now(now)
        self._current_status()
        record = self._require_not_fenced()
        if record is not None and record.read_only_replica:
            if primary_epoch is None:
                primary_epoch = record.primary_epoch
            elif primary_epoch < record.primary_epoch:
                raise LibraryReplicaDenied("stale primary epoch refused")
        return self.replica.sync_index(
            raw_signed_index, now=moment, primary_epoch=primary_epoch,
        )

    def sync_object(
        self, transfer: PinnedChunkTransfer, *, now: datetime | None = None,
        read_chunk: Callable[[int, int], bytes] | None = None,
        open_enrolled_tls: Callable[[], object] | None = None,
        expected_peer_certificate_sha256: str | None = None,
        authorize_peer: Callable | None = None,
        chunk_bytes: int = 1024 * 1024, max_chunks: int = 128,
    ) -> Any:
        """Fetch exact signed bytes read-only; never mutate the catalog/CAS role."""
        moment = self._now(now)
        self._current_status()
        self._require_not_fenced()
        if not isinstance(transfer, PinnedChunkTransfer):
            raise LibraryReplicaDenied("typed pinned replica transfer required")
        if transfer.source_platform_id != self.primary_platform_id:
            raise LibraryReplicaDenied("transfer source differs from configured primary")
        if transfer.target_platform_id != self.replica_platform_id:
            raise LibraryReplicaDenied("transfer target differs from this replica")
        if open_enrolled_tls is not None and authorize_peer is None:
            authorize_peer = CurrentRecipientPeerAuthorizer(
                permissions=self.permissions, stop=self.stop,
                current_status=self._status, signed_transfer=transfer,
            )
        try:
            return self.replica.sync_object(
                transfer, now=moment, read_chunk=read_chunk,
                open_enrolled_tls=open_enrolled_tls,
                expected_peer_certificate_sha256=expected_peer_certificate_sha256,
                authorize_peer=authorize_peer,
                chunk_bytes=chunk_bytes, max_chunks=max_chunks,
            )
        except (LibraryReplicaDenied, ChunkTransferRejected):
            # STOP, revocation, quota or integrity cancellation is not a
            # completed sync. Record a truthful durable state without
            # pretending the bytes were installed or the catalog changed.
            try:
                self.replica_state.record_state(
                    state="STALE", now=moment,
                    error_code="TRANSFER_CANCELLED_OR_DENIED",
                )
            except Exception:
                pass
            raise

    # -- explicit owner-approved promotion -------------------------------------

    def promote_to_primary(
        self, *, new_primary_host_id: str, new_primary_platform_id: str,
        expected_old_epoch: int, old_primary_fence_receipt: PrimaryFenceReceipt,
        safe_authorization: Callable[[], bool], now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> dict[str, object]:
        """Manual promotion only after exact old-primary fence evidence.

        The existing lease store requires a durable local FENCED record. A
        read-only replica record alone is not fence evidence and is refused;
        cross-host fence-receipt adoption is intentionally not invented here.
        """
        moment = self._now(now)
        self._current_status()
        if (new_primary_host_id != self.host_identity
                or new_primary_platform_id != self.replica_platform_id):
            raise LibraryReplicaDenied(
                "promotion must target this installed replica Platform"
            )
        if not callable(safe_authorization):
            raise LibraryReplicaDenied(
                "current authenticated owner SAFE callback required for promotion"
            )
        current = self._role_record()
        if current is not None and (
            current.role == "PRIMARY" or current.is_primary
        ):
            raise LibraryReplicaDenied("local Platform is already writable primary")
        record, _token = self._lease.promote_read_only_replica(
            new_primary_host_id=new_primary_host_id,
            new_primary_platform_id=new_primary_platform_id,
            expected_old_epoch=expected_old_epoch,
            old_primary_fence_receipt=old_primary_fence_receipt,
            safe_authorization=safe_authorization,
            now=moment, lease_seconds=lease_seconds,
        )
        if record.role != "PRIMARY" or record.read_only_replica:
            raise LibraryReplicaDenied("promotion did not produce a writable primary")
        return self.status(now=moment)

    def mark_disconnected(
        self, *, state: str = "OFFLINE", now: datetime | None = None,
        error_code: str = "PRIMARY_DISCONNECTED",
    ) -> dict[str, object]:
        return self.replica.mark_disconnected(
            state=state, now=self._now(now), error_code=error_code,
        )

    # -- strict status ---------------------------------------------------------

    def status(self, *, now: datetime | None = None) -> dict[str, object]:
        """Redacted strict JSON; no writer token, private path or certificate."""
        moment = self._now(now)
        primary = self._lease.status(now=moment)
        replica = self.replica_state.status(now=moment)
        role = primary["role"]
        last_revision = replica["last_catalog_revision"]
        last_epoch = replica["last_primary_epoch"]
        is_replica = role == "READ_REPLICA"
        return {
            "schema": "aegis.library.recipient-service-status.v1",
            "logical_library_id": self.logical_library_id,
            "primary_platform_id": self.primary_platform_id,
            "replica_platform_id": self.replica_platform_id,
            "host_identity": self.host_identity,
            "owner_mode": "SINGLE_OWNER_PRIVATE",
            "role": role if role is not None else "UNKNOWN",
            "read_only": (
                True if role is None
                else primary["read_only"]
            ),
            "catalog_writable": False,
            "zero_replicas_supported": True,
            "primary_state": primary["state"],
            "primary_epoch": (
                last_epoch if is_replica and last_epoch is not None
                else primary["primary_epoch"]
            ),
            "catalog_revision": (
                last_revision if is_replica and last_revision is not None
                else primary["catalog_revision"]
            ),
            "replica_state": replica["state"],
            "last_primary_epoch": replica["last_primary_epoch"],
            "last_catalog_revision": replica["last_catalog_revision"],
            "last_synced_at": replica["last_synced_at"],
            "last_error_code": replica["last_error_code"],
            "install_executed": False,
            "core_activated": False,
        }


__all__ = ["LibraryRecipientService"]
