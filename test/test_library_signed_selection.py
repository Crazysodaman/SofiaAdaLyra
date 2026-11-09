"""D028 signed index -> exact selected immutable transfer binding tests."""
from __future__ import annotations

from hashlib import sha256

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from sofia.platform.ops.library_signed_selection import verify_selected_signed_transfer
from test.test_library_signed_index import signed_catalog as signed_catalog_fixture


@pytest.fixture
def signed_offer(signed_catalog_fixture):
    env, sign, kwargs = signed_catalog_fixture
    data = b"independent-verified-sdk-asset" * 12
    transfer = PinnedChunkTransfer(
        source_platform_id="primary-library",
        target_platform_id="enrolled-recipient",
        content_sha256=sha256(data).hexdigest(),
        size_bytes=len(data), generation=8,
        manifest_sha256="b" * 64,
        catalog_revision=7, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    row = dict(
        artifact_id="sdk.release.1", kind="sdk", version="1.0",
        revision=7, manifest_digest=transfer.manifest_sha256,
        content_digest=transfer.content_sha256, size_bytes=transfer.size_bytes,
        publisher="official-owner-approved-publisher",
        signer_key_id="independently-trusted-release-key",
        signature_scheme="ed25519", signature_receipt_ref="signed-receipt-123",
        target_os_arch="debian12-x86_64", sdk_range=">=1.0",
        abi_range=">=1.0", license_distribution="permitted",
        data_class="public", distribution_allowed=True,
    )
    env["catalog"]["items"] = [row]
    args = dict(
        raw_signed_index=sign(), transfer=transfer,
        expected_artifact_id=row["artifact_id"],
        trusted_publisher_public_key=kwargs["trusted_publisher_public_key"],
        expected_publisher_key_sha256=kwargs["expected_publisher_key_sha256"],
        expected_catalog_generation=3, now=kwargs["now"],
        publisher_key_current=lambda _: True,
    )
    return env, sign, args


def test_signed_selection_binds_immutable_bytes_and_recipient(signed_offer):
    _env, _sign, args = signed_offer
    selection = verify_selected_signed_transfer(**args)
    assert selection.transfer == args["transfer"]
    assert selection.artifact_id == "sdk.release.1"
    assert selection.signer_key_id == "independently-trusted-release-key"
    assert selection.still_matches()
    selection.index.catalog["items"][0]["size_bytes"] += 1
    assert not selection.still_matches()


def test_signed_selection_refuses_changed_content_digest(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"][0]["content_digest"] = "0" * 64
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="differs"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_refuses_redistribution_restricted_asset(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"][0]["distribution_allowed"] = False
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="differs"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_rejects_ambiguous_offer(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"].append(dict(env["catalog"]["items"][0]))
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="ambiguous"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_rejects_expired_or_untrusted_index(signed_offer):
    _env, _sign, args = signed_offer
    with pytest.raises(SignedLibraryIndexRejected, match="revoked"):
        verify_selected_signed_transfer(
            **{**args, "publisher_key_current": lambda _: False},
        )


def test_signed_selection_rejects_wrong_owner_selected_id(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["source"]["source_id"] = "untrusted-sender"
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="source"):
        verify_selected_signed_transfer(**args)
