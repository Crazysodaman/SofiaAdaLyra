"""D028 peer fetch policy is deliberately owner-authenticated, never automatic."""
from __future__ import annotations

from sofia.platform.safe.permissions import (
    PermissionLevel, automatic_capabilities, capability_permission_policy,
    grantable_capabilities, is_explicitly_classified,
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
