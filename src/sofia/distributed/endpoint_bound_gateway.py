"""Endpoint-bound durable gateway for PKG-NET.

This wrapper requires the caller to present the exact endpoint being used for
the operation and checks it against durable human-approved policy before the
existing durable authorization/replay gateway is allowed to proceed.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sofia.distributed.durable import (
    DurableDistributedGateway,
    DurableRemoteAuthorization,
    DurableRemoteLedger,
)
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import NodeEndpoint
from sofia.distributed.operations import (
    RemoteOperationDenied,
    RemoteOperationRequest,
    RemoteOperationResult,
    RemoteTransport,
)


class EndpointBoundDurableGateway:
    def __init__(
        self,
        transport: RemoteTransport,
        authorization: DurableRemoteAuthorization,
        ledger: DurableRemoteLedger,
        endpoint_policy: DurableEndpointPolicy,
        *,
        max_inventory_age: timedelta,
    ) -> None:
        if not isinstance(endpoint_policy, DurableEndpointPolicy):
            raise TypeError("endpoint_policy must be a DurableEndpointPolicy")
        self._endpoint_policy = endpoint_policy
        self._gateway = DurableDistributedGateway(
            transport,
            authorization,
            ledger,
            max_inventory_age=max_inventory_age,
        )

    def invoke(
        self,
        enrollment: NodeEnrollment,
        endpoint: NodeEndpoint,
        request: RemoteOperationRequest,
        *,
        now: datetime,
    ) -> RemoteOperationResult:
        if not isinstance(enrollment, NodeEnrollment):
            raise TypeError("enrollment must be a NodeEnrollment")
        if not isinstance(endpoint, NodeEndpoint):
            raise TypeError("endpoint must be a NodeEndpoint")
        if not isinstance(request, RemoteOperationRequest):
            raise TypeError("request must be a RemoteOperationRequest")
        node_id = enrollment.node.node_id
        if request.node_id != node_id:
            raise RemoteOperationDenied("request node does not match enrollment")
        if not self._endpoint_policy.permits(node_id, endpoint):
            raise RemoteOperationDenied("endpoint is not durably approved for node")
        return self._gateway.invoke(enrollment, request, now=now)
