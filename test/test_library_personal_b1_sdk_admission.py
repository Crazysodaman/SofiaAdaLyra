"""D028 personal SDK source receipt -> signed Hub index -> B1 recipient CAS.

Original repository fixtures supply a real disposable Ed25519 release signer,
actual SDK wheel, canonical B1 receipt store, private quarantine and a signed
one-use owner grant in the original SAFE verifier. No network is opened, no
Core/model is installed, and test credentials are NOT production publisher
trust or live-host acceptance evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from sofia.platform.ops.library_b1_sdk_publisher import (
    InstalledB1SignedSdkVerifier, review_personal_b1_sdk_offer,
)
from sofia.platform.ops.library_chunk_receiver import ChunkedArtifactReceiver
from sofia.platform.ops.library_owner_catalog_publish import (
    publish_signed_owner_catalog,
)
from sofia.platform.ops.library_recipient_pipeline import (
    acquire_from_independently_signed_index,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_library_admission import (
    LIBRARY_PEER_CACHE_ADMIT,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_library_b1_sdk_publisher import (
    installed_sdk, _record_test_only_installed_release,
)
from test.test_platform_service_session import provision


@pytest.fixture
def signed_personal_sdk(tmp_path, installed_sdk):
    release, signer, original_wheel, transfer, source_store, source_args, policy = installed_sdk
    _record_test_only_installed_release(source_store, release)
    source_verifier = InstalledB1SignedSdkVerifier(**source_args)
    offered = review_personal_b1_sdk_offer(
        verifier=source_verifier, transfer=transfer,
        verified_local_sdk_path=original_wheel,
        owner_private_copy_allowed=lambda _: True,
    )
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    now = datetime.now(timezone.utc)
    raw_catalog = publish_signed_owner_catalog(
        source_platform_id=transfer.source_platform_id,
        target_platform_id=transfer.target_platform_id,
        trusted_publisher_public_key=public, catalog_generation=3,
        catalog_revision=transfer.catalog_revision, selected_assets=[offered],
        sign_external=signer.sign,
        owner_hub_current=lambda: True,
        publisher_current=lambda _: True,
        time_now=lambda: now,
    )
    host = tmp_path / "new-recipient"
    host.mkdir()
    host.chmod(0o700)
    identity, current, state = provision(host)
    # Unlike the sender, the recipient has NO installed B1 release receipt.
    recipient_store = PlatformInstallationStore(
        tmp_path / "recipient-B1" / "install.db",
    )
    assert recipient_store.receipt_for_release(release.release_id) is None
    recipient_verifier = InstalledB1SignedSdkVerifier(
        **{**source_args, "installation": recipient_store},
    )
    received = original_wheel.read_bytes()
    assert sha256(received).hexdigest() == transfer.content_sha256
    receiver = ChunkedArtifactReceiver(
        tmp_path / "recipient-quarantine",
        max_bytes=transfer.size_bytes + 65536,
    )
    offset = 0
    for start in range(0, len(received), 1024 * 1024):
        chunk = received[start:start + 1024 * 1024]
        offset = receiver.append_chunk(
            transfer, offset=offset, chunk=chunk,
            chunk_sha256=sha256(chunk).hexdigest(),
            authorize=lambda _: True,
        )
    assert offset == transfer.size_bytes
    completed = receiver.finalize(
        transfer, authorize=lambda _: True, retain_scope=True,
    )
    assert completed.read_bytes() == received
    cache = OfflineArtifactCache(
        tmp_path / "recipient-cache",
        max_bytes=transfer.size_bytes + 65536,
    )
    options = dict(
        raw_signed_index=raw_catalog,
        expected_artifact_id=release.release_id,
        trusted_publisher_public_key=public,
        expected_publisher_key_sha256=sha256(public).hexdigest(),
        expected_catalog_generation=3,
        publisher_key_current=lambda _: True,
        transfer=transfer,
        receiver=receiver,
        cache=cache,
        open_enrolled_tls=lambda: (_ for _ in ()).throw(
            AssertionError("finished SDK must not dial a peer again")
        ),
        expected_peer_certificate_sha256="a" * 64,
        authorize_peer=lambda *_: True,
        publisher_current=lambda _: True,
        current_host_admit=lambda _: True,
        verify_independent_publisher=recipient_verifier,
        canonical_safe_state=state,
        approval_id="approval:personal-b1-sdk",
        start_offset=transfer.size_bytes,
        chunk_bytes=min(1024 * 1024, transfer.size_bytes),
        max_chunks=1,
        now=now,
        current_time=lambda: now,
    )
    return (
        options, received, offered, recipient_store, state, completed,
    )


def _approve_real_safe_cache_admission(options, state):
    transfer = options["transfer"]
    now = options["now"]
    scope = {
        "source": "ENROLLED_PEER",
        "source_platform_id": transfer.source_platform_id,
        "target_platform_id": transfer.target_platform_id,
        "content_digest": transfer.content_sha256,
        "manifest_digest": transfer.manifest_sha256,
        "artifact_kind": transfer.artifact_kind,
        "size_bytes": transfer.size_bytes,
        "generation": transfer.generation,
        "catalog_revision": transfer.catalog_revision,
        "signer_key_id": "test-release",
        "safe_state": str(Path(state).absolute()),
        "cache_root": str(options["cache"].root),
    }
    proof = ExecutionApproval(
        approval_id=options["approval_id"],
        capability=LIBRARY_PEER_CACHE_ADMIT,
        request_fingerprint=execution_fingerprint(
            LIBRARY_PEER_CACHE_ADMIT, scope,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(state), proof,
    )


def test_personal_signed_sdk_admitted_offline_only_after_one_use_owner_proof(
    signed_personal_sdk,
):
    options, received, offered, recipient_store, state, completed = signed_personal_sdk
    _approve_real_safe_cache_admission(options, state)
    result = acquire_from_independently_signed_index(**options)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["network_attempted"] is False
    assert result["reused_complete_quarantine"] is True
    assert result["owner_proof_consumed"] is True
    assert result["install_executed"] is False
    assert result["installed"] is None and result["active"] is None
    assert result["received_bytes"] == len(received)
    assert result["verified_bytes"] == len(received)
    assert result["selected_artifact_id"] == offered.artifact_id
    package = options["verify_independent_publisher"](
        options["transfer"], completed,
    )
    assert options["cache"].resolve(package).read_bytes() == received
    assert recipient_store.receipt_for_release(offered.artifact_id) is None
    assert not (
        options["receiver"].incoming
        / (options["transfer"].content_sha256 + ".scope")
    ).exists()


def test_personal_signed_sdk_missing_owner_approval_does_not_enter_b1(
    signed_personal_sdk,
):
    options, received, offered, recipient_store, state, completed = signed_personal_sdk
    with pytest.raises(PermissionError):
        acquire_from_independently_signed_index(**options)
    assert completed.read_bytes() == received
    assert (
        options["receiver"].incoming
        / (options["transfer"].content_sha256 + ".scope")
    ).is_file()
    assert not (
        options["cache"].root / options["transfer"].content_sha256
    ).exists()
    assert recipient_store.receipt_for_release(offered.artifact_id) is None
