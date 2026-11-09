"""D028 long-transfer recipient publisher renewal is signed and identity-locked.

All keys are disposable test-only. Source tests do not prove installed-host,
hardware, release signer or TLS enrollment acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkTransferRejected
from sofia.platform.ops.library_signed_selection import (
    verify_selected_signed_transfer, verify_renewed_recipient_offer,
)
from sofia.platform.ops.library_recipient_pipeline import (
    acquire_from_independently_signed_index,
)
from test.library_fixture_support import make_signed_offer_fixture


def _renew(env, sign, now, *, minutes=2):
    renewed = deepcopy(env)
    renewed["issued_at"] = (now + timedelta(seconds=15)).isoformat()
    renewed["expires_at"] = (now + timedelta(minutes=minutes)).isoformat()
    renewed["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=minutes - 1)
    ).isoformat()
    renewed["catalog"]["source"]["last_observed_at"] = (
        now + timedelta(seconds=15)
    ).isoformat()
    return renewed, sign(renewed)


def test_signed_renewal_retains_exact_content_recipient_signer_and_revision():
    env, sign, args = make_signed_offer_fixture()
    original = verify_selected_signed_transfer(**args)
    renewed, raw = _renew(env, sign, args["now"])
    next_offer = verify_renewed_recipient_offer(
        original=original, renewed_signed_index=raw,
        trusted_publisher_public_key=args["trusted_publisher_public_key"],
        expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
        expected_catalog_generation=args["expected_catalog_generation"],
        publisher_key_current=lambda _: True,
        now=args["now"] + timedelta(seconds=20),
    )
    assert next_offer.transfer == original.transfer
    assert next_offer.artifact_id == original.artifact_id
    assert next_offer.signer_key_id == original.signer_key_id
    assert next_offer.signature_receipt_ref == original.signature_receipt_ref
    assert next_offer.index.expires_at > original.index.expires_at
    assert next_offer.index.signed_index_sha256 == sha256(raw).hexdigest()


@pytest.mark.parametrize("change", (
    ("catalog", "items", 0, "content_digest", "f" * 64),
    ("catalog", "items", 0, "manifest_digest", "f" * 64),
    ("catalog", "items", 0, "signer_key_id", "unapproved-other-key"),
    ("catalog", "items", 0, "version", "2.0"),
    ("catalog", "items", 0, "signature_receipt_ref", "another-receipt"),
    ("catalog", "items", 0, "distribution_allowed", False),
    ("catalog", "items", 0, "license_distribution", "restricted"),
    ("catalog_revision", 8),
    ("catalog", "target_platform_id", "other-platform"),
))
def test_signed_renewal_denies_even_valid_signatures_for_changed_immutable_plan(change):
    env, sign, args = make_signed_offer_fixture()
    original = verify_selected_signed_transfer(**args)
    renewed, _raw = _renew(env, sign, args["now"])
    obj = renewed
    for key in change[:-2]:
        obj = obj[key]
    if len(change) == 2:
        renewed[change[0]] = change[1]
    else:
        obj[change[-2]] = change[-1]
    raw = sign(renewed)
    with pytest.raises((ChunkTransferRejected, PermissionError, ValueError)):
        verify_renewed_recipient_offer(
            original=original, renewed_signed_index=raw,
            trusted_publisher_public_key=args["trusted_publisher_public_key"],
            expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
            expected_catalog_generation=args["expected_catalog_generation"],
            publisher_key_current=lambda _: True,
            now=args["now"] + timedelta(seconds=20),
        )


def test_replayed_signed_page_never_extends_original_expiry():
    env, sign, args = make_signed_offer_fixture()
    original = verify_selected_signed_transfer(**args)
    with pytest.raises(ChunkTransferRejected, match="advance freshness"):
        verify_renewed_recipient_offer(
            original=original, renewed_signed_index=args["raw_signed_index"],
            trusted_publisher_public_key=args["trusted_publisher_public_key"],
            expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
            expected_catalog_generation=args["expected_catalog_generation"],
            publisher_key_current=lambda _: True, now=args["now"],
        )


def test_recipient_refreshes_only_near_deadline_and_prevents_revoked_package_before_admit(
    tmp_path, monkeypatch,
):
    from sofia.platform.ops.library_chunk_receiver import ChunkedArtifactReceiver
    from sofia.platform.ops.platform_install import OfflineArtifactCache
    import sofia.platform.ops.library_recipient_pipeline as pipeline

    env, sign, args = make_signed_offer_fixture()
    renewed, refreshed_bytes = _renew(env, sign, args["now"])
    clock = {"now": args["now"]}
    chosen = {"raw": args["raw_signed_index"], "calls": 0, "allowed": True}
    read_calls = []
    verified = []
    def supply():
        read_calls.append(True)
        return chosen["raw"]
    def fake_acquire(**kwargs):
        t = kwargs["transfer"]
        checked = kwargs["publisher_current"]
        assert checked(t) is True
        assert read_calls == []  # initial catalog still has >30s expiry?
        clock["now"] = args["now"] + timedelta(seconds=25)
        chosen["raw"] = refreshed_bytes
        assert checked(t) is True
        assert len(read_calls) == 1
        # The grant cannot be tricked into surviving a later publisher revoke.
        chosen["allowed"] = False
        assert checked(t) is False
        chosen["allowed"] = True
        verified.append(t)
        return {
            "cache_state": "RECEIVING", "received_bytes": 100,
            "verified_bytes": 0, "install_executed": False,
            "installed": None, "active": None,
        }
    monkeypatch.setattr(pipeline, "acquire_selected_signed_platform_asset", fake_acquire)
    receiver = ChunkedArtifactReceiver(tmp_path / "receiver", max_bytes=65536)
    cache = OfflineArtifactCache(tmp_path / "cache", max_bytes=65536)
    result = acquire_from_independently_signed_index(
        raw_signed_index=args["raw_signed_index"],
        expected_artifact_id=args["expected_artifact_id"],
        trusted_publisher_public_key=args["trusted_publisher_public_key"],
        expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
        expected_catalog_generation=args["expected_catalog_generation"],
        publisher_key_current=lambda _: chosen["allowed"],
        transfer=args["transfer"], receiver=receiver, cache=cache,
        open_enrolled_tls=lambda: None,
        expected_peer_certificate_sha256="a" * 64,
        authorize_peer=lambda *_: True,
        publisher_current=lambda _: True,
        current_host_admit=lambda _: True,
        verify_independent_publisher=lambda *_: None,
        canonical_safe_state=tmp_path / "SAFE.db",
        approval_id="unused-test-only",
        now=args["now"], current_time=lambda: clock["now"],
        read_current_signed_index=supply,
    )
    assert result["signed_index_sha256"] == sha256(refreshed_bytes).hexdigest()
    assert result["cache_state"] == "RECEIVING"
    assert len(verified) == 1


def test_recipient_unsigned_or_expired_renewal_never_returns_success(
    tmp_path, monkeypatch,
):
    from sofia.platform.ops.library_chunk_receiver import ChunkedArtifactReceiver
    from sofia.platform.ops.platform_install import OfflineArtifactCache
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    env, sign, args = make_signed_offer_fixture()
    clock = {"now": args["now"] + timedelta(seconds=40)}
    opened = []
    def must_deny(**kwargs):
        opened.append(True)
        assert kwargs["publisher_current"](kwargs["transfer"]) is False
        raise ChunkTransferRejected("publisher revoked or expired")
    monkeypatch.setattr(pipeline, "acquire_selected_signed_platform_asset", must_deny)
    with pytest.raises(ChunkTransferRejected, match="publisher"):
        acquire_from_independently_signed_index(
            raw_signed_index=args["raw_signed_index"],
            expected_artifact_id=args["expected_artifact_id"],
            trusted_publisher_public_key=args["trusted_publisher_public_key"],
            expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
            expected_catalog_generation=args["expected_catalog_generation"],
            publisher_key_current=lambda _: True,
            transfer=args["transfer"],
            receiver=ChunkedArtifactReceiver(tmp_path / "receiver", max_bytes=65536),
            cache=OfflineArtifactCache(tmp_path / "cache", max_bytes=65536),
            open_enrolled_tls=lambda: None,
            expected_peer_certificate_sha256="a" * 64,
            authorize_peer=lambda *_: True,
            publisher_current=lambda _: True,
            current_host_admit=lambda _: True,
            verify_independent_publisher=lambda *_: None,
            canonical_safe_state=tmp_path / "SAFE.db",
            approval_id="unused-test-only",
            now=args["now"], current_time=lambda: clock["now"],
            read_current_signed_index=lambda: b"unsigned-garbage",
        )
    assert len(opened) == 1



def test_three_signed_pages_advance_monotonically_without_replaying_older_offer():
    """Last accepted signed page, not just original, is the renewal floor."""
    env, sign, args = make_signed_offer_fixture()
    initial = verify_selected_signed_transfer(**args)
    start = args["now"]
    page1 = deepcopy(env)
    page1["issued_at"] = (start + timedelta(seconds=10)).isoformat()
    page1["expires_at"] = (start + timedelta(minutes=2)).isoformat()
    page1["catalog"]["catalog_fresh_until"] = (
        start + timedelta(minutes=1)
    ).isoformat()
    page1["catalog"]["source"]["last_observed_at"] = (
        start + timedelta(seconds=10)
    ).isoformat()
    raw1 = sign(page1)
    page2 = deepcopy(page1)
    page2["issued_at"] = (start + timedelta(seconds=30)).isoformat()
    page2["expires_at"] = (start + timedelta(minutes=3)).isoformat()
    page2["catalog"]["catalog_fresh_until"] = (
        start + timedelta(minutes=2)
    ).isoformat()
    page2["catalog"]["source"]["last_observed_at"] = (
        start + timedelta(seconds=30)
    ).isoformat()
    raw2 = sign(page2)
    def verify(previous, raw, now):
        return verify_renewed_recipient_offer(
            original=previous, renewed_signed_index=raw,
            trusted_publisher_public_key=args["trusted_publisher_public_key"],
            expected_publisher_key_sha256=args["expected_publisher_key_sha256"],
            expected_catalog_generation=args["expected_catalog_generation"],
            publisher_key_current=lambda _: True, now=now,
        )
    first = verify(initial, raw1, start + timedelta(seconds=20))
    second = verify(first, raw2, start + timedelta(seconds=40))
    assert second.index.expires_at > first.index.expires_at
    # The previously signed first renewal is still valid at +40 seconds,
    # but it is not newer than the second accepted page.
    with pytest.raises(ChunkTransferRejected, match="advance freshness"):
        verify(second, raw1, start + timedelta(seconds=40))
