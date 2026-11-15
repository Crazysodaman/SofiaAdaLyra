"""D028 read-only replica sync, bounded CAS admission and truthful status."""
from __future__ import annotations

from base64 import b64encode
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_replica import (
    LibraryReplica, LibraryReplicaDenied, LibraryReplicaStateStore,
)
from sofia.platform.ops.library_signed_index import SCHEMA, _DOMAIN
from sofia.platform.state.local_store import PlatformLocalStore

PRIMARY = "primary-library-host"
REPLICA = "read-only-replica-host"
LIBRARY = "private-library-1"
NOW = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)


def _local_state(tmp_path, host: str = REPLICA) -> PlatformLocalStore:
    return PlatformLocalStore(
        tmp_path / "platform.db",
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=host,
    )


def _index_fixture(
    data: bytes, *, now: datetime = NOW, revision: int = 7,
    generation: int = 3, license_distribution: str = "permitted",
    data_class: str = "public", source_status: str = "CURRENT",
):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest = "a" * 64
    transfer = PinnedChunkTransfer(
        source_platform_id=PRIMARY, target_platform_id=REPLICA,
        content_sha256=sha256(data).hexdigest(), size_bytes=len(data),
        generation=8, manifest_sha256=manifest, catalog_revision=revision,
        artifact_kind="sdk", license_distribution="permitted",
        data_class="public",
    )
    item = {
        "artifact_id": "sdk.release.1", "kind": "sdk", "version": "1.0",
        "revision": revision, "manifest_digest": manifest,
        "content_digest": transfer.content_sha256,
        "size_bytes": transfer.size_bytes,
        "publisher": "owner-approved-publisher",
        "signer_key_id": "independent-release-key",
        "signature_scheme": "ed25519",
        "signature_receipt_ref": "signed-receipt-1",
        "target_os_arch": "debian12-x86_64", "sdk_range": ">=1.0",
        "abi_range": ">=1.0",
        "license_distribution": license_distribution,
        "data_class": data_class, "distribution_allowed": True,
    }
    envelope = {
        "schema": SCHEMA,
        "publisher_key_sha256": sha256(public).hexdigest(),
        "source_platform_id": PRIMARY,
        "target_platform_id": REPLICA,
        "catalog_revision": revision,
        "catalog_generation": generation,
        "issued_at": (now - timedelta(seconds=2)).isoformat(),
        "expires_at": (now + timedelta(minutes=2)).isoformat(),
        "catalog": {
            "catalog_revision": revision,
            "catalog_generation": generation,
            "catalog_fresh_until": (now + timedelta(seconds=30)).isoformat(),
            "target_platform_id": REPLICA,
            "source": {
                "kind": "OWNER_SELECTED_HUB", "source_id": PRIMARY,
                "last_observed_at": now.isoformat(),
                "status": source_status,
            },
            "page": {"limit": 32, "next_cursor": None,
                     "cursor_state": "CURRENT"},
            "items": [item],
        },
    }

    def sign(body=None):
        payload = json.dumps(
            envelope if body is None else body,
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        signature = private.sign(_DOMAIN + payload)
        return json.dumps(
            {**(envelope if body is None else body),
             "signature_b64": b64encode(signature).decode("ascii")},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")

    return envelope, sign, transfer, public


def _replica(
    tmp_path, *, sign, public, now=NOW,
    publisher_current: Callable[[str], bool] | None = None,
    stop_active: Callable[[], bool] | None = None,
    source_allowed: Callable[[PinnedChunkTransfer], bool] | None = None,
) -> LibraryReplica:
    storage = _local_state(tmp_path)
    state_store = LibraryReplicaStateStore(
        storage, logical_library_id=LIBRARY,
        replica_platform_id=REPLICA, primary_platform_id=PRIMARY,
    )
    receiver = ChunkedArtifactReceiver(tmp_path / "replica-cas", max_bytes=64 * 1024)
    return LibraryReplica(
        state_store=state_store, receiver=receiver,
        logical_library_id=LIBRARY, replica_platform_id=REPLICA,
        primary_platform_id=PRIMARY,
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        expected_catalog_generation=3, minimum_catalog_revision=7,
        authenticate_primary=lambda identity: identity == PRIMARY,
        publisher_key_current=publisher_current or (lambda _: True),
        stop_active=stop_active or (lambda: False),
        source_allowed=source_allowed or (lambda _: True),
        clock=lambda: now,
    )


def _forced_transfer(data: bytes, **overrides) -> PinnedChunkTransfer:
    values = {
        "source_platform_id": PRIMARY, "target_platform_id": REPLICA,
        "content_sha256": sha256(data).hexdigest(), "size_bytes": len(data),
        "generation": 8, "manifest_sha256": "a" * 64,
        "catalog_revision": 7, "artifact_kind": "sdk",
        "license_distribution": "permitted", "data_class": "public",
    }
    values.update(overrides)
    transfer = object.__new__(PinnedChunkTransfer)
    for name, value in values.items():
        object.__setattr__(transfer, name, value)
    return transfer


def test_replica_syncs_exact_signed_index_and_cas_object(tmp_path):
    data = b"verified-replica-object" * 8
    envelope, sign, transfer, public = _index_fixture(data)
    replica = _replica(tmp_path, sign=sign, public=public)

    assert replica.status(now=NOW)["state"] == "UNKNOWN"
    verified = replica.sync_index(sign())
    assert verified.catalog_revision == 7
    assert verified.signed_index_sha256 == sha256(sign()).hexdigest()
    assert replica.status(now=NOW)["state"] == "SYNCED"

    result = replica.sync_object(
        transfer, read_chunk=lambda offset, length: data[offset:offset + length],
    )
    assert result.complete is True
    assert result.offset == len(data)
    assert result.path.read_bytes() == data
    assert sha256(result.path.read_bytes()).hexdigest() == transfer.content_sha256


def test_replica_refuses_tampered_index_and_untrusted_publisher(tmp_path):
    data = b"tamper-check"
    envelope, sign, transfer, public = _index_fixture(data)
    replica = _replica(tmp_path, sign=sign, public=public)
    tampered = sign().replace(b'"catalog_revision":7', b'"catalog_revision":8')
    with pytest.raises(PermissionError):
        replica.sync_index(tampered)

    untrusted = _replica(
        tmp_path / "untrusted", sign=sign, public=public,
        publisher_current=lambda _: False,
    )
    with pytest.raises(LibraryReplicaDenied):
        untrusted.sync_index(sign())


def test_replica_refuses_license_blocked_private_or_wrong_source(tmp_path):
    data = b"license-blocked"
    _, sign, _, public = _index_fixture(
        data, license_distribution="restricted", data_class="private",
    )
    replica = _replica(tmp_path / "license", sign=sign, public=public)
    with pytest.raises(LibraryReplicaDenied):
        replica.sync_index(sign())

    _, sign_private, _, public_private = _index_fixture(
        data, data_class="private",
    )
    private_replica = _replica(
        tmp_path / "private", sign=sign_private, public=public_private,
    )
    with pytest.raises(LibraryReplicaDenied):
        private_replica.sync_index(sign_private())

    _, stale_sign, _, stale_public = _index_fixture(
        data, source_status="STALE",
    )
    stale_replica = _replica(
        tmp_path / "stale-source", sign=stale_sign, public=stale_public,
    )
    with pytest.raises(LibraryReplicaDenied):
        stale_replica.sync_index(stale_sign())


def test_replica_enforces_stop_and_source_license_callbacks(tmp_path):
    data = b"callback-gates"
    _, sign, transfer, public = _index_fixture(data)
    stopped = _replica(
        tmp_path / "stopped", sign=sign, public=public,
        stop_active=lambda: True,
    )
    with pytest.raises(LibraryReplicaDenied):
        stopped.sync_index(sign())

    denied = _replica(
        tmp_path / "source-denied", sign=sign, public=public,
        source_allowed=lambda _: False,
    )
    denied.sync_index(sign())
    with pytest.raises(LibraryReplicaDenied):
        denied.sync_object(
            transfer, read_chunk=lambda offset, length: data[offset:offset + length],
        )


def test_replica_refuses_tampered_object_and_private_transfer(tmp_path):
    data = b"object-integrity" * 4
    _, sign, transfer, public = _index_fixture(data)
    replica = _replica(tmp_path, sign=sign, public=public)
    replica.sync_index(sign())
    tampered = b"x" * len(data)
    with pytest.raises(ChunkTransferRejected):
        replica.sync_object(
            transfer,
            read_chunk=lambda offset, length: tampered[offset:offset + length],
        )

    blocked = _forced_transfer(
        data, license_distribution="restricted", data_class="private",
    )
    with pytest.raises(LibraryReplicaDenied):
        replica.sync_object(
            blocked, read_chunk=lambda offset, length: data[offset:offset + length],
        )


def test_replica_resumes_and_rejects_duplicate_or_overlapping_chunks(tmp_path):
    data = b"0123456789abcdef" * 4
    _, sign, transfer, public = _index_fixture(data)
    replica = _replica(tmp_path, sign=sign, public=public)
    replica.sync_index(sign())

    first = replica.sync_object(
        transfer, chunk_bytes=16, max_chunks=1,
        read_chunk=lambda offset, length: data[offset:offset + length],
    )
    assert first.complete is False
    assert first.offset == 16

    with pytest.raises(ChunkTransferRejected):
        replica.append_chunk(transfer, offset=0, chunk=data[:16])

    rest = replica.sync_object(
        transfer, chunk_bytes=16, max_chunks=16,
        read_chunk=lambda offset, length: data[offset:offset + length],
    )
    assert rest.complete is True
    assert rest.offset == len(data)
    assert rest.path.read_bytes() == data


def test_replica_status_is_truthful_when_disconnected_or_stale(tmp_path):
    data = b"states"
    _, sign, transfer, public = _index_fixture(data)
    replica = _replica(tmp_path, sign=sign, public=public)
    assert replica.status(now=NOW)["state"] == "UNKNOWN"
    assert replica.mark_disconnected(
        state="OFFLINE", now=NOW, error_code="PRIMARY_OFFLINE",
    )["state"] == "OFFLINE"
    assert replica.mark_disconnected(
        state="UNKNOWN", now=NOW, error_code="NO_OBSERVATION",
    )["state"] == "UNKNOWN"

    replica.sync_index(sign(), now=NOW)
    assert replica.status(now=NOW)["state"] == "SYNCED"
    assert replica.status(now=NOW + timedelta(seconds=31))["state"] == "STALE"
    with pytest.raises(LibraryReplicaDenied):
        replica.sync_object(
            transfer, now=NOW + timedelta(seconds=31),
            read_chunk=lambda offset, length: data[offset:offset + length],
        )
