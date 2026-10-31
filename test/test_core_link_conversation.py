from dataclasses import replace
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
import threading
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.conversation.lifelong import LifelongThreadStore
from sofia.platform.application import SofiaApplication
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.platform.core_link import (
    CoreLinkBinding, CoreLinkBindingState, CoreLinkBindingStore,
    CoreLinkClientAccess, CoreLinkClientAccessStore,
    CoreLinkConversationGateway, CoreLinkEndpoint, CoreLinkServer,
    CoreLinkServerConfiguration, CoreLinkTLSCredentials,
    CoreLinkTransportError, PinnedCoreLinkClient,
)
from sofia.platform.distributed.tls import (
    public_key_fingerprint_from_pem_certificate,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk import (
    CoreLinkRequest,
    CoreLinkResponse, CoreLinkResponseStatus, ProtocolVersion,
)
from test.owner_auth_fixture import record_verified_owner_approval
from sofia.modules.ui.core_link_desktop import (
    CoreLinkDesktopClient, CoreLinkDesktopStateStore,
)


NOW = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).parent.parent


def access() -> CoreLinkClientAccess:
    return CoreLinkClientAccess(
        client_id="client:windows-owner",
        certificate_public_key_sha256="a" * 64,
        local_platform_id="platform:windows",
        remote_platform_id="platform:canonical",
        remote_core_identity_id="core:sofia",
        remote_core_generation=7,
        principal=PrincipalContext(
            "principal:sparks", "audience:owner-private",
            AudienceKind.PRIVATE,
        ),
        scopes=(
            "core-link.status", "conversation.create", "conversation.select",
            "conversation.send", "conversation.history",
            "conversation.result", "conversation.cancel",
            "settings.snapshot", "settings.update", "settings.events",
            "settings.read.core", "settings.write.core",
            "module.settings.list", "module.settings.snapshot",
            "module.settings.update",
        ),
        protocol_version=ProtocolVersion(1, 0),
        enrolled_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )


def authorize(state_path, *, capability: str, parameters: dict, now=NOW) -> str:
    verifier = ExecutionApprovalVerifier(state_path)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=capability,
        request_fingerprint=execution_fingerprint(capability, parameters),
        approved_by="Sparks", approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(verifier, approval)
    return approval.approval_id


def request(
    operation: str, payload: dict[str, object], *,
    request_id: str | None = None, idempotency_key: str | None = None,
    generation: int = 7,
) -> CoreLinkRequest:
    return CoreLinkRequest(
        request_id=request_id or f"request:{uuid4().hex}",
        idempotency_key=idempotency_key or f"idempotency:{uuid4().hex}",
        local_platform_id="platform:windows",
        remote_platform_id="platform:canonical",
        remote_core_identity_id="core:sofia",
        remote_core_generation=generation,
        operation=operation, payload=payload,
        created_at=NOW, deadline=NOW + timedelta(minutes=1),
    )


def configuration(tmp_path: Path) -> SofiaConfiguration:
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["curious"],'
        '"communication_style":"Direct."}', encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=PROJECT_ROOT / "src/sofia/core/constitution/constitution.md",
        constitution_hash_path=PROJECT_ROOT / "src/sofia/core/constitution/constitution.sha256",
        identity_path=PROJECT_ROOT / "src/sofia/core/identity/identity.json",
        personality_path=personality,
        avatar_path=PROJECT_ROOT / "src/sofia/core/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
    )


def enrolled_store(state_path) -> CoreLinkClientAccessStore:
    store = CoreLinkClientAccessStore(state_path)
    value = access()
    approval_id = authorize(
        state_path, capability="core-link.enroll", parameters=value.parameters(),
    )
    assert store.enroll(value, approval_id=approval_id, now=NOW) == value
    return store


def tls_material(tmp_path: Path):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Core Link Test CA")])
    now = datetime.now(timezone.utc)
    ca = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = tmp_path / "ca.pem"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))

    def leaf(name: str, server: bool):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=True, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ), critical=True)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    ca_key.public_key(),
                ),
                critical=False,
            )
        )
        if server:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ip_address("127.0.0.1")),
                ]), critical=False,
            ).add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
        else:
            builder = builder.add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
        certificate = builder.sign(ca_key, hashes.SHA256())
        certificate_path = tmp_path / f"{name}.pem"
        key_path = tmp_path / f"{name}.key"
        certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        return certificate_path, key_path

    return ca_path, leaf("localhost", True), leaf("client", False)


def test_sdk_contract_strict_round_trip_and_bounds():
    original = request("status", {})
    assert CoreLinkRequest.from_payload(original.to_payload()) == original
    response = CoreLinkResponse(
        original.request_id, CoreLinkResponseStatus.COMPLETED,
        {"state": "ready"}, NOW,
    )
    assert CoreLinkResponse.from_payload(response.to_payload()) == response
    changed = original.to_payload()
    changed["authority"] = "caller-forged"
    with pytest.raises(ValueError, match="unreviewed"):
        CoreLinkRequest.from_payload(changed)
    with pytest.raises(ValueError, match="64 KiB"):
        request("conversation.send", {"content": "x" * 70_000})


def test_enrollment_consumes_exact_owner_approval_and_revocation_is_immediate(
    canonical_state_path,
):
    store = CoreLinkClientAccessStore(canonical_state_path)
    value = access()
    enrollment_id = authorize(
        canonical_state_path, capability="core-link.enroll",
        parameters=value.parameters(),
    )
    store.enroll(value, approval_id=enrollment_id, now=NOW)
    assert store.authenticate("a" * 64, now=NOW) == value
    with pytest.raises(PermissionError, match="already consumed"):
        store.enroll(value, approval_id=enrollment_id, now=NOW)
    revoke_parameters = {"client_id": value.client_id, "expected_revision": 1}
    revoke_id = authorize(
        canonical_state_path, capability="core-link.revoke",
        parameters=revoke_parameters,
    )
    revoked = store.revoke(
        value.client_id, expected_revision=1,
        approval_id=revoke_id, now=NOW + timedelta(seconds=1),
    )
    assert revoked.revoked_at == NOW + timedelta(seconds=1)
    assert store.authenticate(
        "a" * 64, now=NOW + timedelta(seconds=1),
    ) is None


def test_operator_stop_blocks_remote_turns_but_keeps_diagnostic_status(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    gateway = None
    try:
        store = enrolled_store(state)
        gateway = CoreLinkConversationGateway(
            application, access_store=store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        OperatorStopStore(state).set(
            active=True, reason="test stop", updated_by="Sparks",
            at=NOW + timedelta(milliseconds=1),
        )
        status = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request("status", {}),
        )
        assert status.payload["state"] == "ready"
        assert status.payload["operator_stop_active"] is True
        with pytest.raises(PermissionError, match="operator stop"):
            gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=request("conversation.create", {}),
            )
    finally:
        if gateway is not None:
            gateway.close()
        application.shutdown()


def test_core_link_module_settings_derive_identity_and_do_not_mint_authority(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    calls = []

    class ModuleSettings:
        def catalog(self):
            return ({
                "module_id": "org.sofia.example", "package_digest": "b" * 64,
                "lifecycle": "active", "lifecycle_revision": 3,
                "revision": 1, "effective_revision": 1,
                "settings_identity": "current",
                "contract": {"schema": "sofia.module.settings.v1"},
            },)

        def snapshot(self, *, module_id):
            assert module_id == "org.sofia.example"
            return {
                **self.catalog()[0], "values": {"display.mode": "compact"},
            }

        def update(self, **arguments):
            calls.append(arguments)
            from sofia.platform.modules import ModuleSettingsReceipt
            from sofia.platform.config.settings_authority import SettingsApplyState
            return ModuleSettingsReceipt(
                "org.sofia.example", "b" * 64, 2, 1,
                SettingsApplyState.PENDING_NEXT_OPERATION,
                ("display.mode",), ("next_operation",),
            )

    gateway = None
    try:
        gateway = CoreLinkConversationGateway(
            application, access_store=enrolled_store(state),
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            module_settings=ModuleSettings(), clock=lambda: NOW,
        )
        listed = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request("module.settings.list", {}),
        )
        assert listed.payload["modules"][0]["module_id"] == "org.sofia.example"
        changed = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "module.settings.update", {
                    "module_id": "org.sofia.example",
                    "expected_package_digest": "b" * 64,
                    "expected_lifecycle_revision": 3,
                    "expected_revision": 1,
                    "approval_ref": "approval:owner-fido",
                    "changes": {"display.mode": "full"},
                }, idempotency_key="module-settings:stable",
            ),
        )
        assert changed.payload["apply_state"] == "pending_next_operation"
        assert calls[0]["client_id"] == "client:windows-owner"
        assert calls[0]["principal_id"] == "principal:sparks"
        assert calls[0]["audience_id"] == "audience:owner-private"
        assert calls[0]["approval_ref"] == "approval:owner-fido"
        assert calls[0]["idempotency_key"] == "module-settings:stable"
    finally:
        if gateway is not None:
            gateway.close()
        application.shutdown()


def test_real_application_core_link_turn_is_deduplicated_and_audience_scoped(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    config = configuration(tmp_path)
    application = SofiaApplication(config)
    application.start()
    gateway = None
    try:
        store = enrolled_store(state)
        gateway = CoreLinkConversationGateway(
            application, access_store=store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        create_request = request(
            "conversation.create", {}, idempotency_key="session:stable-owner",
        )
        created = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=create_request,
        )
        session_id = created.payload["session_id"]
        create_replay = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=create_request,
        )
        assert create_replay.payload["session_id"] == session_id
        gateway.close()
        gateway = CoreLinkConversationGateway(
            application, access_store=store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        restarted_replay = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=create_request,
        )
        assert restarted_replay.payload["session_id"] == session_id
        gateway.session_requests.claim(
            client_id=access().client_id,
            idempotency_key="session:interrupted-create",
            now=NOW + timedelta(milliseconds=1),
        )
        interrupted_create = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.create", {},
                idempotency_key="session:interrupted-create",
            ),
        )
        assert interrupted_create.status is CoreLinkResponseStatus.OUTCOME_UNKNOWN
        stable = "turn:stable-owner-1"
        first = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.send",
                {"session_id": session_id, "content": "Hello Sofía",
                 "client_created_at": NOW.isoformat()},
                idempotency_key=stable,
            ),
        )
        replay = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.send",
                {"session_id": session_id, "content": "Hello Sofía",
                 "client_created_at": NOW.isoformat()},
                idempotency_key=stable,
            ),
        )
        assert first.status is CoreLinkResponseStatus.COMPLETED
        assert first.payload["receipt"]["source_device_id"] == access().client_id
        assert replay.payload["content"] == first.payload["content"]
        assert replay.payload["receipt"]["replayed"] is True
        conflict = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.send",
                {"session_id": session_id, "content": "Different payload",
                 "client_created_at": NOW.isoformat()},
                idempotency_key=stable,
            ),
        )
        assert conflict.status is CoreLinkResponseStatus.CONFLICT
        pending_key = "turn:still-processing"
        LifelongThreadStore(state).admit_turn(
            event_id=gateway._event_id(access(), pending_key),
            principal=access().principal, session_id=session_id,
            channel="core-link", content="Still processing",
            runtime_id="conversation-runtime:other",
            now=NOW + timedelta(milliseconds=500),
            source_device_id=access().client_id,
            client_created_at=NOW,
        )
        pending = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.send",
                {"session_id": session_id, "content": "Still processing",
                 "client_created_at": NOW.isoformat()},
                idempotency_key=pending_key,
            ),
        )
        assert pending.status is CoreLinkResponseStatus.OUTCOME_UNKNOWN
        history = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.history",
                {"session_id": session_id, "after": None, "limit": 20},
            ),
        )
        assert [item["role"] for item in history.payload["messages"]] == [
            "user", "assistant",
        ]
        result = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.result", {"idempotency_key": stable},
            ),
        )
        assert result.status is CoreLinkResponseStatus.COMPLETED
        assert result.payload["content"] == first.payload["content"]
        with pytest.raises(PermissionError, match="generation mismatch"):
            gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=request("status", {}, generation=8),
            )
        with pytest.raises(PermissionError, match="not actively enrolled"):
            gateway.dispatch(
                certificate_public_key_sha256="b" * 64,
                request=request("status", {}),
            )
    finally:
        if gateway is not None:
            gateway.close()
        application.shutdown()


def test_core_link_settings_are_cas_scoped_and_emit_apply_receipts(tmp_path):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    applied = []
    gateway = None
    try:
        gateway = CoreLinkConversationGateway(
            application, access_store=enrolled_store(state),
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            settings_live_apply=lambda settings, fields: applied.append(fields),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        initial = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request("settings.snapshot", {}),
        )
        assert initial.payload["revision"] == 0
        assert "adaptive_theme" not in initial.payload["values"]
        change = request(
            "settings.update",
            {"expected_revision": 0, "changes": {"location_label": "Lab"}},
            idempotency_key="settings:location:1",
        )
        updated = gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=change,
        )
        replay = gateway.dispatch(
            certificate_public_key_sha256="a" * 64, request=change,
        )
        assert updated.payload == replay.payload
        assert updated.payload["apply_state"] == "applied"
        assert applied == [("location_label",)]
        conflict = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "settings.update",
                {"expected_revision": 0, "changes": {"location_label": "Old"}},
                idempotency_key="settings:stale",
            ),
        )
        assert conflict.status is CoreLinkResponseStatus.CONFLICT
        events = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "settings.events", {"after_revision": 0, "limit": 10},
            ),
        )
        assert events.payload["events"][0]["changed_fields"] == ["location_label"]
    finally:
        if gateway is not None:
            gateway.close()
        application.shutdown()


def test_pinned_mtls_core_link_runs_real_remote_conversation_without_local_core(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    ca_path, (server_cert, server_key), (client_cert, client_key) = tls_material(
        tmp_path
    )
    client_fingerprint = public_key_fingerprint_from_pem_certificate(client_cert)
    server_fingerprint = public_key_fingerprint_from_pem_certificate(server_cert)
    application = SofiaApplication(configuration(tmp_path))
    application.start()
    gateway = None
    server = None
    thread = None
    try:
        host_access = replace(
            access(), certificate_public_key_sha256=client_fingerprint,
        )
        access_store = CoreLinkClientAccessStore(state)
        approval_id = authorize(
            state, capability="core-link.enroll",
            parameters=host_access.parameters(),
        )
        access_store.enroll(host_access, approval_id=approval_id, now=NOW)
        gateway = CoreLinkConversationGateway(
            application, access_store=access_store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        server = CoreLinkServer(
            CoreLinkServerConfiguration(
                listen_host="127.0.0.1", listen_port=0,
                server_certificate=server_cert,
                server_private_key=server_key,
                client_ca_file=ca_path,
                socket_timeout_seconds=3,
            ),
            gateway,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        binding_root = tmp_path / "client-private"
        binding_root.mkdir(mode=0o700)
        binding_store = CoreLinkBindingStore(
            (binding_root / "bindings.json").resolve()
        )
        binding = CoreLinkBinding(
            binding_id="binding:sofia", local_platform_id="platform:windows",
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia", remote_core_generation=7,
            endpoint_id="endpoint:test-core",
            credential_ref="os-keystore:test/core-link",
            trust_anchor_ref=f"sha256:{server_fingerprint}",
            audience_id="audience:owner-private",
            granted_scopes=("core-link.status", "conversation.create", "conversation.send"),
            protocol_version=ProtocolVersion(1, 0),
            state=CoreLinkBindingState.PENDING_APPROVAL, revision=1,
            created_at=NOW, updated_at=NOW,
        )
        pending = binding_store.add_pending(binding, expected_store_revision=0)
        verifying = binding_store.transition(
            binding.binding_id, expected_binding_revision=1,
            expected_store_revision=pending.revision,
            state=CoreLinkBindingState.VERIFYING,
            at=NOW + timedelta(milliseconds=1),
        )
        active = binding_store.reconcile_contact(
            binding.binding_id, expected_binding_revision=2,
            expected_store_revision=verifying.revision,
            remote_platform_id=binding.remote_platform_id,
            remote_core_identity_id=binding.remote_core_identity_id,
            remote_core_generation=binding.remote_core_generation,
            endpoint_id=binding.endpoint_id,
            trust_anchor_ref=binding.trust_anchor_ref,
            at=NOW + timedelta(milliseconds=2),
        )
        binding_store.select(
            binding.binding_id, expected_store_revision=active.revision,
        )
        endpoint = CoreLinkEndpoint(
            binding.endpoint_id, "localhost", server.address[1],
        )
        client = PinnedCoreLinkClient(
            binding_store,
            endpoint_resolver=lambda endpoint_id: (
                endpoint if endpoint_id == endpoint.endpoint_id else None
            ),
            credential_resolver=lambda credential_ref: CoreLinkTLSCredentials(
                ca_path, client_cert, client_key,
            ),
            timeout_seconds=3,
        )
        created = client.request(request("conversation.create", {}))
        sent = client.request(request(
            "conversation.send",
            {
                "session_id": created.payload["session_id"],
                "content": "Hello remotely",
                "client_created_at": None,
            },
            idempotency_key="turn:real-mtls",
        ))
        assert sent.status is CoreLinkResponseStatus.COMPLETED
        assert sent.payload["receipt"]["source_device_id"] == host_access.client_id

        remote_ui = CoreLinkDesktopClient(
            client, binding,
            CoreLinkDesktopStateStore(
                (binding_root / "desktop-state.json").resolve(), binding,
            ),
            clock=lambda: NOW + timedelta(seconds=1),
        )
        assert remote_ui.start() == ()
        rendered = remote_ui.send("Desktop through the authenticated Core Link")
        assert [message.actor for message in rendered] == ["user", "sofia"]
        assert not any(path.suffix == ".db" for path in binding_root.iterdir())

        corrupt = replace(binding, trust_anchor_ref="sha256:" + "0" * 64)
        quarantined_root = tmp_path / "client-corrupt"
        quarantined_root.mkdir(mode=0o700)
        bad_store = CoreLinkBindingStore((quarantined_root / "bindings.json").resolve())
        first = bad_store.add_pending(corrupt, expected_store_revision=0)
        second = bad_store.transition(
            corrupt.binding_id, expected_binding_revision=1,
            expected_store_revision=first.revision,
            state=CoreLinkBindingState.VERIFYING,
            at=NOW + timedelta(milliseconds=1),
        )
        third = bad_store.reconcile_contact(
            corrupt.binding_id, expected_binding_revision=2,
            expected_store_revision=second.revision,
            remote_platform_id=corrupt.remote_platform_id,
            remote_core_identity_id=corrupt.remote_core_identity_id,
            remote_core_generation=corrupt.remote_core_generation,
            endpoint_id=corrupt.endpoint_id,
            trust_anchor_ref=corrupt.trust_anchor_ref,
            at=NOW + timedelta(milliseconds=2),
        )
        bad_store.select(corrupt.binding_id, expected_store_revision=third.revision)
        bad_client = PinnedCoreLinkClient(
            bad_store, endpoint_resolver=lambda _: endpoint,
            credential_resolver=lambda _: CoreLinkTLSCredentials(
                ca_path, client_cert, client_key,
            ), timeout_seconds=3,
        )
        with pytest.raises(CoreLinkTransportError, match="pin mismatch"):
            bad_client.request(request("status", {}))
    finally:
        if server is not None:
            server.close()
        if thread is not None:
            thread.join(timeout=2)
        if server is None and gateway is not None:
            gateway.close()
        application.shutdown()


def test_g4_outbound_core_link_frame_rejected_before_network(monkeypatch, tmp_path):
    """Oversized Core Link payload cannot reach mTLS or consume remote work."""
    from types import SimpleNamespace
    import sofia.platform.core_link.transport as transport

    selected = []
    client = object.__new__(PinnedCoreLinkClient)
    client._selected = lambda _request: (
        selected.append("selected") or SimpleNamespace(credential_ref="test"),
        CoreLinkEndpoint("endpoint:g4", "localhost", 443),
    )
    client.credential_resolver = lambda _ref: CoreLinkTLSCredentials(
        tmp_path / "ca.pem", tmp_path / "client.pem", tmp_path / "client.key",
    )
    monkeypatch.setattr(transport, "_MAX_WIRE_BYTES", 32)

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("oversized request opened a network connection")

    monkeypatch.setattr(transport, "HTTPSConnection", forbidden_network)
    with pytest.raises(CoreLinkTransportError, match="outbound request exceeds size"):
        client.request(request("status", {}))
    assert selected == ["selected"]
