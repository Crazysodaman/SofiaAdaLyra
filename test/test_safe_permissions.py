from datetime import datetime, timedelta, timezone

import pytest

from sofia.safe.permissions import (
    AdultPrivateAuthority,
    PermissionLevel,
    PermissionStore,
    PrivacyClass,
    capability_permission_policy,
)


def test_read_only_capability_is_level_one():
    policy = capability_permission_policy("hardware.inspect")
    assert policy.level is PermissionLevel.OBSERVE_READ
    assert policy.privacy is PrivacyClass.PRIVATE
    assert policy.standing_grant_allowed is False


def test_unknown_capability_fails_closed_as_protected():
    policy = capability_permission_policy("unknown.future.capability")
    assert policy.level is PermissionLevel.PROTECTED
    assert policy.standing_grant_allowed is False


def test_standing_grant_is_scoped_and_revocable(tmp_path):
    store = PermissionStore(tmp_path / "sofia.db")
    now = datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)
    grant = store.grant(
        "portainer.container.restart",
        scope={"container_id": "mealie"},
        now=now,
        grant_id="grant-mealie",
    )

    assert store.allows_standing(
        "portainer.container.restart",
        {"container_id": "mealie"},
        now=now,
    )
    assert not store.allows_standing(
        "portainer.container.restart",
        {"container_id": "homepage"},
        now=now,
    )

    revoked = store.revoke(
        grant.grant_id,
        now=now + timedelta(seconds=1),
    )
    assert revoked.revoked_at is not None
    assert not store.allows_standing(
        "portainer.container.restart",
        {"container_id": "mealie"},
        now=now + timedelta(seconds=2),
    )


def test_protected_capability_rejects_standing_grant(tmp_path):
    store = PermissionStore(tmp_path / "sofia.db")
    with pytest.raises(PermissionError, match="does not permit standing grants"):
        store.grant("local.host.reboot")


def test_only_sparks_can_change_permission_authority(tmp_path):
    store = PermissionStore(tmp_path / "sofia.db")
    with pytest.raises(PermissionError, match="belongs to Sparks"):
        store.grant(
            "local.service.restart",
            scope={"name": "SofiaAdaLyra"},
            granted_by="sofia",
        )
    with pytest.raises(PermissionError, match="belongs to Sparks"):
        store.set_private_adult_authority(
            private_chat=True,
            adult_chat=True,
            adult_avatar=True,
            adult_external_delivery=False,
            updated_by="sofia",
        )


def test_private_adult_defaults_fail_closed_for_adult_content(tmp_path):
    authority = PermissionStore(tmp_path / "sofia.db").private_adult_authority()
    assert authority.private_chat is True
    assert authority.adult_chat is False
    assert authority.adult_avatar is False
    assert authority.adult_external_delivery is False


def test_private_adult_authority_is_durable(tmp_path):
    path = tmp_path / "sofia.db"
    store = PermissionStore(path)
    updated = store.set_private_adult_authority(
        private_chat=True,
        adult_chat=True,
        adult_avatar=True,
        adult_external_delivery=False,
    )
    assert isinstance(updated, AdultPrivateAuthority)
    reloaded = PermissionStore(path).private_adult_authority()
    assert reloaded.adult_chat is True
    assert reloaded.adult_avatar is True
    assert reloaded.adult_external_delivery is False


def test_external_adult_delivery_cannot_be_enabled_without_adult_authority(tmp_path):
    store = PermissionStore(tmp_path / "sofia.db")
    with pytest.raises(ValueError, match="requires adult chat or adult avatar"):
        store.set_private_adult_authority(
            private_chat=True,
            adult_chat=False,
            adult_avatar=False,
            adult_external_delivery=True,
        )


def test_expired_grant_does_not_authorize(tmp_path):
    store = PermissionStore(tmp_path / "sofia.db")
    now = datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)
    store.grant(
        "local.service.restart",
        scope={"name": "SofiaAdaLyra"},
        now=now,
        expires_at=now + timedelta(minutes=5),
    )
    assert store.allows_standing(
        "local.service.restart",
        {"name": "SofiaAdaLyra"},
        now=now + timedelta(minutes=4),
    )
    assert not store.allows_standing(
        "local.service.restart",
        {"name": "SofiaAdaLyra"},
        now=now + timedelta(minutes=5),
    )
