"""22F contracts: permission must be exact, current, explicit and revocable."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.authorization import RemoteAuthorization, RemoteGrant

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_default_deny_and_exact_scope():
    auth = RemoteAuthorization()
    node, grant_id = uuid4(), uuid4()
    fields = dict(grant_id=grant_id, node_id=node, capability="system.inspect",
                  operation="summary", now=NOW)
    assert not auth.permits(**fields)
    grant = RemoteGrant(grant_id, node, "system.inspect", "summary", "Sparks",
                        NOW + timedelta(minutes=5))
    auth.add_approved_grant(grant)
    assert auth.permits(**fields)
    assert not auth.permits(**(fields | {"node_id": uuid4()}))
    assert not auth.permits(**(fields | {"capability": "network.inspect"}))
    assert not auth.permits(**(fields | {"operation": "restart"}))
    assert not auth.permits(**(fields | {"grant_id": uuid4()}))
    assert not auth.permits(**(fields | {"now": NOW + timedelta(minutes=5)}))
    auth.revoke(grant_id)
    assert not auth.permits(**fields)


def test_duplicate_approval_for_same_grant_refused():
    grant = RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", "operator",
                        NOW + timedelta(seconds=1))
    auth = RemoteAuthorization()
    auth.add_approved_grant(grant)
    with pytest.raises(ValueError, match="already exists"):
        auth.add_approved_grant(grant)


def test_human_approval_record_and_aware_time_required():
    with pytest.raises(ValueError, match="approver"):
        RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", " ", NOW)
    with pytest.raises(ValueError, match="timezone"):
        RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", "operator",
                    datetime(2026, 9, 20))
