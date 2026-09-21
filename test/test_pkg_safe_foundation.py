from datetime import datetime, timedelta, timezone

import pytest

from sofia.package_foundations.safe import AuthorizationSnapshot


def test_unverified_snapshot_denies_by_default():
    assert not AuthorizationSnapshot().passes_preflight(datetime.now(timezone.utc))


def test_stop_and_revocation_override_claimed_grant():
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=5)
    assert not AuthorizationSnapshot(True, True, False, True, expiry).passes_preflight(now)
    assert not AuthorizationSnapshot(True, True, True, False, expiry).passes_preflight(now)
    assert AuthorizationSnapshot(True, True, False, False, expiry).passes_preflight(now)
    assert not AuthorizationSnapshot(True, True, False, False, expiry).passes_preflight(expiry)


def test_naive_expiry_rejected():
    with pytest.raises(ValueError):
        AuthorizationSnapshot(expires_at=datetime(2026, 1, 1))
