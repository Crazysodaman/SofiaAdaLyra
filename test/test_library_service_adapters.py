"""Disposable D028 service-adapter mechanics, never installed-host certification.

These tests exercise the Core-free primary Hub adapter and the recipient/replica
adapter with real local SQLite, real SAFE grants, real quarantine/CAS and (where
available) real loopback mTLS. They do not claim signed installed Windows or
Debian host acceptance, production publisher keys, a live Hub deployment or a
Core.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import socket
import ssl
from threading import Thread
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_owner_catalog_publish import OwnerPublishedAsset
from sofia.platform.ops.library_primary_lease import (
    LibraryPrimaryDenied, LibraryPrimaryLeaseStore,
)
from sofia.platform.ops.library_primary_service import LibraryPrimaryService
from sofia.platform.ops.library_replica import (
    LibraryReplicaDenied, LibraryReplicaStateStore,
)
from sofia.platform.ops.library_replica_service import LibraryRecipientService
from sofia.platform.ops.library_signed_index import (
    SCHEMA, _DOMAIN, verify_signed_library_index,
)
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from sofia.platform.run.library_peer_gate import CurrentRecipientPeerAuthorizer
from sofia.platform.run.library_source_gate import (
    HUB_CAPABILITY, selected_hub_grant_scope,
)
from sofia.platform.run.library_peer_gate import selected_peer_grant_scope
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.local_store import PlatformLocalStore
from test.owner_auth_fixture import (
    grant_with_signed_owner, revoke_with_signed_owner,
)
from test.test_core_link_conversation import tls_material

PRIMARY = "primary-library-host"
REPLICA = "read-only-replica-host"
LIBRARY = "private-library-1"
SOURCE = "source-platform"
TARGET = "target-platform"
ARTIFACT_ID = "sdk.release.1"
SIGNER = "synthetic-independent-signer"
MANIFEST = "a" * 64
NOW = datetime.now(timezone.utc)
SOURCE_GENERATION = 5
TARGET_GENERATION = 9
CATALOG_GENERATION = 3
CATALOG_REVISION = 7


def _local_state(root, host: str) -> PlatformLocalStore:
    return PlatformLocalStore(
        root / "platform.db",
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=host,
    )


def _cache_and_artifact(root, data: bytes) -> tuple[OfflineArtifactCache, PlatformArtifact]:
    artifact = PlatformArtifact(
        artifact_id=ARTIFACT_ID, version="1.0", platform=PlatformKind.LINUX,
        architecture="x86_64", sha256=sha256(data).hexdigest(),
        signer_key_id=SIGNER, signature_verified=True,
        source="synthetic-disposable-signer",
    )
    source = root / "signed-payload"
    source.write_bytes(data)
    source.chmod(0o600)
    cache = OfflineArtifactCache(root / "cache", max_bytes=max(len(data) * 2, 4096))
    cache.import_artifact(artifact, source)
    return cache, artifact


def _offer(
    data: bytes, *, license_distribution: str = "permitted",
    data_class: str = "public", source_status: str = "CURRENT",
    source=SOURCE, target=TARGET, revision: int = CATALOG_REVISION,
    transfer_generation: int = TARGET_GENERATION,
):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    transfer = PinnedChunkTransfer(
        source_platform_id=source, target_platform_id=target,
        content_sha256=sha256(data).hexdigest(), size_bytes=len(data),
        generation=transfer_generation, manifest_sha256=MANIFEST,
        catalog_revision=revision, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    item = {
        "artifact_id": ARTIFACT_ID, "kind": "sdk", "version": "1.0",
        "revision": revision, "manifest_digest": MANIFEST,
        "content_digest": transfer.content_sha256,
        "size_bytes": transfer.size_bytes,
        "publisher": "owner-approved-publisher",
        "signer_key_id": SIGNER,
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
        "source_platform_id": source,
        "target_platform_id": target,
        "catalog_revision": revision,
        "catalog_generation": CATALOG_GENERATION,
        "issued_at": (NOW - timedelta(seconds=2)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=2)).isoformat(),
        "catalog": {
            "catalog_revision": revision,
            "catalog_generation": CATALOG_GENERATION,
            "catalog_fresh_until": (NOW + timedelta(seconds=30)).isoformat(),
            "target_platform_id": target,
            "source": {
                "kind": "OWNER_SELECTED_HUB", "source_id": source,
                "last_observed_at": NOW.isoformat(),
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

    def external_signer(payload: bytes) -> bytes:
        return private.sign(payload)

    return SimpleNamespace(
        transfer=transfer, envelope=envelope, sign=sign,
        sign_external=external_signer, public=public, private=private,
        item=item,
    )


def _asset(offer) -> OwnerPublishedAsset:
    item = offer.item
    return OwnerPublishedAsset(
        artifact_id=item["artifact_id"], kind=item["kind"],
        version=item["version"], revision=item["revision"],
        manifest_digest=item["manifest_digest"],
        content_digest=item["content_digest"], size_bytes=item["size_bytes"],
        publisher=item["publisher"], signer_key_id=item["signer_key_id"],
        signature_receipt_ref=item["signature_receipt_ref"],
        target_os_arch=item["target_os_arch"], sdk_range=item["sdk_range"],
        abi_range=item["abi_range"],
        license_distribution=item["license_distribution"],
        data_class=item["data_class"], distribution_allowed=True,
        independent_package_verified=True,
    )


def _primary(
    tmp_path, offer, *, status, data: bytes,
    host=PRIMARY, platform=SOURCE, root=None,
):
    root = root or tmp_path / "source"
    root.mkdir(parents=True, exist_ok=True)
    storage = _local_state(root, host)
    permissions = PermissionStore(root / "platform.db")
    stop = OperatorStopStore(root / "platform.db")
    cache, artifact = _cache_and_artifact(root, data)
    return LibraryPrimaryService(
        storage=storage, logical_library_id=LIBRARY,
        host_identity=host, platform_id=platform,
        status=lambda: status, permissions=permissions, stop=stop,
        trusted_publisher_public_key=offer.public,
        expected_publisher_key_sha256=sha256(offer.public).hexdigest(),
        publisher_key_current=lambda _: True,
        expected_catalog_generation=CATALOG_GENERATION,
        cache=cache, artifact=artifact,
        package_signer_current=lambda _: True,
        verify_independent_package=lambda transfer, path: artifact,
        clock=lambda: NOW,
    )


def _recipient(tmp_path, offer, *, status, max_bytes=64 * 1024, root=None):
    root = root or tmp_path / "replica"
    root.mkdir(parents=True, exist_ok=True)
    storage = _local_state(root, REPLICA)
    permissions = PermissionStore(root / "platform.db")
    stop = OperatorStopStore(root / "platform.db")
    receiver = ChunkedArtifactReceiver(root / "incoming", max_bytes=max_bytes)
    return LibraryRecipientService(
        storage=storage, logical_library_id=LIBRARY,
        host_identity=REPLICA, replica_platform_id=TARGET,
        primary_platform_id=SOURCE, receiver=receiver,
        trusted_publisher_public_key=offer.public,
        expected_publisher_key_sha256=sha256(offer.public).hexdigest(),
        expected_catalog_generation=CATALOG_GENERATION,
        minimum_catalog_revision=CATALOG_REVISION,
        authenticate_primary=lambda identity: identity == SOURCE,
        publisher_key_current=lambda _: True,
        source_allowed=lambda _: True,
        permissions=permissions, stop=stop, status=lambda: status,
        clock=lambda: NOW,
    )


def test_read_only_replica_role_cannot_claim_writer_or_roll_epoch(tmp_path):
    storage = _local_state(tmp_path / "replica", REPLICA)
    lease = LibraryPrimaryLeaseStore(storage, logical_library_id=LIBRARY)
    record = lease.mark_read_only_replica(
        host_identity=REPLICA, platform_id=TARGET,
        primary_platform_id=SOURCE, primary_epoch=2,
        catalog_revision=CATALOG_REVISION, now=NOW,
    )
    assert record.role == "READ_REPLICA"
    assert record.read_only_replica is True
    assert lease.status(now=NOW)["state"] == "READ_REPLICA"
    assert lease.status(now=NOW)["read_only"] is True

    with pytest.raises(LibraryPrimaryDenied, match="read-only replica"):
        lease.claim_primary(host_identity=REPLICA, platform_id=TARGET, now=NOW)
    with pytest.raises(LibraryPrimaryDenied, match="not a writable primary"):
        lease.advance_catalog_revision(
            host_identity=REPLICA, platform_id=TARGET, epoch=2,
            writer_token="0" * 64, expected_revision=CATALOG_REVISION, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="rollback"):
        lease.mark_read_only_replica(
            host_identity=REPLICA, platform_id=TARGET,
            primary_platform_id=SOURCE, primary_epoch=1,
            catalog_revision=CATALOG_REVISION, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="rollback"):
        lease.mark_read_only_replica(
            host_identity=REPLICA, platform_id=TARGET,
            primary_platform_id=SOURCE, primary_epoch=2,
            catalog_revision=CATALOG_REVISION - 1, now=NOW,
        )


def test_primary_adapter_publishes_signed_catalog_and_denies_dual_primary(tmp_path):
    data = b"independent-verified-sdk-asset" * 12
    offer = _offer(data)
    source_status = {
        "platform_id": SOURCE, "generation": SOURCE_GENERATION,
        "operator_stop": False,
    }
    primary = _primary(tmp_path, offer, status=source_status, data=data)
    assert primary.status()["state"] == "UNINITIALIZED"
    claimed = primary.claim_primary(now=NOW)
    assert claimed["state"] == "PRIMARY"
    assert claimed["writer_claimed"] is True

    published = primary.publish_catalog(
        transfer=offer.transfer, selected_assets=(_asset(offer),),
        expected_artifact_id=ARTIFACT_ID,
        sign_external=offer.sign_external, now=NOW,
    )
    verified = verify_signed_library_index(
        published,
        trusted_publisher_public_key=offer.public,
        expected_publisher_key_sha256=sha256(offer.public).hexdigest(),
        expected_source_platform_id=SOURCE,
        expected_target_platform_id=TARGET,
        expected_catalog_generation=CATALOG_GENERATION,
        minimum_catalog_revision=CATALOG_REVISION,
        now=NOW, publisher_key_current=lambda _: True,
    )
    assert verified.catalog_revision == CATALOG_REVISION
    assert verified.catalog["items"][0]["content_digest"] == offer.transfer.content_sha256

    snapshot = json.dumps(primary.status(), sort_keys=True)
    assert str(tmp_path) not in snapshot
    assert "0" * 64 not in snapshot

    second = LibraryPrimaryService(
        storage=primary.storage, logical_library_id=LIBRARY,
        host_identity="other-primary-host", platform_id=TARGET,
        status=lambda: {
            "platform_id": TARGET, "generation": TARGET_GENERATION,
            "operator_stop": False,
        },
        permissions=primary.permissions, stop=primary.stop,
        trusted_publisher_public_key=offer.public,
        expected_publisher_key_sha256=sha256(offer.public).hexdigest(),
        publisher_key_current=lambda _: True,
        expected_catalog_generation=CATALOG_GENERATION,
        cache=primary.cache, artifact=primary.artifact,
        package_signer_current=lambda _: True,
        verify_independent_package=lambda transfer, path: primary.artifact,
        clock=lambda: NOW,
    )
    with pytest.raises(LibraryPrimaryDenied, match="dual-primary"):
        second.claim_primary(now=NOW)

    receipt = primary.fence_primary(now=NOW)
    assert receipt.old_primary_epoch == 1
    assert primary.status()["state"] == "FENCED"
    with pytest.raises(LibraryPrimaryDenied, match="fenced|writer"):
        primary.publish_catalog(
            transfer=offer.transfer, selected_assets=(_asset(offer),),
            expected_artifact_id=ARTIFACT_ID,
            sign_external=offer.sign_external, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="fenced"):
        second.claim_primary(now=NOW)


def test_replica_adapter_syncs_read_only_and_refuses_catalog_mutation(tmp_path):
    data = b"verified-replica-object" * 8
    offer = _offer(data)
    status = {
        "platform_id": TARGET, "generation": TARGET_GENERATION,
        "operator_stop": False,
    }
    recipient = _recipient(tmp_path, offer, status=status)
    marked = recipient.mark_read_only(
        primary_epoch=1, catalog_revision=CATALOG_REVISION, now=NOW,
    )
    assert marked["role"] == "READ_REPLICA"
    assert marked["catalog_writable"] is False
    assert marked["read_only"] is True

    verified = recipient.sync_index(offer.sign(), primary_epoch=1, now=NOW)
    assert verified.catalog_revision == CATALOG_REVISION
    result = recipient.sync_object(
        offer.transfer,
        read_chunk=lambda offset, length: data[offset:offset + length],
        now=NOW,
    )
    assert result.complete is True
    assert result.path.read_bytes() == data
    assert recipient.replica_state.current().read_only is True
    assert recipient.status()["replica_state"] == "SYNCED"
    assert recipient.status()["catalog_revision"] == CATALOG_REVISION

    with pytest.raises(LibraryPrimaryDenied, match="read-only replica"):
        LibraryPrimaryLeaseStore(
            recipient.storage, logical_library_id=LIBRARY,
        ).claim_primary(
            host_identity=REPLICA, platform_id=TARGET, now=NOW,
        )
    with pytest.raises(LibraryReplicaDenied, match="stale primary epoch"):
        recipient.sync_index(offer.sign(), primary_epoch=0, now=NOW)
    with pytest.raises(LibraryPrimaryDenied):
        recipient.promote_to_primary(
            new_primary_host_id=REPLICA, new_primary_platform_id=TARGET,
            expected_old_epoch=1,
            old_primary_fence_receipt=None,
            safe_authorization=lambda: True, now=NOW,
        )


def test_replica_adapter_refuses_a_fenced_old_primary_epoch(tmp_path):
    data = b"fenced-epoch"
    offer = _offer(data)
    primary = _primary(
        tmp_path, offer, data=data,
        status={"platform_id": SOURCE, "generation": SOURCE_GENERATION,
                "operator_stop": False},
    )
    primary.claim_primary(now=NOW)
    receipt = primary.fence_primary(now=NOW)

    storage = primary.storage
    receiver = ChunkedArtifactReceiver(
        tmp_path / "fenced-replica-incoming", max_bytes=4096,
    )
    recipient = LibraryRecipientService(
        storage=storage, logical_library_id=LIBRARY,
        host_identity=REPLICA, replica_platform_id=TARGET,
        primary_platform_id=SOURCE, receiver=receiver,
        trusted_publisher_public_key=offer.public,
        expected_publisher_key_sha256=sha256(offer.public).hexdigest(),
        expected_catalog_generation=CATALOG_GENERATION,
        minimum_catalog_revision=CATALOG_REVISION,
        authenticate_primary=lambda identity: identity == SOURCE,
        publisher_key_current=lambda _: True,
        source_allowed=lambda _: True,
        permissions=primary.permissions, stop=primary.stop,
        status=lambda: {
            "platform_id": TARGET, "generation": TARGET_GENERATION,
            "operator_stop": False,
        },
        clock=lambda: NOW,
    )
    with pytest.raises(LibraryReplicaDenied, match="fenced"):
        recipient.sync_index(offer.sign(), primary_epoch=1, now=NOW)
    assert recipient.status()["role"] == "FENCED"
    assert recipient.status()["catalog_writable"] is False

    with pytest.raises(PermissionError, match="SAFE"):
        recipient.promote_to_primary(
            new_primary_host_id=REPLICA, new_primary_platform_id=TARGET,
            expected_old_epoch=receipt.old_primary_epoch,
            old_primary_fence_receipt=receipt,
            safe_authorization=lambda: False, now=NOW,
        )
    promoted = recipient.promote_to_primary(
        new_primary_host_id=REPLICA, new_primary_platform_id=TARGET,
        expected_old_epoch=receipt.old_primary_epoch,
        old_primary_fence_receipt=receipt,
        safe_authorization=lambda: True, now=NOW,
    )
    assert promoted["role"] == "PRIMARY"
    assert promoted["read_only"] is False
    # This adapter still exposes no write/install operation after promotion.
    assert promoted["catalog_writable"] is False


def test_replica_adapter_refuses_license_wrong_signer_and_quota(tmp_path):
    data = b"license-and-quota"
    blocked = _offer(
        data, license_distribution="restricted", data_class="private",
    )
    recipient = _recipient(
        tmp_path / "license", blocked,
        status={"platform_id": TARGET, "generation": TARGET_GENERATION,
                "operator_stop": False},
    )
    with pytest.raises(LibraryReplicaDenied):
        recipient.sync_index(blocked.sign(), primary_epoch=1, now=NOW)

    good = _offer(data)
    wrong_signer = _offer(data)
    mismatched = _recipient(
        tmp_path / "wrong-signer", good,
        status={"platform_id": TARGET, "generation": TARGET_GENERATION,
                "operator_stop": False},
    )
    with pytest.raises(PermissionError):
        mismatched.sync_index(wrong_signer.sign(), primary_epoch=1, now=NOW)

    small = _recipient(
        tmp_path / "quota", good, max_bytes=len(data) // 2,
        status={"platform_id": TARGET, "generation": TARGET_GENERATION,
                "operator_stop": False},
    )
    small.sync_index(good.sign(), primary_epoch=1, now=NOW)
    with pytest.raises(ChunkTransferRejected):
        small.sync_object(
            good.transfer,
            read_chunk=lambda offset, length: data[offset:offset + length],
            now=NOW,
        )


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _tls_contexts(root):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(root)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = server.maximum_version = ssl.TLSVersion.TLSv1_3
    server.verify_mode = ssl.CERT_REQUIRED
    server.load_verify_locations(cafile=str(ca))
    server.load_cert_chain(str(server_cert), str(server_key))
    client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    client.minimum_version = client.maximum_version = ssl.TLSVersion.TLSv1_3
    client.load_cert_chain(str(client_cert), str(client_key))
    source_sha = sha256(ssl.PEM_cert_to_DER_cert(server_cert.read_text())).hexdigest()
    replica_sha = sha256(ssl.PEM_cert_to_DER_cert(client_cert.read_text())).hexdigest()
    return server, client, source_sha, replica_sha


def _two_hosts(tmp_path, data):
    (tmp_path / "source").mkdir()
    (tmp_path / "replica").mkdir()
    offer = _offer(data)
    source_status = {
        "platform_id": SOURCE, "generation": SOURCE_GENERATION,
        "operator_stop": False,
    }
    replica_status = {
        "platform_id": TARGET, "generation": TARGET_GENERATION,
        "operator_stop": False,
    }
    server_tls, client_tls, source_sha, replica_sha = _tls_contexts(tmp_path)
    primary = _primary(tmp_path, offer, status=source_status, data=data)
    primary.claim_primary(now=NOW)
    recipient = _recipient(tmp_path, offer, status=replica_status)
    recipient.mark_read_only(
        primary_epoch=1, catalog_revision=CATALOG_REVISION, now=NOW,
    )
    signed = offer.sign()
    recipient.sync_index(signed, primary_epoch=1, now=NOW)

    port = _free_loopback_port()
    expires = NOW + timedelta(minutes=5)
    chunk_cap = min(1024, len(data))
    s_permissions = primary.permissions
    r_permissions = recipient.permissions
    source_hub_grant = grant_with_signed_owner(
        s_permissions, HUB_CAPABILITY,
        scope=selected_hub_grant_scope(
            source_platform_id=SOURCE, source_generation=SOURCE_GENERATION,
            bind_host="127.0.0.1", bind_port=port,
        ), expires_at=expires, now=NOW,
    )
    source_peer_grant = grant_with_signed_owner(
        s_permissions, "library.peer.fetch",
        scope=selected_peer_grant_scope(
            transfer=offer.transfer,
            enrolled_peer_certificate_sha256=replica_sha,
            max_chunk_bytes=chunk_cap, now=NOW, expires_at=expires,
        ), expires_at=expires, now=NOW,
    )
    recipient_peer_grant = grant_with_signed_owner(
        r_permissions, "library.peer.fetch",
        scope=selected_peer_grant_scope(
            transfer=offer.transfer,
            enrolled_peer_certificate_sha256=source_sha,
            max_chunk_bytes=chunk_cap, now=NOW, expires_at=expires,
        ), expires_at=expires, now=NOW,
    )

    primary.open_hub(
        bind_host="127.0.0.1", port=port, tls_context=server_tls,
        transfer=offer.transfer, raw_signed_index=signed,
        expected_artifact_id=ARTIFACT_ID,
        expected_recipient_certificate_sha256=replica_sha,
        timeout_seconds=2, now=NOW,
    )

    def open_tls():
        return client_tls.wrap_socket(
            socket.create_connection(primary.endpoint, timeout=5),
            server_hostname="localhost",
        )

    return SimpleNamespace(
        offer=offer, primary=primary, recipient=recipient,
        source_status=source_status, replica_status=replica_status,
        source_sha=source_sha, replica_sha=replica_sha,
        source_hub_grant=source_hub_grant,
        source_peer_grant=source_peer_grant,
        recipient_peer_grant=recipient_peer_grant,
        client_tls=client_tls, open_tls=open_tls,
    )


def test_primary_hub_and_replica_adapter_transfer_real_bytes_with_separate_grants(tmp_path):
    data = b"public-signed-service-adapter-bytes-" * 80
    setup = _two_hosts(tmp_path, data)
    primary, recipient = setup.primary, setup.recipient
    chunks = (len(data) + 1023) // 1024
    failures = []

    def serve():
        try:
            assert primary.serve_bounded(max_connections=chunks, now=NOW) == len(data)
        except Exception as exc:
            failures.append(exc)

    worker = Thread(target=serve)
    worker.start()
    try:
        result = recipient.sync_object(
            setup.offer.transfer, open_enrolled_tls=setup.open_tls,
            expected_peer_certificate_sha256=setup.source_sha,
            chunk_bytes=1024, max_chunks=chunks, now=NOW,
        )
    finally:
        worker.join(timeout=12)
        primary.close()
    assert not worker.is_alive()
    assert not failures
    assert result.complete is True
    assert result.offset == len(data)
    assert result.path.read_bytes() == data
    assert recipient.status()["replica_state"] == "SYNCED"
    assert recipient.replica_state.current().read_only is True
    assert primary.serving_status()["served_bytes"] == len(data)
    # Status is strict JSON with no private path or writer token.
    snapshot = json.dumps(recipient.status(), sort_keys=True)
    assert str(tmp_path) not in snapshot
    assert "writer_token" not in snapshot


def test_primary_adapter_revoked_hub_grant_cancels_before_serving(tmp_path):
    data = b"revoked-source-grant" * 20
    setup = _two_hosts(tmp_path, data)
    revoke_with_signed_owner(
        setup.primary.permissions, setup.source_hub_grant.grant_id,
        now=datetime.now(timezone.utc),
    )
    with pytest.raises(ChunkTransferRejected, match="revoked|STOP"):
        setup.primary.serve_once(now=NOW)
    assert setup.primary.serving_status()["state"] == "CLOSED"
    assert setup.primary.serving_status()["served_bytes"] == 0
    setup.primary.close()


def test_bounded_progress_and_resume_use_durable_receiver_offset(tmp_path):
    data = b"resume-bounded-chunks-" * 100
    setup = _two_hosts(tmp_path, data)
    primary, recipient = setup.primary, setup.recipient
    chunks = (len(data) + 1023) // 1024
    failures = []

    def serve(count):
        try:
            primary.serve_bounded(max_connections=count, now=NOW)
        except Exception as exc:
            failures.append(exc)

    first = Thread(target=serve, args=(1,))
    first.start()
    try:
        partial = recipient.sync_object(
            setup.offer.transfer, open_enrolled_tls=setup.open_tls,
            expected_peer_certificate_sha256=setup.source_sha,
            chunk_bytes=1024, max_chunks=1, now=NOW,
        )
    finally:
        first.join(timeout=8)
    assert not failures
    assert partial.complete is False
    assert partial.offset == 1024
    assert recipient.status()["replica_state"] == "SYNCING"

    rest = Thread(target=serve, args=(chunks - 1,))
    rest.start()
    try:
        completed = recipient.sync_object(
            setup.offer.transfer, open_enrolled_tls=setup.open_tls,
            expected_peer_certificate_sha256=setup.source_sha,
            chunk_bytes=1024, max_chunks=chunks, now=NOW,
        )
    finally:
        rest.join(timeout=12)
        primary.close()
    assert not failures
    assert completed.complete is True
    assert completed.path.read_bytes() == data


def test_recipient_stop_mid_transfer_preserves_only_verified_progress(tmp_path):
    data = b"stop-mid-transfer" * 200
    offer = _offer(data)
    status = {
        "platform_id": TARGET, "generation": TARGET_GENERATION,
        "operator_stop": False,
    }
    recipient = _recipient(tmp_path, offer, status=status)
    recipient.mark_read_only(
        primary_epoch=1, catalog_revision=CATALOG_REVISION, now=NOW,
    )
    recipient.sync_index(offer.sign(), primary_epoch=1, now=NOW)
    reads = []
    original_append = recipient.receiver.append_chunk

    def append_then_stop(*args, **kwargs):
        result = original_append(*args, **kwargs)
        status["operator_stop"] = True
        return result

    recipient.receiver.append_chunk = append_then_stop

    def read_chunk(offset, length):
        reads.append((offset, length))
        return data[offset:offset + length]

    with pytest.raises(LibraryReplicaDenied):
        recipient.sync_object(
            offer.transfer, read_chunk=read_chunk,
            chunk_bytes=1024, max_chunks=8, now=NOW,
        )
    assert len(reads) == 1
    # Exactly one verified chunk is durable; no silent completion or install.
    assert recipient.receiver.received_bytes(
        offer.transfer, authorize=lambda _: True,
    ) == 1024
    current = recipient.replica_state.current()
    assert current.read_only is True
    assert recipient.status()["replica_state"] in {"SYNCING", "UNKNOWN", "STALE"}
