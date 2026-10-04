"""Batch 22B offline node enrollment and key-pin contract tests."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

import pytest

from sofia.distributed.model import NodeEnrollment
from sofia.distributed.model import DistributedNode


def enrollment(node_id=None, key=b"node-A-public-key"):
    return NodeEnrollment(
        node=DistributedNode(node_id=node_id or uuid4(), name="Artemis"),
        public_key_sha256=sha256(key).hexdigest(),
        provisioned_at=datetime.now(timezone.utc),
        recorded_by="operator inventory",
    )














@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "z" * 64, 5, None])
def test_invalid_pin_fails_closed(bad):
    with pytest.raises((TypeError, ValueError)):
        NodeEnrollment(DistributedNode(uuid4(), "Artemis"), bad,
                       datetime.now(timezone.utc), "operator")


def test_naive_provisioning_timestamp_fails_closed():
    with pytest.raises(ValueError, match="timezone-aware"):
        NodeEnrollment(DistributedNode(uuid4(), "Artemis"), "a" * 64,
                       datetime(2026, 9, 20), "operator")


def test_enrollment_is_immutable_and_does_not_expose_authority():
    record = enrollment()
    with pytest.raises(FrozenInstanceError):
        record.public_key_sha256 = "b" * 64
    assert not hasattr(record, "authorized")
