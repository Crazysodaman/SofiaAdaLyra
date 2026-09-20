"""Batch 22B offline node enrollment and key-pin contract tests."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

import pytest

from sofia.distributed.identity import (
    NodeEnrollment,
    NodeIdentityRegistry,
    fingerprint_public_key,
)
from sofia.distributed.model import DistributedNode


def enrollment(node_id=None, key=b"node-A-public-key"):
    return NodeEnrollment(
        node=DistributedNode(node_id=node_id or uuid4(), name="Artemis"),
        public_key_sha256=fingerprint_public_key(key),
        provisioned_at=datetime.now(timezone.utc),
        recorded_by="operator inventory",
    )


def test_hash_is_exact_sha256_of_public_key_bytes():
    assert fingerprint_public_key(b"abc") == sha256(b"abc").hexdigest()


@pytest.mark.parametrize("bad", [None, b"", "key", bytearray(b"key")])
def test_empty_or_nonimmutable_key_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        fingerprint_public_key(bad)


def test_enrollment_matches_only_the_pinned_public_key():
    record = enrollment()
    registry = NodeIdentityRegistry()
    registry.enroll(record)
    assert registry.get(record.node.node_id) is record
    assert registry.matches_pinned_public_key(record.node.node_id, b"node-A-public-key")
    assert not registry.matches_pinned_public_key(record.node.node_id, b"other")
    assert not registry.matches_pinned_public_key(uuid4(), b"node-A-public-key")


def test_display_name_does_not_determine_node_identity():
    a = enrollment()
    b = enrollment(key=b"second-public-key")
    assert a.node.name == b.node.name
    assert a.node.node_id != b.node.node_id
    registry = NodeIdentityRegistry()
    registry.enroll(a)
    registry.enroll(b)
    assert registry.get(a.node.node_id) is a
    assert registry.get(b.node.node_id) is b


def test_implicit_reenrollment_or_key_rotation_is_rejected():
    same_id = uuid4()
    registry = NodeIdentityRegistry()
    registry.enroll(enrollment(node_id=same_id))
    with pytest.raises(ValueError, match="already enrolled"):
        registry.enroll(enrollment(node_id=same_id, key=b"rotated"))


def test_same_key_cannot_be_bound_to_two_node_ids():
    registry = NodeIdentityRegistry()
    registry.enroll(enrollment())
    with pytest.raises(ValueError, match="already bound"):
        registry.enroll(enrollment())


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
    assert not hasattr(NodeIdentityRegistry(), "execute")


def test_unknown_node_returns_no_record():
    assert NodeIdentityRegistry().get(uuid4()) is None
