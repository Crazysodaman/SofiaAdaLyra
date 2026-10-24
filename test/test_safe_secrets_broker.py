from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.safe.secrets_broker import PlatformSecretsBroker
from sofia.core.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 23, 3, tzinfo=timezone.utc)
OWNER = PrincipalContext(
    "principal:sparks", "audience:desktop", AudienceKind.PRIVATE,
)


class MemoryProtectedStore:
    def __init__(self):
        self.values = {}

    def set(self, key, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)

    def clear(self, key):
        return self.values.pop(key, None) is not None


def broker(path, store, *, allowed=True):
    return PlatformSecretsBroker(
        path, value_store=store,
        authorizer=lambda principal, module, ref, purpose, authority, now: (
            allowed and authority == "approval:secret"
        ),
    )


def create(service):
    return service.create(
        secret_ref="secret:research-api", value="super-secret-value",
        owner_module="org.sofia.research", audience_id="audience:desktop",
        allowed_modules=("org.sofia.research", "org.sofia.browser"),
        principal=OWNER, authority_ref="approval:secret", now=NOW,
    )


def test_scoped_secret_disclosure_is_one_use_and_redacted(canonical_state_path):
    store = MemoryProtectedStore()
    service = broker(canonical_state_path, store)
    metadata = create(service)
    assert b"super-secret-value" not in canonical_state_path.read_bytes()
    lease = service.disclose(
        secret_ref=metadata.secret_ref, caller_module="org.sofia.browser",
        principal=OWNER, authority_ref="approval:secret", purpose="web request",
        now=NOW,
    )
    assert "super-secret-value" not in repr(lease)
    assert "audience:desktop" not in repr(metadata)
    assert lease.take(now=NOW) == "super-secret-value"
    with pytest.raises(PermissionError, match="already consumed"):
        lease.take(now=NOW)


def test_wrong_audience_module_or_authority_cannot_disclose(canonical_state_path):
    store = MemoryProtectedStore()
    service = broker(canonical_state_path, store)
    create(service)
    wrong = PrincipalContext(
        "principal:sparks", "audience:discord", AudienceKind.PRIVATE,
    )
    with pytest.raises(PermissionError, match="audience"):
        service.disclose(
            secret_ref="secret:research-api", caller_module="org.sofia.browser",
            principal=wrong, authority_ref="approval:secret", purpose="request", now=NOW,
        )
    with pytest.raises(PermissionError, match="allowlist"):
        service.disclose(
            secret_ref="secret:research-api", caller_module="org.sofia.avatar",
            principal=OWNER, authority_ref="approval:secret", purpose="request", now=NOW,
        )
    with pytest.raises(PermissionError, match="authorized"):
        service.disclose(
            secret_ref="secret:research-api", caller_module="org.sofia.browser",
            principal=OWNER, authority_ref="forged", purpose="request", now=NOW,
        )


def test_rotation_is_versioned_crash_safe_and_restart_visible(canonical_state_path):
    store = MemoryProtectedStore()
    service = broker(canonical_state_path, store)
    original = create(service)
    plan = service.plan_rotation(original.secret_ref)
    assert plan.executable is False
    rotated = service.rotate(
        secret_ref=original.secret_ref, value="replacement", expected_version=1,
        principal=OWNER, authority_ref="approval:secret", now=NOW + timedelta(seconds=1),
    )
    assert rotated.version == 2
    restarted = broker(canonical_state_path, store)
    lease = restarted.disclose(
        secret_ref=original.secret_ref, caller_module="org.sofia.research",
        principal=OWNER, authority_ref="approval:secret", purpose="provider login",
        now=NOW + timedelta(seconds=2),
    )
    assert lease.take(now=NOW + timedelta(seconds=2)) == "replacement"
    with pytest.raises(RuntimeError, match="revision changed"):
        restarted.rotate(
            secret_ref=original.secret_ref, value="stale", expected_version=1,
            principal=OWNER, authority_ref="approval:secret",
            now=NOW + timedelta(seconds=3),
        )
    assert "stale" not in store.values.values()


def test_revocation_commits_before_blob_cleanup_and_blocks_restart(canonical_state_path):
    class CleanupFailureStore(MemoryProtectedStore):
        def clear(self, key):
            raise OSError("simulated protected-store cleanup failure")

    store = CleanupFailureStore()
    service = broker(canonical_state_path, store)
    create(service)
    with pytest.raises(OSError, match="cleanup failure"):
        service.revoke(
            secret_ref="secret:research-api", principal=OWNER,
            authority_ref="approval:secret", now=NOW,
        )
    restarted = broker(canonical_state_path, store)
    assert restarted.inspect("secret:research-api").revoked_at == NOW
    with pytest.raises(PermissionError, match="revoked"):
        restarted.disclose(
            secret_ref="secret:research-api", caller_module="org.sofia.research",
            principal=OWNER, authority_ref="approval:secret", purpose="request", now=NOW,
        )


def test_expired_lease_erases_value(canonical_state_path):
    store = MemoryProtectedStore()
    service = broker(canonical_state_path, store)
    create(service)
    lease = service.disclose(
        secret_ref="secret:research-api", caller_module="org.sofia.research",
        principal=OWNER, authority_ref="approval:secret", purpose="request",
        now=NOW, ttl=timedelta(seconds=1),
    )
    with pytest.raises(PermissionError, match="expired"):
        lease.take(now=NOW + timedelta(seconds=1))
    assert "super-secret-value" not in repr(lease)
