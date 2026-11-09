"""D028 peer fetch policy is deliberately owner-authenticated, never automatic."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.safe.permissions import (
    PermissionLevel, automatic_capabilities, capability_permission_policy,
    grantable_capabilities, is_explicitly_classified, LIBRARY_PEER_SCOPE,
    PermissionStore, _validate_library_peer_standing_scope,
)


def test_peer_fetch_can_only_use_fresh_owner_approved_scoped_grant():
    capability = "library.peer.fetch"
    assert is_explicitly_classified(capability)
    policy = capability_permission_policy(capability)
    assert policy.level == PermissionLevel.REVERSIBLE_SCOPED
    assert policy.standing_grant_allowed is True
    assert capability in grantable_capabilities()
    assert capability not in automatic_capabilities()


def test_verified_cache_and_install_effects_remain_protected():
    for capability in (
        "platform.library.cache_admit_verified_seed",
        "platform.activate_release",
        "platform.rollback_release",
    ):
        policy = capability_permission_policy(capability)
        assert policy.level >= PermissionLevel.PROTECTED
        assert not policy.standing_grant_allowed
        assert capability not in automatic_capabilities()



@pytest.fixture
def exact_scope():
    return {
        "source_platform_id": "primary-library",
        "target_platform_id": "recipient-platform",
        "certificate_sha256": "a" * 64,
        "manifest_digest": "b" * 64,
        "content_digest": "c" * 64,
        "artifact_kind": "sdk",
        "catalog_revision": 7,
        "data_class": "public",
        "license_distribution": "permitted",
        "max_chunk_bytes": 1024,
        "max_total_bytes": 32768,
    }


def test_owner_peer_scope_requires_exact_fields_and_bounded_expiry(exact_scope):
    now = datetime.now(timezone.utc)
    assert set(exact_scope) == LIBRARY_PEER_SCOPE
    _validate_library_peer_standing_scope(
        exact_scope, moment=now, expires_at=now + timedelta(minutes=5),
    )
    for override in (
        {"license_distribution": "restricted"},
        {"data_class": "private"},
        {"max_chunk_bytes": 1024 * 1024 + 1},
        {"max_chunk_bytes": True},
        {"max_total_bytes": 0},
        {"catalog_revision": 0},
        {"source_platform_id": exact_scope["target_platform_id"]},
        {"certificate_sha256": "not-a-digest"},
        {"manifest_digest": "F" * 64},
        {"artifact_kind": "arbitrary"},
    ):
        scope = {**exact_scope, **override}
        with pytest.raises(PermissionError):
            _validate_library_peer_standing_scope(
                scope, moment=now, expires_at=now + timedelta(minutes=5),
            )
    for expiry in (None, now, now + timedelta(hours=2)):
        with pytest.raises(PermissionError, match="expiry"):
            _validate_library_peer_standing_scope(
                exact_scope, moment=now, expires_at=expiry,
            )


def test_owner_peer_grant_requires_actual_safe_owner_proof(
    canonical_state_path, exact_scope,
):
    now = datetime.now(timezone.utc)
    grants = PermissionStore(canonical_state_path)
    with pytest.raises(PermissionError, match="authenticated owner approval"):
        grants.grant(
            "library.peer.fetch", scope=exact_scope,
            expires_at=now + timedelta(minutes=5), now=now,
            granted_by="person:sparks",
        )
    assert not any(
        grant.capability == "library.peer.fetch"
        for grant in grants.grants(active_only=False)
    )


def test_invalid_peer_scope_denied_before_owner_proof(
    canonical_state_path, exact_scope,
):
    store = PermissionStore(canonical_state_path)
    invalid = {**exact_scope, "max_chunk_bytes": 1024 * 1024 + 1}
    with pytest.raises(PermissionError, match="bounded transfer"):
        store.grant(
            "library.peer.fetch", scope=invalid,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            approval_id="not-a-real-owner-proof",
        )
    assert not any(
        grant.capability == "library.peer.fetch"
        for grant in store.grants(active_only=False)
    )
