"""Bind durable enrollment state into remote operation admission."""
from __future__ import annotations
from datetime import datetime
from sofia.distributed.endpoint_bound_gateway import EndpointBoundDurableGateway
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import NodeEndpoint
from sofia.distributed.operations import RemoteOperationDenied, RemoteOperationRequest, RemoteOperationResult


class IdentityBoundGateway:
    def __init__(self, identities: DurableNodeIdentityRegistry, gateway: EndpointBoundDurableGateway) -> None:
        if not isinstance(identities, DurableNodeIdentityRegistry):
            raise TypeError("identities must be a DurableNodeIdentityRegistry")
        if not isinstance(gateway, EndpointBoundDurableGateway):
            raise TypeError("gateway must be an EndpointBoundDurableGateway")
        self._identities=identities
        self._gateway=gateway

    def invoke(self, enrollment: NodeEnrollment, endpoint: NodeEndpoint,
               request: RemoteOperationRequest, *, now: datetime) -> RemoteOperationResult:
        active=self._identities.get(request.node_id)
        if active is None or active != enrollment:
            raise RemoteOperationDenied("node enrollment is absent, retired, or does not match durable identity")
        return self._gateway.invoke(enrollment, endpoint, request, now=now)
