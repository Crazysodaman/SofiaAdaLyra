"""D028 disposable two-Platform signed catalog -> mTLS -> B1 CAS test.

This exercises two real canonical Platform RUN services with different
generations, actual Python native IPC endpoints, two real SAFE owner-grant
stores (test WebAuthn signers), local TLS 1.3 CERT_REQUIRED on both sides,
source's exact Hub and recipient grants, received quarantine and one-use
recipient B1 CAS approval. No live networking outside 127.0.0.1, no real
production publisher package, installed release or Core startup.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import socket
import ssl
from threading import Thread

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkedArtifactReceiver
from sofia.platform.ops.platform_install import (
    OfflineArtifactCache, PlatformArtifact, PlatformKind,
)
from sofia.platform.ops.platform_library_admission import LIBRARY_PEER_CACHE_ADMIT
from sofia.platform.run.library_peer_gate import selected_peer_grant_scope
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.run.library_source_gate import (
    HUB_CAPABILITY, selected_hub_grant_scope,
)
from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from test.library_fixture_support import make_signed_offer_fixture
from test.owner_auth_fixture import grant_with_signed_owner, record_verified_owner_approval
from test.test_platform_service_session import provision
from test.test_core_link_conversation import tls_material


def _free_loopback_port():
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
    source_cert = sha256(
        ssl.PEM_cert_to_DER_cert(server_cert.read_text())
    ).hexdigest()
    recipient_cert = sha256(
        ssl.PEM_cert_to_DER_cert(client_cert.read_text())
    ).hexdigest()
    return server, client, source_cert, recipient_cert


@pytest.mark.skipif(os.name == "nt", reason="actual disposable POSIX B1 and private TLS source")
def test_two_canonical_platforms_transfer_signed_selection_into_recipient_b1(tmp_path):
    source_home, recipient_home = tmp_path / "source", tmp_path / "recipient"
    source_home.mkdir()
    recipient_home.mkdir()
    source_home.chmod(0o700)
    recipient_home.chmod(0o700)
    s_identity, s_current, s_state = provision(source_home)
    r_identity, r_current, r_state = provision(recipient_home)
    # Intentionally fence recipient epoch separately from source epoch.
    with PlatformServiceSession(
        r_identity.home, r_state, r_current.identity.canonical_uuid,
        r_current.public_key_sha256,
    ):
        pass
    data = b"independent-verified-sdk-asset" * 12
    env, sign, offer = make_signed_offer_fixture()
    source_id = s_current.identity.canonical_uuid
    target_id = r_current.identity.canonical_uuid
    server_tls, client_tls, source_cert, recipient_cert = _tls_contexts(tmp_path)
    now = datetime.now(timezone.utc)
    env["source_platform_id"] = source_id
    env["target_platform_id"] = target_id
    env["catalog"]["target_platform_id"] = target_id
    env["catalog"]["source"]["source_id"] = source_id
    env["catalog"]["source"]["last_observed_at"] = now.isoformat()
    env["issued_at"] = (now - timedelta(seconds=3)).isoformat()
    env["expires_at"] = (now + timedelta(minutes=3)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (now + timedelta(minutes=2)).isoformat()
    article = PlatformArtifact(
        artifact_id="sdk.release.1", version="1.0", platform=PlatformKind.LINUX,
        architecture="x86_64", sha256=sha256(data).hexdigest(),
        signer_key_id="independently-trusted-release-key",
        signature_verified=True, source="synthetic-test-package-signer",
    )
    source_file = tmp_path / "signed-test-wheel"
    source_file.write_bytes(data)
    source_file.chmod(0o600)
    source_cache = OfflineArtifactCache(tmp_path / "source-cache", max_bytes=65536)
    source_cache.import_artifact(article, source_file)
    recipient_cache = OfflineArtifactCache(tmp_path / "recipient-cache", max_bytes=65536)
    receiver = ChunkedArtifactReceiver(tmp_path / "recipient-quarantine", max_bytes=65536)
    s_permissions = PermissionStore(s_state)
    r_permissions = PermissionStore(r_state)
    port = _free_loopback_port()

    with PlatformServiceSession(
        s_identity.home, s_state, source_id, s_current.public_key_sha256,
    ) as source:
        with PlatformServiceSession(
            r_identity.home, r_state, target_id, r_current.public_key_sha256,
        ) as recipient:
            assert source.status()["generation"] != recipient.status()["generation"]
            transfer = replace(
                offer["transfer"],
                source_platform_id=source_id, target_platform_id=target_id,
                generation=recipient.status()["generation"],
            )
            assert transfer.generation != source.status()["generation"]
            env["catalog"]["items"][0]["content_digest"] = transfer.content_sha256
            env["catalog"]["items"][0]["manifest_digest"] = transfer.manifest_sha256
            signed_bytes = sign()
            expires = datetime.now(timezone.utc) + timedelta(minutes=5)
            hub_scope = selected_hub_grant_scope(
                source_platform_id=source_id,
                source_generation=source.status()["generation"],
                bind_host="127.0.0.1", bind_port=port,
            )
            grant_with_signed_owner(
                s_permissions, HUB_CAPABILITY, scope=hub_scope,
                expires_at=expires,
            )
            grant_with_signed_owner(
                s_permissions, "library.peer.fetch",
                scope=selected_peer_grant_scope(
                    transfer=transfer,
                    enrolled_peer_certificate_sha256=recipient_cert,
                    max_chunk_bytes=len(data), now=datetime.now(timezone.utc),
                    expires_at=expires,
                ), expires_at=expires,
            )
            grant_with_signed_owner(
                r_permissions, "library.peer.fetch",
                scope=selected_peer_grant_scope(
                    transfer=transfer,
                    enrolled_peer_certificate_sha256=source_cert,
                    max_chunk_bytes=len(data), now=datetime.now(timezone.utc),
                    expires_at=expires,
                ), expires_at=expires,
            )
            def package_verifier(t, path):
                assert t == transfer
                assert source_cache.digest(path) == article.sha256
                # Synthetic package-signature assertion, never production
                # publisher trust or a valid release-signing receipt.
                return article

            hub = source.open_owner_approved_library_hub(
                bind_host="127.0.0.1", port=port, tls_context=server_tls,
                transfer=transfer, raw_signed_index=signed_bytes,
                expected_artifact_id="sdk.release.1",
                trusted_publisher_public_key=offer["trusted_publisher_public_key"],
                expected_publisher_key_sha256=offer["expected_publisher_key_sha256"],
                expected_catalog_generation=3,
                publisher_key_current=lambda _: True,
                package_signer_current=lambda _: True,
                verify_independent_package=package_verifier,
                artifact=article, cache=source_cache,
                expected_recipient_certificate_sha256=recipient_cert,
            )
            errors = []

            def serve():
                try:
                    assert hub.serve_once() == len(data)
                except Exception as exc:
                    errors.append(exc)

            worker = Thread(target=serve)
            worker.start()

            def open_tls():
                return client_tls.wrap_socket(
                    socket.create_connection(hub.endpoint, timeout=5),
                    server_hostname="localhost",
                )

            # One service-owned call must traverse the independently verified
            # signed catalog, enrolled mTLS peer, quarantine, whole-object B1
            # package verification and distinct one-use recipient CAS proof.
            params = {
                "source": "ENROLLED_PEER",
                "source_platform_id": transfer.source_platform_id,
                "target_platform_id": transfer.target_platform_id,
                "content_digest": transfer.content_sha256,
                "manifest_digest": transfer.manifest_sha256,
                "artifact_kind": transfer.artifact_kind,
                "size_bytes": transfer.size_bytes,
                "generation": transfer.generation,
                "catalog_revision": transfer.catalog_revision,
                "signer_key_id": article.signer_key_id,
                "safe_state": str(r_state.absolute()),
                "cache_root": str(recipient_cache.root),
            }
            now = datetime.now(timezone.utc)
            proof = ExecutionApproval(
                approval_id="approval:recipient-b1-cas",
                capability=LIBRARY_PEER_CACHE_ADMIT,
                request_fingerprint=execution_fingerprint(
                    LIBRARY_PEER_CACHE_ADMIT, params,
                ),
                approved_by="Sparks",
                approved_at=now,
                expires_at=now + timedelta(minutes=5),
            )
            record_verified_owner_approval(
                ExecutionApprovalVerifier(r_state), proof,
            )
            signed_source = InstalledSignedCatalogSource(
                raw_signed_index=signed_bytes,
                trusted_publisher_public_key=offer["trusted_publisher_public_key"],
                expected_publisher_key_sha256=offer["expected_publisher_key_sha256"],
                expected_source_platform_id=source_id,
                expected_catalog_generation=3,
                minimum_catalog_revision=transfer.catalog_revision,
                publisher_key_current=lambda _: True,
            )
            try:
                result = recipient.acquire_owner_approved_library_asset(
                    approval_id=proof.approval_id,
                    transfer=transfer,
                    expected_artifact_id="sdk.release.1",
                    receiver=receiver,
                    cache=recipient_cache,
                    open_enrolled_tls=open_tls,
                    enrolled_source_certificate_sha256=source_cert,
                    verify_independent_package=package_verifier,
                    package_signer_current=lambda _: True,
                    signed_catalog_source=lambda: signed_source,
                    chunk_bytes=len(data),
                    max_chunks=1,
                )
            finally:
                worker.join(timeout=8)
            assert not worker.is_alive()
            assert errors == []
            assert result["cache_state"] == "CACHED_VERIFIED"
            assert result["received_bytes"] == len(data)
            assert result["verified_bytes"] == len(data)
            assert result["network_attempted"] is True
            assert result["owner_proof_consumed"] is True
            assert result["install_executed"] is False
            assert result["active"] is None
            assert recipient_cache.resolve(article).read_bytes() == data
            hub.close()
