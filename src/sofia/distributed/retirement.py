"""Coordinated local retirement of a distributed node.

Retirement removes the node from active identity and endpoint admission. It
does not delete audit history or reuse identity records.
"""
from __future__ import annotations
from uuid import UUID
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry


class NodeRetirementCoordinator:
    def __init__(self, identities: DurableNodeIdentityRegistry, endpoints: DurableEndpointPolicy) -> None:
        if not isinstance(identities, DurableNodeIdentityRegistry):
            raise TypeError("identities must be DurableNodeIdentityRegistry")
        if not isinstance(endpoints, DurableEndpointPolicy):
            raise TypeError("endpoints must be DurableEndpointPolicy")
        self._identities=identities; self._endpoints=endpoints

    def retire(self, node_id: UUID) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        self._endpoints.revoke(node_id)
        self._identities.retire(node_id)
