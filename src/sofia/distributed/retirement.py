"""Coordinated local retirement of a distributed node.

Retirement removes identity, endpoint admission, and active grants while
preserving durable audit/history records.
"""
from __future__ import annotations
from uuid import UUID
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry


class NodeRetirementCoordinator:
    def __init__(self, identities: DurableNodeIdentityRegistry, endpoints: DurableEndpointPolicy,
                 authorization: DurableRemoteAuthorization | None = None) -> None:
        if not isinstance(identities, DurableNodeIdentityRegistry):
            raise TypeError("identities must be DurableNodeIdentityRegistry")
        if not isinstance(endpoints, DurableEndpointPolicy):
            raise TypeError("endpoints must be DurableEndpointPolicy")
        if authorization is not None and not isinstance(authorization, DurableRemoteAuthorization):
            raise TypeError("authorization must be DurableRemoteAuthorization or None")
        self._identities=identities; self._endpoints=endpoints; self._authorization=authorization

    def retire(self, node_id: UUID) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        if self._authorization is not None:
            self._authorization.revoke_node(node_id)
        self._endpoints.revoke(node_id)
        self._identities.retire(node_id)
