"""22F contracts: permission must be exact, current, explicit and revocable."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.authorization import (
    RemoteGrant,
    remote_operation_is_read_only,
)
from test.distributed_support import remote_authorization

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_default_deny_and_exact_scope(remote_authorization):
    auth = remote_authorization
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


def test_duplicate_approval_for_same_grant_refused(remote_authorization):
    grant = RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", "operator",
                        NOW + timedelta(seconds=1))
    auth = remote_authorization
    auth.add_approved_grant(grant)
    with pytest.raises(ValueError, match="already exists"):
        auth.add_approved_grant(grant)


def test_human_approval_record_and_aware_time_required():
    with pytest.raises(ValueError, match="approving authority"):
        RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", " ", NOW)
    with pytest.raises(ValueError, match="timezone"):
        RemoteGrant(uuid4(), uuid4(), "system.inspect", "summary", "operator",
                    datetime(2026, 9, 20))


@pytest.mark.parametrize(
    "operation",
    ("list", "get", "stats", "info", "summary", "images", "volumes", "networks", "stacks"),
)
def test_remote_docker_inspection_operations_are_level_one_reads(operation):
    assert remote_operation_is_read_only("container.inspect", operation) is True


def test_remote_container_restart_is_not_read_only():
    assert remote_operation_is_read_only(
        "container.manage",
        "restart",
    ) is False


def test_active_grants_lists_current_grants_across_nodes(tmp_path):
    from datetime import timedelta
    from uuid import uuid4

    from sofia.distributed.authorization import RemoteGrant
    from sofia.distributed.durable import DurableRemoteAuthorization

    now = datetime.now(timezone.utc)
    store = DurableRemoteAuthorization(tmp_path / "sofia.db")
    try:
        first = RemoteGrant(
            uuid4(), uuid4(), "service.manage", "restart",
            "Sparks", now + timedelta(hours=1),
        )
        second = RemoteGrant(
            uuid4(), uuid4(), "container.manage", "restart",
            "Sparks", now + timedelta(hours=1),
        )
        store.add_approved_grant(first)
        store.add_approved_grant(second)
        grants = store.active_grants(now=now)
        assert {item.grant_id for item in grants} == {
            first.grant_id,
            second.grant_id,
        }
    finally:
        store.close()
