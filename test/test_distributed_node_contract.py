"""Offline acceptance tests for the first Engineering Batch 22A slice."""
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport












@pytest.mark.parametrize("port", [0, 65536, True, "22"])
def test_invalid_endpoint_port_is_rejected(port):
    with pytest.raises(ValueError, match="port"):
        NodeEndpoint("artemis.lan", port, NodeTransport.SSH)


def test_contracts_are_immutable():
    node = DistributedNode(node_id=uuid4(), name="Artemis")
    with pytest.raises(FrozenInstanceError):
        node.name = "different"
