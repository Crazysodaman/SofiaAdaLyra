"""Dummy Core for the Aegis SDK: request builder and response reader only.

No model, identity store, keys, memory, server, authentication, signing, or
direct module import. The Platform must independently bind a real Core session
in production. The AuthorityProjection below is a *provided projection*, not
self-granted authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sofia.sdk import (
    AuthorityProjection, ComponentEndpoint, ComponentKind,
    ComponentOutcome, ComponentRequestEnvelope, ComponentResponseEnvelope,
    SDK_PROTOCOL_VERSION,
)

from examples.sdk_reference_system.wire import payload_digest

PING_TYPE = "aegis.sdk.reference.ping.v1"
PING_RESULT_TYPE = "aegis.sdk.reference.ping.result.v1"


class ReferenceCore:
    """Sends one typed, no-effect module capability request via Platform."""

    def __init__(self, endpoint: ComponentEndpoint) -> None:
        if endpoint.kind is not ComponentKind.CORE:
            raise ValueError("reference Core must use a Core endpoint")
        self.endpoint = endpoint

    def build_ping(
        self, *, platform: ComponentEndpoint,
        projected_authority: AuthorityProjection,
        nonce: str, request_id: str, now: datetime,
    ) -> tuple[ComponentRequestEnvelope, dict[str, object]]:
        """Construct transport data, not a permission, connection or effect."""
        if platform.kind is not ComponentKind.PLATFORM:
            raise ValueError("destination must be a Platform")
        if self.endpoint.platform_instance_id != platform.platform_instance_id:
            raise ValueError("Core and Platform instance mismatch")
        if type(nonce) is not str or not 1 <= len(nonce) <= 64:
            raise ValueError("bounded ping nonce required")
        payload: dict[str, object] = {"nonce": nonce}
        request = ComponentRequestEnvelope(
            protocol=SDK_PROTOCOL_VERSION,
            request_id=request_id,
            correlation_id=request_id,
            idempotency_key=request_id,
            source=self.endpoint,
            destination=platform,
            authority=projected_authority,
            payload_type=PING_TYPE,
            payload_digest=payload_digest(payload),
            created_at=now,
            deadline=now + timedelta(seconds=30),
        )
        return request, payload

    def read_ping(
        self, request: ComponentRequestEnvelope,
        response: ComponentResponseEnvelope,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        """Validate reply correlation and *reported*, not verified, result."""
        if (
            response.request_id != request.request_id
            or response.correlation_id != request.correlation_id
            or response.responder != request.destination
            or response.protocol != request.protocol
        ):
            raise ValueError("reference response is not bound to request")
        if response.payload_digest is None:
            if payload is not None:
                raise ValueError("unexpected response payload")
        elif (
            response.payload_type != PING_RESULT_TYPE
            or payload is None
            or payload_digest(payload) != response.payload_digest
        ):
            raise ValueError("reference response digest/schema mismatch")
        if response.outcome is ComponentOutcome.SUCCEEDED_VERIFIED:
            raise ValueError("a dummy module cannot prove verified completion")
        return {
            "outcome": response.outcome.value,
            "reported_result": payload,
            "verified": False,
        }
