from datetime import datetime, timedelta, timezone

import pytest

from sofia.package_foundations.net import RemoteGrant


def test_grant_requires_matching_node_capability_and_time():
    now = datetime.now(timezone.utc)
    grant = RemoteGrant('artemis', 'inspect', now + timedelta(minutes=5))
    assert grant.permits(node_id='artemis', capability='inspect', now=now)
    assert not grant.permits(node_id='other', capability='inspect', now=now)
    assert not grant.permits(node_id='artemis', capability='execute', now=now)
    assert not grant.permits(node_id='artemis', capability='inspect', now=grant.expires_at)


def test_revocation_denies_even_before_expiry():
    now = datetime.now(timezone.utc)
    assert not RemoteGrant('artemis', 'inspect', now + timedelta(days=1), True).permits(
        node_id='artemis', capability='inspect', now=now)


def test_naive_expiry_is_rejected():
    with pytest.raises(ValueError):
        RemoteGrant('artemis', 'inspect', datetime(2026, 1, 1))
