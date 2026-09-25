"""Production admission composition for distributed operations.

This composes durable identity, exact endpoint policy, authorization/replay,
and the injected authenticated transport. It does not implement a transport.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path

from sofia.distributed.durable import DurableRemoteAuthorization, DurableRemoteLedger
from sofia.distributed.endpoint_bound_gateway import EndpointBoundDurableGateway
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_bound_gateway import IdentityBoundGateway
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import NodeEndpoint
from sofia.distributed.operations import RemoteOperationRequest, RemoteOperationResult, RemoteTransport


class DurableRemoteControl:
    def __init__(self, *, transport: RemoteTransport, identity_path: Path | str,
                 endpoint_path: Path | str, authorization_path: Path | str,
                 ledger_path: Path | str, max_inventory_age: timedelta) -> None:
        self.identities=DurableNodeIdentityRegistry(identity_path)
        self.endpoints=DurableEndpointPolicy(endpoint_path)
        self.authorization=DurableRemoteAuthorization(authorization_path)
        self.ledger=DurableRemoteLedger(ledger_path)
        endpoint_gateway=EndpointBoundDurableGateway(
            transport,self.authorization,self.ledger,self.endpoints,max_inventory_age=max_inventory_age)
        self._gateway=IdentityBoundGateway(self.identities,endpoint_gateway)

    def invoke(self, enrollment: NodeEnrollment, endpoint: NodeEndpoint,
               request: RemoteOperationRequest, *, now: datetime) -> RemoteOperationResult:
        return self._gateway.invoke(enrollment,endpoint,request,now=now)

    def close(self) -> None:
        self.identities.close(); self.endpoints.close(); self.authorization.close(); self.ledger.close()
