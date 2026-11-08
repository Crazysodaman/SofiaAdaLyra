"""CORE-004 / IG-001: real pinned-mTLS wire, lost reply and idempotent reconnect.

The disposable gateway intentionally uses a deterministic *fake* answer.
This verifies the real Python CoreLinkServer + PinnedCoreLinkClient + desktop
state over an actual loopback mTLS socket, not Ollama or installed-host G8.
No production Core, canonical writer, host cutover, or Discord is involved.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Thread

import pytest

from sofia.modules.ui.core_link_desktop import (
    CoreLinkDesktopClient, CoreLinkDesktopStateStore, RemoteTurnUncertain,
)
from sofia.platform.core_link import (
    CoreLinkBinding, CoreLinkBindingState, CoreLinkBindingStore,
    CoreLinkEndpoint, CoreLinkServer, CoreLinkServerConfiguration,
    CoreLinkTLSCredentials, CoreLinkTransportError, PinnedCoreLinkClient,
)
from sofia.platform.distributed.tls import (
    public_key_fingerprint_from_pem_certificate,
)
from sofia.sdk import CoreLinkRequest, CoreLinkResponse, CoreLinkResponseStatus, ProtocolVersion
from test.test_core_link_conversation import tls_material


def test_core004_actual_mtls_lost_completed_reply_reconciles_without_resend(tmp_path):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    client_fingerprint = public_key_fingerprint_from_pem_certificate(client_cert)
    server_fingerprint = public_key_fingerprint_from_pem_certificate(server_cert)
    now = datetime.now(timezone.utc)

    class DisposableGateway:
        def __init__(self):
            self.messages = []
            self.known = {}
            self.send_attempts = 0
            self.produced = 0
            self.closed = False

        def dispatch(self, *, certificate_public_key_sha256, request):
            assert certificate_public_key_sha256 == client_fingerprint
            op = request.operation
            if op == "status":
                payload = {
                    "remote_platform_id": "platform:disposable-debian",
                    "remote_core_identity_id": "core:disposable",
                    "remote_core_generation": 7,
                    "protocol": "1.0", "state": "ready",
                    "operator_stop_active": False,
                }
            elif op in {"conversation.create", "conversation.select"}:
                payload = {"session_id": "session:disposable"}
            elif op == "conversation.send":
                self.send_attempts += 1
                key = request.idempotency_key
                text = request.payload["content"]
                if key not in self.known:
                    self.produced += 1
                    reply = "FAKE_PROVIDER_OUTPUT_" + str(self.produced)
                    self.known[key] = reply
                    stamp = datetime.now(timezone.utc)
                    self.messages.extend([
                        {"message_id": f"m:{self.produced}:user", "role": "user",
                         "content": text, "created_at": stamp.isoformat()},
                        {"message_id": f"m:{self.produced}:assistant", "role": "assistant",
                         "content": reply,
                         "created_at": (stamp + timedelta(microseconds=1)).isoformat()},
                    ])
                payload = {
                    "session_id": "session:disposable",
                    "content": self.known[key], "evidence_refs": [],
                    "receipt": {"status": "completed", "source_device_id": "client:disposable"},
                }
            elif op == "conversation.result":
                key = request.payload["idempotency_key"]
                if key not in self.known:
                    return CoreLinkResponse(
                        request.request_id, CoreLinkResponseStatus.OUTCOME_UNKNOWN,
                        {"state": "processing"}, datetime.now(timezone.utc),
                    )
                payload = {
                    "event_id": "event:disposable",
                    "state": "completed", "content": self.known[key],
                    "canonical_sequence": 1,
                }
            elif op == "conversation.history":
                payload = {
                    "session_id": "session:disposable",
                    "messages": list(self.messages), "next_cursor": None,
                }
            else:
                raise PermissionError("test gateway operation not authorized")
            return CoreLinkResponse(
                request.request_id, CoreLinkResponseStatus.COMPLETED,
                payload, datetime.now(timezone.utc),
            )

        def close(self):
            self.closed = True

    gateway = DisposableGateway()
    server = CoreLinkServer(
        CoreLinkServerConfiguration(
            listen_host="127.0.0.1", listen_port=0,
            server_certificate=server_cert,
            server_private_key=server_key,
            client_ca_file=ca,
            socket_timeout_seconds=5,
        ), gateway,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = tmp_path / "client-private"
        root.mkdir(mode=0o700)
        registry = CoreLinkBindingStore((root / "bindings.json").resolve())
        binding = CoreLinkBinding(
            binding_id="binding:disposable",
            local_platform_id="platform:disposable-windows",
            remote_platform_id="platform:disposable-debian",
            remote_core_identity_id="core:disposable",
            remote_core_generation=7,
            endpoint_id="endpoint:disposable-core",
            credential_ref="os-keystore:test/disposable-client",
            trust_anchor_ref=f"sha256:{server_fingerprint}",
            audience_id="audience:disposable-private",
            granted_scopes=(
                "core-link.status", "conversation.create", "conversation.select",
                "conversation.send", "conversation.result", "conversation.history",
            ),
            protocol_version=ProtocolVersion(1, 0),
            state=CoreLinkBindingState.PENDING_APPROVAL,
            revision=1, created_at=now, updated_at=now,
        )
        first = registry.add_pending(binding, expected_store_revision=0)
        second = registry.transition(
            binding.binding_id, expected_binding_revision=1,
            expected_store_revision=first.revision,
            state=CoreLinkBindingState.VERIFYING,
            at=now + timedelta(milliseconds=1),
        )
        third = registry.reconcile_contact(
            binding.binding_id, expected_binding_revision=2,
            expected_store_revision=second.revision,
            remote_platform_id=binding.remote_platform_id,
            remote_core_identity_id=binding.remote_core_identity_id,
            remote_core_generation=binding.remote_core_generation,
            endpoint_id=binding.endpoint_id,
            trust_anchor_ref=binding.trust_anchor_ref,
            at=now + timedelta(milliseconds=2),
        )
        registry.select(binding.binding_id, expected_store_revision=third.revision)
        endpoint = CoreLinkEndpoint(
            binding.endpoint_id, "localhost", server.address[1],
        )

        def client_transport():
            return PinnedCoreLinkClient(
                registry,
                endpoint_resolver=lambda _: endpoint,
                credential_resolver=lambda _: CoreLinkTLSCredentials(
                    ca, client_cert, client_key,
                ),
                timeout_seconds=5,
            )

        class DropAfterServerCompleted:
            """Simulate a lost HTTP acknowledgment AFTER the real mTLS POST."""
            def __init__(self, transport):
                self.transport = transport
                self.dropped = False

            def request(self, req):
                received = self.transport.request(req)
                if req.operation == "conversation.send" and not self.dropped:
                    self.dropped = True
                    raise CoreLinkTransportError(
                        "disposable network disconnected before client accepted reply"
                    )
                return received

        state_store = CoreLinkDesktopStateStore(
            (root / "desktop.json").resolve(), binding,
        )
        first_desktop = CoreLinkDesktopClient(
            DropAfterServerCompleted(client_transport()),
            binding, state_store,
        )
        assert first_desktop.start() == ()
        with pytest.raises(RemoteTurnUncertain, match="transport loss"):
            first_desktop.send("one disposable test turn")
        pending = state_store.load().pending_idempotency_key
        assert pending is not None
        assert gateway.produced == gateway.send_attempts == 1

        # A new client process/object, same exact binding and durable local key.
        second_desktop = CoreLinkDesktopClient(
            client_transport(), binding,
            CoreLinkDesktopStateStore((root / "desktop.json").resolve(), binding),
        )
        history = second_desktop.start()
        assert [m.actor for m in history] == ["user", "sofia"]
        assert history[-1].content == "FAKE_PROVIDER_OUTPUT_1"
        assert gateway.send_attempts == gateway.produced == 1
        assert second_desktop.state_store.load().pending_idempotency_key is None

        wrong_pin = replace(binding, trust_anchor_ref="sha256:" + "0" * 64)
        corrupt_root = tmp_path / "wrong-pin"
        corrupt_root.mkdir(mode=0o700)
        bad_store = CoreLinkBindingStore((corrupt_root / "bindings.json").resolve())
        b1 = bad_store.add_pending(wrong_pin, expected_store_revision=0)
        b2 = bad_store.transition(
            wrong_pin.binding_id, expected_binding_revision=1,
            expected_store_revision=b1.revision,
            state=CoreLinkBindingState.VERIFYING,
            at=now + timedelta(milliseconds=1),
        )
        b3 = bad_store.reconcile_contact(
            wrong_pin.binding_id, expected_binding_revision=2,
            expected_store_revision=b2.revision,
            remote_platform_id=wrong_pin.remote_platform_id,
            remote_core_identity_id=wrong_pin.remote_core_identity_id,
            remote_core_generation=wrong_pin.remote_core_generation,
            endpoint_id=wrong_pin.endpoint_id,
            trust_anchor_ref=wrong_pin.trust_anchor_ref,
            at=now + timedelta(milliseconds=2),
        )
        bad_store.select(wrong_pin.binding_id, expected_store_revision=b3.revision)
        bad_client = PinnedCoreLinkClient(
            bad_store, endpoint_resolver=lambda _: endpoint,
            credential_resolver=lambda _: CoreLinkTLSCredentials(
                ca, client_cert, client_key,
            ), timeout_seconds=5,
        )
        wrong_pin_now = datetime.now(timezone.utc)
        wrong_pin_request = CoreLinkRequest(
            request_id="request:wrong-pin",
            idempotency_key="status:wrong-pin",
            local_platform_id=wrong_pin.local_platform_id,
            remote_platform_id=wrong_pin.remote_platform_id,
            remote_core_identity_id=wrong_pin.remote_core_identity_id,
            remote_core_generation=wrong_pin.remote_core_generation,
            operation="status", payload={}, created_at=wrong_pin_now,
            deadline=wrong_pin_now + timedelta(seconds=30),
            protocol=wrong_pin.protocol_version,
        )
        with pytest.raises(CoreLinkTransportError, match="pin mismatch"):
            bad_client.request(wrong_pin_request)
        assert gateway.send_attempts == 1
    finally:
        server.close()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert gateway.closed
