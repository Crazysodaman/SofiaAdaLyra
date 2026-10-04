from uuid import uuid4

import pytest

from sofia.distributed.model import ApprovedEndpoint
from sofia.distributed.model import NodeEndpoint, NodeTransport


def endpoint(host="artemis.local", port=443, transport=NodeTransport.HTTPS):
    return NodeEndpoint(hostname=host, port=port, transport=transport)












@pytest.mark.parametrize("approver", ["", "   ", None])
def test_human_approver_required(approver):
    with pytest.raises((TypeError, ValueError)):
        ApprovedEndpoint(uuid4(), endpoint(), approver)
