from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.distributed.identity import NodeEnrollment, fingerprint_public_key
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode


def enrollment(node_id=None, key=b"artemis-key"):
    return NodeEnrollment(
        DistributedNode(node_id or uuid4(), "Artemis"),
        fingerprint_public_key(key),
        datetime.now(timezone.utc),
        "Sparks",
    )


def test_enrollment_survives_restart(tmp_path):
    path = tmp_path / "net.db"
    record = enrollment()
    first = DurableNodeIdentityRegistry(path)
    first.enroll(record); first.close()
    reopened = DurableNodeIdentityRegistry(path)
    assert reopened.get(record.node.node_id) == record
    reopened.close()


def test_retirement_survives_restart(tmp_path):
    path = tmp_path / "net.db"
    record = enrollment()
    first = DurableNodeIdentityRegistry(path)
    first.enroll(record); first.retire(record.node.node_id); first.close()
    reopened = DurableNodeIdentityRegistry(path)
    assert reopened.get(record.node.node_id) is None
    reopened.close()


def test_same_node_id_cannot_silently_rotate_key(tmp_path):
    store = DurableNodeIdentityRegistry(tmp_path / "net.db")
    node_id = uuid4()
    store.enroll(enrollment(node_id, b"old"))
    with pytest.raises(ValueError):
        store.enroll(enrollment(node_id, b"new"))
    store.close()


def test_same_pin_cannot_identify_two_nodes(tmp_path):
    store = DurableNodeIdentityRegistry(tmp_path / "net.db")
    store.enroll(enrollment(key=b"same"))
    with pytest.raises(ValueError):
        store.enroll(enrollment(key=b"same"))
    store.close()


def test_retired_identity_is_not_reused(tmp_path):
    store = DurableNodeIdentityRegistry(tmp_path / "net.db")
    record = enrollment()
    store.enroll(record); store.retire(record.node.node_id)
    with pytest.raises(ValueError):
        store.enroll(enrollment(record.node.node_id, b"replacement"))
    store.close()


def test_in_memory_database_rejected():
    with pytest.raises(ValueError):
        DurableNodeIdentityRegistry(":memory:")
