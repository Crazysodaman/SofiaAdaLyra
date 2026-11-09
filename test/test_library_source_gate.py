"""D028 source-vs-recipient generation, private Hub grant, and mTLS peer gate.

Owner approvals exercise the original SAFE signature/credential verifier
against disposable canonical Platform-local state. No production keys.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import ssl

import pytest

from sofia.platform.ops.library_chunk_receiver import PinnedChunkTransfer
from sofia.platform.run.library_peer_gate import selected_peer_grant_scope
from sofia.platform.run.library_source_gate import (
    HUB_CAPABILITY, HUB_PROTOCOL, CurrentLibraryHubAuthority,
    CurrentLibrarySourcePeerAuthorizer, selected_hub_grant_scope,
)
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.safe.operator_stop import OperatorStopStore
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
from test.test_platform_service_session import provision
from test.test_library_tls_chunk_transport import _pair


def _source_state(tmp_path):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    instant = datetime.now(timezone.utc)
    status = {
        "platform_id": platform_id, "generation": 43,
        "core_started": True, "operator_stop": False,
    }
    pin = PinnedChunkTransfer(
        source_platform_id=platform_id,
        target_platform_id="independent-recipient",
        content_sha256=sha256(b"signed-public-asset").hexdigest(),
        size_bytes=len(b"signed-public-asset"),
        generation=971, # the RECIPIENT, not the source epoch
        manifest_sha256="a" * 64, catalog_revision=7,
        artifact_kind="sdk", license_distribution="permitted",
        data_class="public",
    )
    perms = PermissionStore(state)
    scope = selected_hub_grant_scope(
        source_platform_id=platform_id, source_generation=43,
        bind_host="127.0.0.1", bind_port=47321,
    )
    authority = CurrentLibraryHubAuthority(
        permissions=perms, stop=OperatorStopStore(state),
        current_status=lambda: dict(status),
        source_platform_id=platform_id, source_generation=43,
        bind_host="127.0.0.1", bind_port=47321,
    )
    return perms, scope, authority, status, pin


def test_explicit_hub_requires_owner_grant_and_rechecks_source_run_generation(tmp_path):
    perms, scope, hub, status, pin = _source_state(tmp_path)
    assert hub() is False
    approval = grant_with_signed_owner(
        perms, HUB_CAPABILITY, scope=scope,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    assert hub() is True
    assert scope["source_generation"] == 43
    assert pin.generation == 971
    status["generation"] = 44
    assert hub() is False
    status["generation"] = 43
    status["operator_stop"] = True
    assert hub() is False
    status["operator_stop"] = False
    assert hub() is True
    revoke_with_signed_owner(perms, approval.grant_id)
    assert hub() is False


def test_hub_grant_cannot_enroll_public_bind_or_unbounded_endpoint(tmp_path):
    perms, scope, hub, status, pin = _source_state(tmp_path)
    now = datetime.now(timezone.utc)
    for mutation in (
        {"bind_host": "0.0.0.0"},
        {"bind_host": "8.8.8.8"},
        {"bind_port": 0},
        {"bind_port": True},
        {"source_generation": 0},
        {"source_generation": pin.generation},
        {"protocol": "unreviewed"},
        {"new_scope": "wildcard"},
    ):
        with pytest.raises(PermissionError):
            perms.grant(
                HUB_CAPABILITY, scope={**scope, **mutation},
                now=now, expires_at=now + timedelta(minutes=5),
                approval_id="untrusted-owner-proof",
            )
    for expiry in (None, now + timedelta(hours=2)):
        with pytest.raises(PermissionError):
            perms.grant(
                HUB_CAPABILITY, scope=scope,
                now=now, expires_at=expiry,
                approval_id="untrusted-owner-proof",
            )


@pytest.mark.skipif(os.name == "nt", reason="disposable mutual TLS socketpair")
def test_source_peer_is_pinned_to_recipient_cert_and_separate_run_epoch(tmp_path):
    perms, scope, hub, status, pin = _source_state(tmp_path)
    signed_hub = grant_with_signed_owner(
        perms, HUB_CAPABILITY, scope=scope,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    server, client = _pair(tmp_path)
    try:
        client_sha = sha256(server.getpeercert(binary_form=True)).hexdigest()
        peer_scope = selected_peer_grant_scope(
            transfer=pin, enrolled_peer_certificate_sha256=client_sha,
            max_chunk_bytes=pin.size_bytes,
            now=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        signed_peer = grant_with_signed_owner(
            perms, "library.peer.fetch", scope=peer_scope,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        gate = CurrentLibrarySourcePeerAuthorizer(
            permissions=perms, hub_enabled=hub,
            signed_transfer=pin,
            expected_recipient_certificate_sha256=client_sha,
            publisher_current=lambda _: True,
        )
        assert gate(server, client_sha, pin, 0, pin.size_bytes) is True
        assert pin.generation != status["generation"]  # source vs target
        with pytest.raises(PermissionError, match="certificate"):
            gate(server, "f" * 64, pin, 0, pin.size_bytes)
        with pytest.raises(PermissionError, match="differs"):
            gate(server, client_sha, replace(pin, generation=972), 0, pin.size_bytes)
        revoke_with_signed_owner(perms, signed_peer.grant_id)
        with pytest.raises(PermissionError, match="grant"):
            gate(server, client_sha, pin, 0, pin.size_bytes)
        revoke_with_signed_owner(perms, signed_hub.grant_id)
        assert hub() is False
    finally:
        server.close()
        client.close()
