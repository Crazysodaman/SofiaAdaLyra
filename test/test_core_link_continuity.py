"""C4: authenticated multi-Platform conversation and Core Link continuity.

All checks use disposable canonical SQLite state and a deterministic test
provider or fake peer transport. No production Core, host cutover, credential
store, Ollama endpoint or real Artemis/Venus host is accessed.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4

import pytest

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.application import SofiaApplication
from sofia.platform.core_link import (
    CoreLinkBindingState,
    CoreLinkClientAccessStore,
    CoreLinkConversationGateway,
    CoreLinkEndpoint,
    CoreLinkTLSCredentials,
    CoreLinkTransportError,
    PinnedCoreLinkClient,
)
from sofia.platform.distributed.inference_control import RemoteInferenceDenied
from sofia.platform.distributed.model import DistributedNode
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk import CoreLinkRequest, CoreLinkResponseStatus
from test.test_core_link_binding import activate, store
from test.test_core_link_conversation import (
    NOW, access, authorize, configuration, enrolled_store, request,
)
from test.test_distributed_inference_control import (
    NOW as FLEET_NOW, _provider, _request, _setup,
)


PROJECT_ROOT = Path(__file__).parent.parent


def gateway(application, store, *, generation=7):
    return CoreLinkConversationGateway(
        application, access_store=store,
        remote_platform_id="platform:canonical",
        remote_core_identity_id="core:sofia",
        generation_provider=lambda: generation,
        clock=lambda: NOW + timedelta(seconds=1),
    )


def linux_access():
    return replace(
        access(),
        client_id="client:linux-owner",
        certificate_public_key_sha256="b" * 64,
        local_platform_id="platform:linux",
        principal=PrincipalContext(
            "principal:sparks", "audience:shared",
            AudienceKind.SHARED,
        ),
    )


def scoped_request(value, operation, payload, **kwargs):
    base = request(operation, payload, **kwargs)
    return replace(
        base,
        local_platform_id=value.local_platform_id,
        remote_platform_id=value.remote_platform_id,
        remote_core_identity_id=value.remote_core_identity_id,
        remote_core_generation=value.remote_core_generation,
        protocol=value.protocol_version,
    )


def dispatch(gateway_value, value, operation, payload, fingerprint, **kwargs):
    return gateway_value.dispatch(
        certificate_public_key_sha256=fingerprint,
        request=scoped_request(value, operation, payload, **kwargs),
    )


def history_page(gateway_value, value, session_id, after, *, limit=1):
    payload = json.loads(json.dumps({
        "session_id": session_id, "after": after, "limit": limit,
    }))
    return dispatch(
        gateway_value, value, "conversation.history", payload,
        value.certificate_public_key_sha256,
    )


def drain_history(gateway_value, value, session_id):
    messages = []
    cursor = None
    for _page in range(16):
        response = history_page(
            gateway_value, value, session_id, cursor, limit=1,
        )
        assert response.status is CoreLinkResponseStatus.COMPLETED
        messages.extend(response.payload["messages"])
        cursor = response.payload["next_cursor"]
        if cursor is None:
            return messages
    raise AssertionError("bounded history traversal did not terminate")


def test_remote_conversation_survives_gateway_restart_cursor_and_duplicate_request(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    host_gateway = None
    try:
        store = enrolled_store(state)
        value = access()
        host_gateway = gateway(application, store)

        create_request = scoped_request(value, "conversation.create", {},
                                        idempotency_key="create:continuity")
        created = host_gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=create_request,
        )
        session_id = created.payload["session_id"]
        assert created.status is CoreLinkResponseStatus.COMPLETED

        first_request = scoped_request(
            value, "conversation.send",
            {"session_id": session_id, "content": "First durable turn",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:continuity:1",
        )
        first = host_gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=first_request,
        )
        duplicate = host_gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=first_request,
        )
        assert first.status is CoreLinkResponseStatus.COMPLETED
        assert duplicate.status is CoreLinkResponseStatus.COMPLETED
        assert duplicate.payload["content"] == first.payload["content"]
        assert duplicate.payload["receipt"]["replayed"] is True

        second = dispatch(
            host_gateway, value, "conversation.send",
            {"session_id": session_id, "content": "Second durable turn",
             "client_created_at": NOW.isoformat()},
            "a" * 64, idempotency_key="turn:continuity:2",
        )
        assert second.status is CoreLinkResponseStatus.COMPLETED

        original_history = drain_history(host_gateway, value, session_id)
        assert [item["role"] for item in original_history] == [
            "user", "assistant", "user", "assistant",
        ]
        assert [item["content"] for item in original_history][0::2] == [
            "First durable turn", "Second durable turn",
        ]
        assert len({item["message_id"] for item in original_history}) == 4

        # A restarted host reopens the same canonical history without a cache.
        host_gateway.close()
        host_gateway = gateway(application, store)
        replay = host_gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=create_request,
        )
        assert replay.payload["session_id"] == session_id
        assert drain_history(host_gateway, value, session_id) == original_history

        # No empty history is invented for an unknown conversation.
        missing = history_page(
            host_gateway, value, "session:does-not-exist", None,
        )
        assert missing.status is CoreLinkResponseStatus.UNAVAILABLE
        assert "messages" not in missing.payload

        # Reusing the same request ID for different content is a replay.
        replay_request = replace(first_request, payload={
            "session_id": session_id, "content": "Different replayed content",
            "client_created_at": NOW.isoformat(),
        })
        with pytest.raises(PermissionError, match="replayed"):
            host_gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=replay_request,
            )
    finally:
        if host_gateway is not None:
            host_gateway.close()
        application.shutdown()


def test_stale_generation_and_unavailable_service_are_reported_truthfully(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    store = enrolled_store(state)

    class UnavailableApplication:
        def open_channel_conversation(self, *, session_id=None):
            raise RuntimeError("disposable conversation service is offline")

    unavailable_gateway = gateway(UnavailableApplication(), store)
    try:
        response = dispatch(
            unavailable_gateway, access(), "conversation.create", {},
            "a" * 64, idempotency_key="create:unavailable",
        )
        assert response.status is CoreLinkResponseStatus.UNAVAILABLE
        assert response.payload["error"] == "conversation service is unavailable"

        with pytest.raises(PermissionError, match="generation mismatch"):
            unavailable_gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=replace(
                    scoped_request(access(), "status", {}),
                    remote_core_generation=8,
                ),
            )
        fixture = CoreLinkRequest.from_payload(json.loads((
            PROJECT_ROOT / "contracts/core-link/invalid-stale-generation.json"
        ).read_text(encoding="utf-8")))
        with pytest.raises(PermissionError, match="generation mismatch"):
            unavailable_gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=replace(
                    fixture, created_at=NOW,
                    deadline=NOW + timedelta(seconds=30),
                ),
            )
    finally:
        unavailable_gateway.close()


def test_one_core_identity_serves_distinct_clients_without_cross_audience_reads(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    host_gateway = None
    try:
        store = CoreLinkClientAccessStore(state)
        windows = access()
        linux = linux_access()
        for value in (windows, linux):
            approval_id = authorize(
                state, capability="core-link.enroll",
                parameters=value.parameters(),
            )
            store.enroll(value, approval_id=approval_id, now=NOW)
        host_gateway = gateway(application, store)

        windows_create = dispatch(
            host_gateway, windows, "conversation.create", {},
            "a" * 64, idempotency_key="create:windows",
        )
        linux_create = dispatch(
            host_gateway, linux, "conversation.create", {},
            "b" * 64, idempotency_key="create:linux",
        )
        windows_session = windows_create.payload["session_id"]
        linux_session = linux_create.payload["session_id"]
        assert windows_session != linux_session

        dispatch(
            host_gateway, windows, "conversation.send",
            {"session_id": windows_session, "content": "Windows private turn",
             "client_created_at": NOW.isoformat()},
            "a" * 64, idempotency_key="turn:windows:1",
        )
        dispatch(
            host_gateway, linux, "conversation.send",
            {"session_id": linux_session, "content": "Linux shared turn",
             "client_created_at": NOW.isoformat()},
            "b" * 64, idempotency_key="turn:linux:1",
        )

        windows_history = drain_history(host_gateway, windows, windows_session)
        linux_history = drain_history(host_gateway, linux, linux_session)
        assert [item["content"] for item in windows_history][0] == (
            "Windows private turn"
        )
        assert [item["content"] for item in linux_history][0] == (
            "Linux shared turn"
        )
        assert all(
            "Linux shared turn" not in item["content"]
            for item in windows_history
        )

        # A different enrolled client cannot select or read another audience's
        # conversation merely by presenting its opaque session ID.
        with pytest.raises(PermissionError):
            dispatch(
                host_gateway, linux, "conversation.select",
                {"session_id": windows_session}, "b" * 64,
            )
        with pytest.raises(PermissionError):
            history_page(host_gateway, linux, windows_session, None)

        # Both clients see the same one authoritative Core identity.
        windows_status = dispatch(
            host_gateway, windows, "status", {}, "a" * 64,
        )
        linux_status = dispatch(
            host_gateway, linux, "status", {}, "b" * 64,
        )
        assert windows_status.payload["remote_core_identity_id"] == (
            linux_status.payload["remote_core_identity_id"]
        ) == "core:sofia"

        # Wrong host or claimed Core identity cannot be chosen by a client.
        for change in (
            {"remote_platform_id": "platform:impostor"},
            {"remote_core_identity_id": "core:roland"},
            {"remote_core_generation": 8},
        ):
            with pytest.raises(PermissionError, match="identity or generation"):
                host_gateway.dispatch(
                    certificate_public_key_sha256="b" * 64,
                    request=replace(
                        scoped_request(linux, "status", {}), **change,
                    ),
                )

        # Revoking one client denies its later reads and writes while the
        # other enrolled client and the canonical Core identity stay usable.
        revoke_approval = authorize(
            state, capability="core-link.revoke",
            parameters={"client_id": windows.client_id, "expected_revision": 1},
            now=NOW + timedelta(seconds=2),
        )
        store.revoke(
            windows.client_id, expected_revision=1,
            approval_id=revoke_approval, now=NOW + timedelta(seconds=2),
        )
        with pytest.raises(PermissionError, match="not actively enrolled"):
            dispatch(
                host_gateway, windows, "conversation.send",
                {"session_id": windows_session, "content": "Denied write",
                 "client_created_at": NOW.isoformat()},
                "a" * 64, idempotency_key="turn:windows:denied",
            )
        with pytest.raises(PermissionError, match="not actively enrolled"):
            history_page(host_gateway, windows, windows_session, None)

        after_revoke = dispatch(
            host_gateway, linux, "conversation.send",
            {"session_id": linux_session, "content": "Linux still authorized",
             "client_created_at": NOW.isoformat()},
            "b" * 64, idempotency_key="turn:linux:2",
        )
        assert after_revoke.status is CoreLinkResponseStatus.COMPLETED
        assert linux_status.payload["remote_core_identity_id"] == "core:sofia"
    finally:
        if host_gateway is not None:
            host_gateway.close()
        application.shutdown()


def test_revoked_client_binding_trust_denies_before_network(tmp_path):
    registry = store(tmp_path)
    selected = registry.select(
        "binding:sofia-primary",
        expected_store_revision=activate(registry).revision,
    )
    value = selected.selected()
    assert value is not None
    endpoint = CoreLinkEndpoint(value.endpoint_id, "localhost", 443)
    client = PinnedCoreLinkClient(
        registry, endpoint_resolver=lambda _endpoint_id: endpoint,
        credential_resolver=lambda _ref: CoreLinkTLSCredentials(
            tmp_path / "ca.pem", tmp_path / "client.pem",
            tmp_path / "client.key",
        ),
        timeout_seconds=3,
    )
    request_value = CoreLinkRequest(
        request_id="request:revoked-trust",
        idempotency_key="status:revoked-trust",
        local_platform_id=value.local_platform_id,
        remote_platform_id=value.remote_platform_id,
        remote_core_identity_id=value.remote_core_identity_id,
        remote_core_generation=value.remote_core_generation,
        operation="status", payload={}, created_at=NOW,
        deadline=NOW + timedelta(seconds=30),
        protocol=value.protocol_version,
    )
    revoked = registry.transition(
        value.binding_id, expected_binding_revision=value.revision,
        expected_store_revision=selected.revision,
        state=CoreLinkBindingState.REVOKED,
        at=NOW + timedelta(seconds=3),
    )
    assert revoked.selected_binding_id is None
    with pytest.raises(CoreLinkTransportError, match="no Core Link binding"):
        client.request(request_value)
    with pytest.raises(PermissionError, match="no longer selected"):
        registry.require_current_selected(
            binding_id=value.binding_id,
            expected_binding_revision=value.revision,
            minimum_store_revision=selected.revision,
        )


def test_fleet_inference_routes_only_to_configured_eligible_nodes(tmp_path):
    node, transport, control = _setup(tmp_path)
    try:
        unknown = DistributedNode(uuid4(), "Unconfigured worker")
        with pytest.raises(RemoteInferenceDenied, match="enrolled"):
            control.infer(
                node_id=unknown.node_id,
                provider=_provider(),
                request=_request(),
                now=FLEET_NOW,
            )
        assert transport.calls == []

        # A configured node whose approved endpoint was revoked is not eligible.
        control.endpoints.revoke(node.node_id)
        with pytest.raises(RemoteInferenceDenied, match="endpoint"):
            control.infer(
                node_id=node.node_id,
                provider=_provider(),
                request=_request(),
                now=FLEET_NOW,
            )
        assert transport.calls == []

        # A node that authenticates but reports another inventory identity
        # never receives cognitive content.
        eligible_path = tmp_path / "eligible"
        eligible_path.mkdir()
        eligible, eligible_transport, eligible_control = _setup(eligible_path)
        try:
            eligible_transport.node_id = uuid4()
            with pytest.raises(RemoteInferenceDenied, match="inventory"):
                eligible_control.infer(
                    node_id=eligible.node_id,
                    provider=_provider(),
                    request=_request(),
                    now=FLEET_NOW,
                )
            assert eligible_transport.calls == ["authenticate", "discover"]
        finally:
            eligible_control.close()
    finally:
        control.close()
