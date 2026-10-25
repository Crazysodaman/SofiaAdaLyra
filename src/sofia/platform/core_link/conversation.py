"""Authenticated Core-host conversation boundary for thin Platform clients."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from typing import Protocol

from sofia.core.conversation.lifelong import (
    CanonicalTurnConflict,
    CanonicalTurnPending,
    CanonicalTurnUncertain,
    LifelongThreadStore,
)
from sofia.platform.core_link.access import (
    CoreLinkClientAccess, CoreLinkClientAccessStore,
)
from sofia.sdk import (
    CoreLinkRequest, CoreLinkResponse, CoreLinkResponseStatus,
    SDK_PROTOCOL_VERSION,
)


class CoreLinkApplication(Protocol):
    def open_channel_conversation(self, *, session_id: str | None = None): ...


class CoreLinkConversationGateway:
    """Route authenticated requests into the one canonical application.

    Transport supplies only the peer public-key fingerprint.  Principal,
    audience and effective scopes always come from canonical enrollment.
    """

    def __init__(
        self, application: CoreLinkApplication, *,
        access_store: CoreLinkClientAccessStore,
        remote_platform_id: str, remote_core_identity_id: str,
        generation_provider,
        clock=lambda: datetime.now(timezone.utc),
        max_open_sessions: int = 64,
    ) -> None:
        if not callable(getattr(application, "open_channel_conversation", None)):
            raise TypeError("application must open canonical channel conversations")
        if not isinstance(access_store, CoreLinkClientAccessStore):
            raise TypeError("canonical CoreLinkClientAccessStore required")
        for label, value in (
            ("remote_platform_id", remote_platform_id),
            ("remote_core_identity_id", remote_core_identity_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")
        if not callable(generation_provider) or not callable(clock):
            raise TypeError("generation_provider and clock must be callable")
        if type(max_open_sessions) is not int or not 1 <= max_open_sessions <= 256:
            raise ValueError("max_open_sessions must be in 1..256")
        self.application = application
        self.access_store = access_store
        self.remote_platform_id = remote_platform_id
        self.remote_core_identity_id = remote_core_identity_id
        self.generation_provider = generation_provider
        self.clock = clock
        self.max_open_sessions = max_open_sessions
        self._services: dict[tuple[str, str], object] = {}
        self._lock = RLock()

    @staticmethod
    def _exact(payload: dict[str, object], keys: set[str]) -> None:
        if set(payload) != keys:
            raise ValueError("Core Link operation payload has unreviewed fields")

    @staticmethod
    def _event_id(access: CoreLinkClientAccess, idempotency_key: str) -> str:
        digest = sha256(
            (access.client_id + "\0" + idempotency_key).encode("utf-8")
        ).hexdigest()
        return f"core-link:{digest}"

    def _authenticate(
        self, fingerprint: str, request: CoreLinkRequest,
    ) -> tuple[CoreLinkClientAccess, datetime, int]:
        now = self.clock()
        request.require_current(now)
        if request.protocol.major != SDK_PROTOCOL_VERSION.major:
            raise PermissionError("Core Link SDK protocol is incompatible")
        access = self.access_store.authenticate(fingerprint, now=now)
        if access is None:
            raise PermissionError("Core Link peer is not actively enrolled")
        if request.operation != "status" and self.access_store.stop.current().active:
            raise PermissionError("operator stop blocks Core Link operations")
        generation = self.generation_provider()
        if type(generation) is not int or generation < 1:
            raise RuntimeError("canonical Core generation is unavailable")
        exact = (
            request.local_platform_id == access.local_platform_id
            and request.remote_platform_id == access.remote_platform_id
            and request.remote_core_identity_id == access.remote_core_identity_id
            and request.remote_core_generation == access.remote_core_generation
            and request.remote_platform_id == self.remote_platform_id
            and request.remote_core_identity_id == self.remote_core_identity_id
            and request.remote_core_generation == generation
            and request.protocol == access.protocol_version
        )
        if not exact:
            raise PermissionError("Core Link destination identity or generation mismatch")
        access.require_scope(
            "core-link.status" if request.operation == "status" else request.operation,
            now=now,
        )
        return access, now, generation

    def _service(self, access: CoreLinkClientAccess, session_id: str | None):
        if session_id is not None and (
            not isinstance(session_id, str) or not session_id.strip()
            or len(session_id) > 256
        ):
            raise ValueError("session_id must be bounded nonempty text")
        key = (access.client_id, session_id or "")
        with self._lock:
            existing = self._services.get(key)
            if existing is not None:
                return existing
            if len(self._services) >= self.max_open_sessions:
                raise RuntimeError("Core Link session capacity is exhausted")
            service = self.application.open_channel_conversation(
                session_id=session_id
            )
            try:
                service.bind_authenticated_principal(access.principal)
            except Exception:
                service.close()
                raise
            actual = service.session_id
            if not isinstance(actual, str) or not actual:
                service.close()
                raise RuntimeError("canonical conversation did not produce a session ID")
            actual_key = (access.client_id, actual)
            duplicate = self._services.get(actual_key)
            if duplicate is not None:
                service.close()
                return duplicate
            self._services[actual_key] = service
            return service

    def dispatch(
        self, *, certificate_public_key_sha256: str,
        request: CoreLinkRequest,
    ) -> CoreLinkResponse:
        if not isinstance(request, CoreLinkRequest):
            raise TypeError("typed CoreLinkRequest required")
        access, now, generation = self._authenticate(
            certificate_public_key_sha256, request,
        )
        operation = request.operation
        payload = request.payload
        if operation == "status":
            self._exact(payload, set())
            result = {
                "remote_platform_id": self.remote_platform_id,
                "remote_core_identity_id": self.remote_core_identity_id,
                "remote_core_generation": generation,
                "protocol": str(SDK_PROTOCOL_VERSION),
                "state": "ready",
                "operator_stop_active": self.access_store.stop.current().active,
            }
        elif operation == "conversation.create":
            self._exact(payload, set())
            service = self._service(access, None)
            result = {"session_id": service.session_id}
        elif operation == "conversation.select":
            self._exact(payload, {"session_id"})
            service = self._service(access, payload["session_id"])
            result = {"session_id": service.session_id}
        elif operation == "conversation.history":
            self._exact(payload, {"session_id", "after", "limit"})
            service = self._service(access, payload["session_id"])
            limit = payload["limit"]
            if type(limit) is not int or not 1 <= limit <= 200:
                raise ValueError("history limit must be in 1..200")
            after_raw = payload["after"]
            after = None
            if after_raw is not None:
                if not isinstance(after_raw, dict) or set(after_raw) != {
                    "created_at", "message_id",
                }:
                    raise ValueError("history cursor is invalid")
                after = (
                    datetime.fromisoformat(after_raw["created_at"]),
                    after_raw["message_id"],
                )
            messages = service.authenticated_messages_page(
                principal=access.principal, after=after, limit=limit,
            )
            result = {
                "session_id": service.session_id,
                "messages": [
                    {
                        "message_id": item.id, "role": item.role.value,
                        "content": item.content,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in messages
                ],
                "next_cursor": (
                    None if not messages else {
                        "created_at": messages[-1].created_at.isoformat(),
                        "message_id": messages[-1].id,
                    }
                ),
            }
        elif operation == "conversation.send":
            self._exact(payload, {"session_id", "content", "client_created_at"})
            content = payload["content"]
            if not isinstance(content, str) or not content.strip() or len(content) > 12000:
                raise ValueError("turn content must be bounded nonempty text")
            client_created_raw = payload["client_created_at"]
            client_created_at = (
                None if client_created_raw is None
                else datetime.fromisoformat(client_created_raw)
            )
            service = self._service(access, payload["session_id"])
            event_id = self._event_id(access, request.idempotency_key)
            try:
                response = service.respond(
                    content, principal=access.principal,
                    channel="core-link", source_event_id=event_id,
                    source_device_id=access.client_id,
                    client_created_at=client_created_at,
                )
            except CanonicalTurnConflict as exc:
                return CoreLinkResponse(
                    request.request_id, CoreLinkResponseStatus.CONFLICT,
                    {"event_id": event_id, "error": str(exc)}, now,
                )
            except (CanonicalTurnPending, CanonicalTurnUncertain) as exc:
                return CoreLinkResponse(
                    request.request_id, CoreLinkResponseStatus.OUTCOME_UNKNOWN,
                    {"event_id": event_id, "error": str(exc)}, now,
                )
            result = {
                "session_id": service.session_id,
                "content": response.content,
                "evidence_refs": list(response.evidence_refs),
                "receipt": service.last_turn_receipt,
            }
        elif operation in {"conversation.result", "conversation.cancel"}:
            self._exact(payload, {"idempotency_key"})
            target = payload["idempotency_key"]
            if not isinstance(target, str) or not target.strip():
                raise ValueError("target idempotency_key required")
            event_id = self._event_id(access, target)
            admission = LifelongThreadStore(
                self.access_store.path
            ).turn_status(event_id=event_id, principal=access.principal)
            if admission is None:
                status = CoreLinkResponseStatus.UNAVAILABLE
                result = {"event_id": event_id, "state": "not_found"}
            elif admission.status == "completed":
                status = CoreLinkResponseStatus.COMPLETED
                result = {
                    "event_id": event_id, "state": "completed",
                    "content": admission.response.content,
                    "canonical_sequence": admission.canonical_sequence,
                }
            elif admission.status == "processing":
                # The provider contract has no trustworthy mid-call abort.
                # Never report cancellation or retry an operation that may be
                # producing a response/tool proposal.
                status = CoreLinkResponseStatus.OUTCOME_UNKNOWN
                result = {"event_id": event_id, "state": "processing"}
            else:
                status = CoreLinkResponseStatus.OUTCOME_UNKNOWN
                result = {"event_id": event_id, "state": admission.status}
            return CoreLinkResponse(request.request_id, status, result, now)
        else:  # pragma: no cover - CoreLinkRequest rejects this first.
            raise ValueError("unsupported Core Link operation")
        return CoreLinkResponse(
            request.request_id, CoreLinkResponseStatus.COMPLETED, result, now,
        )

    def close(self) -> None:
        with self._lock:
            services = tuple(self._services.values())
            self._services.clear()
        for service in services:
            service.close()
