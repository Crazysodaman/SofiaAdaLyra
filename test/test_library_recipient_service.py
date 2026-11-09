"""D028 single-writer recipient bound to original Platform RUN and real SAFE.

Uses disposable publisher keys and a stubbed network transfer only. It is
NOT actual LAN signed release acceptance, nor a minted production grant.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.run.library_peer_gate import selected_peer_grant_scope
from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from test.library_fixture_support import make_signed_offer_fixture
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
from test.test_platform_service_session import provision


@pytest.fixture
def service_recipient(tmp_path):
    identity, current, state = provision(tmp_path)
    service = PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    )
    env, sign, args = make_signed_offer_fixture()
    now = datetime.now(timezone.utc)
    transfer = replace(
        args["transfer"],
        target_platform_id=current.identity.canonical_uuid,
        generation=service.status()["generation"],
    )
    env["target_platform_id"] = current.identity.canonical_uuid
    env["catalog"]["target_platform_id"] = current.identity.canonical_uuid
    env["issued_at"] = (now - timedelta(seconds=2)).isoformat()
    env["expires_at"] = (now + timedelta(minutes=3)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=2)
    ).isoformat()
    env["catalog"]["source"]["last_observed_at"] = now.isoformat()
    signed_bytes = sign()
    source = InstalledSignedCatalogSource(
        raw_signed_index=signed_bytes,
        trusted_publisher_public_key=args["trusted_publisher_public_key"],
        expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
        expected_source_platform_id=transfer.source_platform_id,
        expected_catalog_generation=3,
        minimum_catalog_revision=7,
        publisher_key_current=lambda _: True,
    )
    receiver = ChunkedArtifactReceiver(
        tmp_path / "quarantine", max_bytes=65536,
    )
    cache = OfflineArtifactCache(tmp_path / "cache", max_bytes=65536)
    options = {
        "transfer": transfer,
        "expected_artifact_id": "sdk.release.1",
        "receiver": receiver,
        "cache": cache,
        "open_enrolled_tls": lambda: None,
        "enrolled_source_certificate_sha256": "a" * 64,
        "verify_independent_package": lambda *_: None,
        "package_signer_current": lambda _: True,
        "signed_catalog_source": lambda: source,
        "clock": lambda: datetime.now(timezone.utc),
    }
    try:
        yield service, options, PermissionStore(state)
    finally:
        service.close()


def test_unenrolled_platform_denies_before_recipient_network(service_recipient, monkeypatch):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    service, options, permissions = service_recipient
    invoked = []
    monkeypatch.setattr(
        pipeline, "acquire_from_independently_signed_index",
        lambda **_: invoked.append(True),
    )
    with pytest.raises(PermissionError, match="enrollment"):
        service.acquire_owner_approved_library_asset(
            approval_id="not-an-owner-approval",
            **options,
        )
    assert not invoked


def test_real_owner_grant_connects_service_recipient_to_independent_signed_pipeline(
    service_recipient, monkeypatch,
):
    import sofia.platform.run.library_recipient_service as service_module
    service, options, permissions = service_recipient
    now = datetime.now(timezone.utc)
    transfer = options["transfer"]
    scope = selected_peer_grant_scope(
        transfer=transfer,
        enrolled_peer_certificate_sha256=options["enrolled_source_certificate_sha256"],
        max_chunk_bytes=min(1024, transfer.size_bytes),
        expires_at=now + timedelta(minutes=4),
        now=now,
    )
    grant = grant_with_signed_owner(
        permissions, "library.peer.fetch", scope=scope,
        expires_at=now + timedelta(minutes=4),
    )
    calls = []
    def actual_boundary(**kwargs):
        calls.append(kwargs)
        assert kwargs["transfer"] == transfer
        assert kwargs["current_host_admit"](transfer) is True
        assert kwargs["publisher_current"](transfer) is True
        assert kwargs["expected_peer_certificate_sha256"] == "a" * 64
        assert kwargs["canonical_safe_state"] == service.storage.path
        return {
            "cache_state": "RECEIVING", "received_bytes": 256,
            "verified_bytes": 0, "owner_proof_consumed": False,
            "install_executed": False, "installed": None, "active": None,
        }
    monkeypatch.setattr(
        service_module,
        "acquire_from_independently_signed_index", actual_boundary,
    )
    progress = service.acquire_owner_approved_library_asset(
        approval_id="separate-unused-B1-proof",
        chunk_bytes=512, max_chunks=2, **options,
    )
    assert progress["cache_state"] == "RECEIVING"
    assert progress["installed"] is None
    assert len(calls) == 1
    revoke_with_signed_owner(permissions, grant.grant_id)
    with pytest.raises(PermissionError, match="enrollment"):
        service.acquire_owner_approved_library_asset(
            approval_id="separate-unused-B1-proof",
            **options,
        )
    assert len(calls) == 1


def test_wrong_RUN_generation_and_other_recipient_denied_before_fetch(service_recipient):
    service, options, permissions = service_recipient
    old = options["transfer"]
    for tamper in (
        replace(old, generation=old.generation + 1),
        replace(old, target_platform_id="another-recipient"),
    ):
        with pytest.raises(ChunkTransferRejected, match="RUN or STOP mismatch"):
            service.acquire_owner_approved_library_asset(
                approval_id="unused",
                **{**options, "transfer": tamper},
            )


def test_recipient_single_writer_lock_denies_simultaneous_actions(service_recipient):
    service, options, permissions = service_recipient
    assert service._recipient_transfer_lock.acquire(blocking=False)
    try:
        with pytest.raises(PermissionError, match="another installed recipient"):
            service.acquire_owner_approved_library_asset(
                approval_id="unused", **options,
            )
    finally:
        service._recipient_transfer_lock.release()



def test_recipient_denies_owner_grant_chunk_scope_smaller_than_requested_before_dial(
    service_recipient, monkeypatch,
):
    import sofia.platform.run.library_recipient_service as service_module
    service, options, permissions = service_recipient
    now = datetime.now(timezone.utc)
    transfer = options["transfer"]
    scope = selected_peer_grant_scope(
        transfer=transfer,
        enrolled_peer_certificate_sha256=options["enrolled_source_certificate_sha256"],
        max_chunk_bytes=min(256, transfer.size_bytes),
        expires_at=now + timedelta(minutes=4), now=now,
    )
    grant_with_signed_owner(
        permissions, "library.peer.fetch", scope=scope,
        expires_at=now + timedelta(minutes=4),
    )
    network = []
    monkeypatch.setattr(
        service_module, "acquire_from_independently_signed_index",
        lambda **_: network.append(True),
    )
    with pytest.raises(PermissionError, match="chunk scope"):
        service.acquire_owner_approved_library_asset(
            approval_id="unused", chunk_bytes=1024, **options,
        )
    assert network == []
