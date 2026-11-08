"""Dummy Aegis Platform for the SDK, NOT a real service or authority.

Demonstrates a Platform-owned capability registry, per-Core synthetic session
binding, separate grants, STOP, module hot-unplug, request deadlines and SDK
response envelopes. No sockets, trusted OS authentication, canonical DB,
secrets, signatures, managed workers or production owner approvals exist here.
This in-memory fixture MUST NOT be used as a real Platform gateway.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sofia.sdk import (
    AuthorityProjection, ComponentEndpoint, ComponentKind,
    ComponentOutcome, ComponentRequestEnvelope, ComponentResponseEnvelope,
    SDK_PROTOCOL_VERSION,
)
from sofia.platform.capability import CapabilitySystem
from sofia.platform.capability.model import (
    CapabilityDispatchContext, CapabilityRequest, CapabilityResultKind,
)
from examples.sdk_reference_module.reference import CAPABILITY_ID, ReferenceModule
from examples.sdk_reference_system.wire import (
    PING_TYPE, PING_RESULT_TYPE, payload_digest,
)


@dataclass(eq=False, frozen=True, slots=True)
class ReferenceSession:
    """Opaque in-process test handle, NOT a credential or authenticated IPC."""

    source: ComponentEndpoint
    authority: AuthorityProjection


class ReferencePlatform:
    """Toy control plane using real SDK envelopes and CapabilitySystem."""

    def __init__(self, endpoint: ComponentEndpoint) -> None:
        if endpoint.kind is not ComponentKind.PLATFORM:
            raise ValueError("reference Platform must have PLATFORM kind")
        self.endpoint = endpoint
        self._sessions: set[ReferenceSession] = set()
        self._grants: set[ReferenceSession] = set()
        self._next_session = 0
        self._seen_request_ids: set[str] = set()
        self._stopped = False
        self._module_regs = None
        self._capabilities = CapabilitySystem(
            authorization_checker=self._test_authorization
        )

    def _test_authorization(self, request: CapabilityRequest) -> bool:
        context = request.dispatch_context
        if context is None or self._stopped:
            return False
        return any(
            session in self._grants
            and session in self._sessions
            and session.authority.authority_ref == context.goal_id
            and session.authority.principal_id == context.principal_id
            and session.authority.audience_id == context.audience
            and context.capability == CAPABILITY_ID
            for session in self._sessions
        )

    def open_test_session(
        self, core: ComponentEndpoint, *, now: datetime,
        audience: str = "audience:example", lifetime_seconds: int = 120,
    ) -> ReferenceSession:
        """Demo only: creating a test session is NOT authenticating a Core."""
        if core.kind is not ComponentKind.CORE:
            raise ValueError("only Core endpoint can open this demo session")
        if core.platform_instance_id != self.endpoint.platform_instance_id:
            raise ValueError("source belongs to another Platform")
        if type(lifetime_seconds) is not int or not 31 <= lifetime_seconds <= 300:
            raise ValueError("test session lifetime must be 31..300 seconds")
        self._next_session += 1
        authority = AuthorityProjection(
            principal_id=core.core_identity_id or "",
            audience_id=audience,
            audience_kind="system",
            authority_ref=f"test:session:{self._next_session}",
            scopes=(CAPABILITY_ID,),
            expires_at=now + timedelta(seconds=lifetime_seconds),
        )
        session = ReferenceSession(source=core, authority=authority)
        self._sessions.add(session)
        return session

    def test_only_grant(self, session: ReferenceSession) -> None:
        """Not an approval API; in production SAFE grants come from owner."""
        if session not in self._sessions:
            raise PermissionError("unrecognized test session")
        self._grants.add(session)

    def test_only_revoke(self, session: ReferenceSession) -> None:
        self._grants.discard(session)

    def close_test_session(self, session: ReferenceSession) -> None:
        self._grants.discard(session)
        self._sessions.discard(session)

    def test_only_stop(self, active: bool) -> None:
        if type(active) is not bool:
            raise TypeError("stop must be boolean")
        self._stopped = active

    def plug_reference_module(self) -> None:
        """Register reviewed sample capability. No real installation occurs."""
        if self._module_regs is not None:
            raise RuntimeError("reference module already plugged")
        registrations = ReferenceModule().capability_registrations()
        self._capabilities.register_batch(registrations)
        self._module_regs = registrations

    def unplug_reference_module(self) -> None:
        """Withdraw only this module's exact registered capability batch."""
        if self._module_regs is None:
            return
        self._capabilities.unregister_batch(self._module_regs)
        self._module_regs = None

    @property
    def available_capabilities(self) -> tuple[str, ...]:
        return self._capabilities.capability_names()

    def _response(
        self, request: ComponentRequestEnvelope, now: datetime,
        outcome: ComponentOutcome, payload: dict[str, object] | None = None,
    ) -> tuple[ComponentResponseEnvelope, dict[str, object] | None]:
        return (
            ComponentResponseEnvelope(
                protocol=SDK_PROTOCOL_VERSION,
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                responder=self.endpoint,
                outcome=outcome,
                payload_type=PING_RESULT_TYPE if payload is not None else None,
                payload_digest=payload_digest(payload) if payload is not None else None,
                # No independent evidence; never report VERIFIED.
                evidence_refs=(),
                completed_at=now,
            ),
            payload,
        )

    def dispatch(
        self, *, session: ReferenceSession,
        request: ComponentRequestEnvelope,
        payload: dict[str, object],
        now: datetime,
    ) -> tuple[ComponentResponseEnvelope, dict[str, object] | None]:
        """Validate typed inputs and synthetic test grants before dispatch.

        Test sessions are local object handles and are not trusted OS sessions.
        No side effects or persistence are performed on any path.
        """
        if session not in self._sessions:
            raise PermissionError("no current test session")
        if not isinstance(request, ComponentRequestEnvelope):
            raise TypeError("typed SDK request required")
        if (
            request.protocol != SDK_PROTOCOL_VERSION
            or request.source != session.source
            or request.destination != self.endpoint
            or request.authority != session.authority
        ):
            raise PermissionError("request does not match the test session/host")
        if request.payload_type != PING_TYPE:
            raise PermissionError("unrecognized demo capability schema")
        if now < request.created_at:
            raise PermissionError("request cannot be dispatched before creation")
        request.require_dispatchable(
            now=now, expected_destination_generation=self.endpoint.generation
        )
        if CAPABILITY_ID not in session.authority.scopes:
            raise PermissionError("capability absent from projected scope")
        if payload_digest(payload) != request.payload_digest:
            raise PermissionError("request payload digest mismatch")
        if request.request_id in self._seen_request_ids:
            raise PermissionError("replayed reference request ID")
        self._seen_request_ids.add(request.request_id)

        if self._stopped:
            return self._response(request, now, ComponentOutcome.DENIED)
        if CAPABILITY_ID not in self.available_capabilities:
            return self._response(request, now, ComponentOutcome.UNAVAILABLE)

        capability = self._capabilities.resolve(CAPABILITY_ID)
        result = self._capabilities.execute(CapabilityRequest(
            capability=capability,
            parameters=dict(payload),
            requested_scope=None,
            rationale="synthetic SDK reference; no real owner authorization",
            dispatch_context=CapabilityDispatchContext(
                dispatch_id=request.request_id,
                goal_id=session.authority.authority_ref,
                capability=CAPABILITY_ID,
                principal_id=session.authority.principal_id,
                audience=session.authority.audience_id,
            ),
        ))
        if result.kind in {CapabilityResultKind.UNAUTHORIZED, CapabilityResultKind.DENIED}:
            return self._response(request, now, ComponentOutcome.DENIED)
        if result.kind is CapabilityResultKind.UNAVAILABLE:
            return self._response(request, now, ComponentOutcome.UNAVAILABLE)
        if result.kind is not CapabilityResultKind.SUCCESS:
            return self._response(request, now, ComponentOutcome.FAILED)
        response_payload: dict[str, object] = {"result": result.evidence}
        return self._response(
            request, now, ComponentOutcome.SUCCEEDED_REPORTED_UNVERIFIED,
            response_payload,
        )
