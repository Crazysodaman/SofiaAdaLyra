from __future__ import annotations

from datetime import datetime,timedelta,timezone
from ipaddress import ip_address
from pathlib import Path
import socket
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID,NameOID

from sofia.platform.distributed.agent import RemoteAgentConfig,RemoteAgentDispatcher,RemoteAgentServer
from sofia.platform.distributed.https_transport import PinnedHttpsRemoteTransport
from sofia.platform.distributed.capability import RemoteFleetToolService
from sofia.platform.distributed.operator import enroll_node,approve_endpoint,grant_operation,retire_node
from sofia.platform.distributed.model import NodeEnrollment
from sofia.platform.distributed.model import DistributedNode,NodeEndpoint,NodeTransport
from sofia.platform.distributed.operations import RemoteOperationRequest,RemoteOutcome
from sofia.platform.capability.model import CapabilityDispatchContext
from sofia.platform.distributed.https_transport import HttpsTransportError
from sofia.platform.distributed.tls import public_key_fingerprint_from_pem_certificate
from sofia.platform.ops.model import FleetHost,HostLifecycle
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.capability import Capability,CapabilitySystem
from sofia.platform.capability.gateway import CapabilityGateway
from sofia.core.goals import (
    CompletionKind,GoalCompletionCondition,GoalEvidenceIndex,
    GoalEvidenceLedger,GoalService,GoalStore,
)
from sofia.core.goals.coordinator import (
    GoalProductionCoordinator,goal_reconciliation_approval_parameters,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,ExecutionApprovalVerifier,execution_fingerprint,
)
from test.owner_auth_fixture import record_verified_owner_approval


def _write_key(path:Path,key):
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))


def _ca(tmp_path:Path):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"Sofia Test CA")])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .sign(key,hashes.SHA256()))
    cert_path=tmp_path/"ca.pem"; cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key,cert,cert_path


def _leaf(tmp_path:Path,ca_key,ca_cert,name:str,kind:str):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc)
    builder=(x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)]))
        .issuer_name(ca_cert.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=True, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False))
    if kind=="server":
        builder=builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"),x509.IPAddress(ip_address("127.0.0.1"))]),
            critical=False,
        ).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
    else:
        builder=builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False)
    cert=builder.sign(ca_key,hashes.SHA256())
    cert_path=tmp_path/f"{name}.pem"; key_path=tmp_path/f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM)); _write_key(key_path,key)
    return cert_path,key_path


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def test_pinned_mutual_tls_transport_authenticates_discovers_executes_and_dedupes(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"sofia-client","client")
    node_id=uuid4(); port=_free_port(); counter={"value":0}
    dispatcher=RemoteAgentDispatcher()
    def inspect(_):
        counter["value"]+=1
        return {"hostname":"venus"}
    dispatcher.register("system.inspect","system",inspect)
    config=RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(client_cert),
        ledger_path=tmp_path/"agent-ledger.db",
    )
    server=RemoteAgentServer(config,dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        endpoint=NodeEndpoint("localhost",port,NodeTransport.HTTPS)
        enrollment=NodeEnrollment(
            DistributedNode(node_id,"venus"),
            public_key_fingerprint_from_pem_certificate(server_cert),
            datetime.now(timezone.utc),"Sparks",
        )
        transport=PinnedHttpsRemoteTransport(
            lambda _:endpoint,ca_file=ca_path,
            client_certificate=client_cert,client_private_key=client_key,timeout_seconds=3,
        )
        assert transport.authenticate(enrollment)
        inventory=transport.discover(enrollment)
        assert inventory.advertises("system.inspect","system")
        request=RemoteOperationRequest(uuid4(),node_id,uuid4(),"system.inspect","system",{})
        first=transport.execute(enrollment,request)
        second=transport.execute(enrollment,request)
        assert first.outcome is RemoteOutcome.REPORTED_SUCCESS
        assert second.outcome is RemoteOutcome.REPORTED_SUCCESS
        assert counter["value"]==1
    finally:
        server.close(); thread.join(timeout=2)


def test_host_observer_publishes_dispatch_bound_effect_over_pinned_mtls(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"sofia-client","client")
    node_id=uuid4(); port=_free_port()
    dispatcher=RemoteAgentDispatcher()
    dispatcher.register(
        "container.inspect","summary",lambda _:{"containers":[]},
        effect_observer=lambda _parameters,_result:"performed",
    )
    dispatcher.register(
        "container.inspect","broken-observer",lambda _:{"containers":[]},
        effect_observer=lambda _parameters,_result:(_ for _ in ()).throw(
            RuntimeError("observer unavailable")
        ),
    )
    server=RemoteAgentServer(RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(client_cert),
        ledger_path=tmp_path/"agent-ledger.db",
        effect_attestation_root=tmp_path/"host-operations",
    ),dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        endpoint=NodeEndpoint("localhost",port,NodeTransport.HTTPS)
        enrollment=NodeEnrollment(
            DistributedNode(node_id,"venus"),
            public_key_fingerprint_from_pem_certificate(server_cert),
            datetime.now(timezone.utc),"Sparks",
        )
        transport=PinnedHttpsRemoteTransport(
            lambda _:endpoint,ca_file=ca_path,
            client_certificate=client_cert,client_private_key=client_key,
            timeout_seconds=3,
        )
        context=CapabilityDispatchContext(
            "goal-action:exact","goal:exact","remote.container.summary",
            "person:sparks","private:local:text",
        )
        result=transport.execute(enrollment,RemoteOperationRequest(
            uuid4(),node_id,uuid4(),"container.inspect","summary",{},context,
        ))
        assert result.outcome is RemoteOutcome.REPORTED_SUCCESS
        row=transport.host_effect(enrollment,context.dispatch_id)
        assert row["goal_id"]==context.goal_id
        assert row["capability"]==context.capability
        assert row["outcome"]=="performed"
        assert row["attested_by"]==f"fleet-node:{node_id}"

        # An ordinary operation without reserved GOALS identity cannot create
        # evidence that later authorizes reconciliation.
        transport.execute(enrollment,RemoteOperationRequest(
            uuid4(),node_id,uuid4(),"container.inspect","summary",{},
        ))
        with pytest.raises(HttpsTransportError,match="404"):
            transport.host_effect(enrollment,"goal-action:not-reserved")

        broken=CapabilityDispatchContext(
            "goal-action:observer-failed","goal:exact",
            "remote.container.summary","person:sparks","private:local:text",
        )
        uncertain=transport.execute(enrollment,RemoteOperationRequest(
            uuid4(),node_id,uuid4(),"container.inspect","broken-observer",{},broken,
        ))
        assert uncertain.outcome is RemoteOutcome.UNKNOWN
        with pytest.raises(HttpsTransportError,match="404"):
            transport.host_effect(enrollment,broken.dispatch_id)
    finally:
        server.close(); thread.join(timeout=2)


def test_production_fleet_service_verifies_only_exact_host_observed_dispatch(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"controller","client")
    node_id=uuid4(); port=_free_port(); state_path=tmp_path/"sofia.db"
    state_path.touch()
    enroll_node(state_path,node_id=node_id,name="venus",server_certificate=server_cert)
    approve_endpoint(state_path,node_id=node_id,hostname="localhost",port=port)
    grant_operation(
        state_path,node_id=node_id,capability="container.inspect",
        operation="summary",hours=1,
    )
    registry=StatePlaneFleetRegistry(
        SQLiteStatePlane(state_path),legacy_path=state_path.parent/"fleet.json",
    )
    registry.register_candidate(FleetHost(
        "venus","unknown","unknown",HostLifecycle.CANDIDATE,False,
    ))
    registry.authenticate_candidate("venus",node_id)
    registry.transition("venus",HostLifecycle.ENROLLED)

    dispatcher=RemoteAgentDispatcher()
    dispatcher.register(
        "container.inspect","summary",lambda _:{"containers":[]},
        effect_observer=lambda _parameters,_result:"performed",
    )
    server=RemoteAgentServer(RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(client_cert),
        ledger_path=tmp_path/"agent-ledger.db",
        effect_attestation_root=tmp_path/"host-operations",
    ),dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    service=RemoteFleetToolService(
        state_path,ca_file=ca_path,client_certificate=client_cert,
        client_private_key=client_key,
    )
    context=CapabilityDispatchContext(
        "goal-action:production","goal:production","remote.container.summary",
        "person:sparks","private:local:text",
    )
    try:
        result=service.invoke(
            str(node_id),"container.inspect","summary",{},
            dispatch_context=context,
        )
        assert result["outcome"]=="reported_success"
        observed=service.observe_goal_dispatch(
            context.dispatch_id,principal=local_sparks_principal(),
            now=datetime.now(timezone.utc),
        )
        assert observed.kind=="operation_receipt"
        assert observed.source==f"fleet-host-effect:{node_id}"
        assert observed.goal_id==context.goal_id
        assert observed.action_id==context.dispatch_id
        assert observed.successful is True
        assert service.verify_goal_dispatch(context.dispatch_id,observed) is True
        assert service.verify_goal_dispatch(
            context.dispatch_id,
            SimpleNamespace(
                goal_id=observed.goal_id,assertion=observed.assertion,
                principal_id=observed.principal_id,audience=observed.audience,
                successful=True,
                observed_at=observed.observed_at+timedelta(seconds=1),
            ),
        ) is False
        with pytest.raises(ValueError,match="stale"):
            service.observe_goal_dispatch(
                context.dispatch_id,principal=local_sparks_principal(),
                now=datetime.now(timezone.utc)+timedelta(minutes=16),
            )
        assert service.verify_goal_dispatch(
            context.dispatch_id,
            SimpleNamespace(
                goal_id=observed.goal_id,assertion=observed.assertion,
                principal_id=observed.principal_id,audience="private:other",
                successful=observed.successful,observed_at=observed.observed_at,
            ),
        ) is False
        retire_node(state_path,node_id)
        assert service.verify_goal_dispatch(context.dispatch_id,observed) is False
    finally:
        service.close(); server.close(); thread.join(timeout=2)


def test_goals_safe_reconciles_real_mtls_host_observation_after_lost_response(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"controller","client")
    node_id=uuid4(); port=_free_port(); state_path=tmp_path/"sofia.db"
    state_path.touch()
    enroll_node(state_path,node_id=node_id,name="venus",server_certificate=server_cert)
    approve_endpoint(state_path,node_id=node_id,hostname="localhost",port=port)
    grant_operation(
        state_path,node_id=node_id,capability="container.inspect",
        operation="summary",hours=1,
    )
    registry=StatePlaneFleetRegistry(
        SQLiteStatePlane(state_path),legacy_path=state_path.parent/"fleet.json",
    )
    registry.register_candidate(FleetHost(
        "venus","unknown","unknown",HostLifecycle.CANDIDATE,False,
    ))
    registry.authenticate_candidate("venus",node_id)
    registry.transition("venus",HostLifecycle.ENROLLED)
    dispatcher=RemoteAgentDispatcher()
    dispatcher.register(
        "container.inspect","summary",lambda _:{"containers":[]},
        effect_observer=lambda _parameters,_result:"performed",
    )
    server=RemoteAgentServer(RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(client_cert),
        ledger_path=tmp_path/"agent-ledger.db",
        effect_attestation_root=tmp_path/"host-operations",
    ),dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    service=RemoteFleetToolService(
        state_path,ca_file=ca_path,client_certificate=client_cert,
        client_private_key=client_key,
    )
    principal=local_sparks_principal()
    capabilities=CapabilitySystem(authorization_checker=lambda _request:True)
    def execute_then_lose_response(request):
        service.invoke(
            request.parameters["node_id"],"container.inspect","summary",{},
            dispatch_context=request.dispatch_context,
        )
        raise ConnectionError("simulated response loss after host observation")
    capabilities.register(
        Capability("remote.container.summary","Inspect enrolled remote containers."),
        execute_then_lose_response,
    )
    goals=GoalService(
        GoalStore(SQLiteStatePlane(state_path)),
        evidence_verifier=GoalEvidenceIndex(state_path),
    )
    safe=ExecutionApprovalVerifier(state_path)
    production=GoalProductionCoordinator(
        goals=goals,state_path=state_path,gateway=CapabilityGateway(capabilities),
        principal_provider=lambda:principal,neuro_provider=lambda:None,
        reconciliation_approval_verifier=safe,
        independent_outcome_verifier=service.verify_goal_dispatch,
    )
    ledger=GoalEvidenceLedger(state_path)
    now=datetime.now(timezone.utc)
    message=ledger.record(
        evidence_ref="message:mtls-closed-loop",kind="authenticated_user_message",
        observed_at=now,source="test-owner-channel",
        principal_id=principal.principal_id,audience="private:local:text",
    )
    fleet=ledger.record(
        evidence_ref="goal-evidence:fleet:mtls-closed-loop",
        kind="external_observation",observed_at=now,
        source="fleet-observation:authenticated-venus",assertion="machine.os",
        payload={"node_id":str(node_id),"value":"linux"},
        principal_id=principal.principal_id,audience="private:local:text",
    )
    goal=goals.create_user_goal(
        principal=principal,title="Investigate Docker on enrolled host",
        reason="Authenticated Fleet evidence requires host diagnostics.",
        base_priority=0.7,confidence=1.0,
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED,"Owner reviews the host outcome.",
        ),evidence_refs=(message.evidence_ref,fleet.evidence_ref),now=now,
    )
    try:
        assert production.run_due(now=now)==1
        dispatch_id,capability=production.unresolved_dispatches(goal.id)[0]
        assert capability=="remote.container.summary"
        verification_now=datetime.now(timezone.utc)
        outcome=service.observe_goal_dispatch(
            dispatch_id,principal=principal,now=verification_now,
        )
        approval_now=datetime.now(timezone.utc)
        approval=ExecutionApproval(
            approval_id="approval:mtls-closed-loop",
            capability="goals.dispatch.reconcile",
            request_fingerprint=execution_fingerprint(
                "goals.dispatch.reconcile",
                goal_reconciliation_approval_parameters(
                    goal=goal,dispatch_id=dispatch_id,capability=capability,
                    evidence=outcome,
                ),
            ),approved_by="Sparks",approved_at=approval_now,
            expires_at=approval_now+timedelta(minutes=5),
        )
        record_verified_owner_approval(safe,approval)
        assert production.reconcile_dispatch(
            goal_id=goal.id,dispatch_id=dispatch_id,principal=principal,
            evidence_ref=outcome.evidence_ref,approval_id=approval.approval_id,
            now=datetime.now(timezone.utc),
        )=="effect_verified"
        assert production.reconciliations(goal.id)==(
            (dispatch_id,"effect_verified",outcome.evidence_ref),
        )
    finally:
        service.close(); server.close(); thread.join(timeout=2)


def test_agent_rejects_mutual_tls_client_with_wrong_pinned_public_key(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    approved_cert,approved_key=_leaf(tmp_path,ca_key,ca_cert,"approved-client","client")
    other_cert,other_key=_leaf(tmp_path,ca_key,ca_cert,"other-client","client")
    node_id=uuid4(); port=_free_port()
    dispatcher=RemoteAgentDispatcher(); dispatcher.register("system.inspect","system",lambda p:{"ok":True})
    server=RemoteAgentServer(RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(approved_cert),
        ledger_path=tmp_path/"ledger.db",
    ),dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        endpoint=NodeEndpoint("localhost",port,NodeTransport.HTTPS)
        enrollment=NodeEnrollment(DistributedNode(node_id,"venus"),
            public_key_fingerprint_from_pem_certificate(server_cert),datetime.now(timezone.utc),"Sparks")
        wrong=PinnedHttpsRemoteTransport(lambda _:endpoint,ca_file=ca_path,
            client_certificate=other_cert,client_private_key=other_key,timeout_seconds=3)
        assert wrong.authenticate(enrollment) is False
    finally:
        server.close(); thread.join(timeout=2)


def test_transport_rejects_server_key_not_matching_enrollment_pin(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    different_cert,different_key=_leaf(tmp_path,ca_key,ca_cert,"different","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"client","client")
    node_id=uuid4(); port=_free_port()
    dispatcher=RemoteAgentDispatcher(); dispatcher.register("system.inspect","system",lambda p:{"ok":True})
    server=RemoteAgentServer(RemoteAgentConfig(
        node_id=node_id,node_name="venus",listen_host="127.0.0.1",listen_port=port,
        server_certificate=server_cert,server_private_key=server_key,client_ca_file=ca_path,
        expected_client_public_key_sha256=public_key_fingerprint_from_pem_certificate(client_cert),
        ledger_path=tmp_path/"ledger.db",
    ),dispatcher)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        endpoint=NodeEndpoint("localhost",port,NodeTransport.HTTPS)
        enrollment=NodeEnrollment(DistributedNode(node_id,"venus"),
            public_key_fingerprint_from_pem_certificate(different_cert),datetime.now(timezone.utc),"Sparks")
        transport=PinnedHttpsRemoteTransport(lambda _:endpoint,ca_file=ca_path,
            client_certificate=client_cert,client_private_key=client_key,timeout_seconds=3)
        assert transport.authenticate(enrollment) is False
    finally:
        server.close(); thread.join(timeout=2)


def test_operator_provisions_exact_node_endpoint_grant_and_retirement(tmp_path:Path):
    ca_key,ca_cert,ca_path=_ca(tmp_path)
    server_cert,server_key=_leaf(tmp_path,ca_key,ca_cert,"localhost","server")
    client_cert,client_key=_leaf(tmp_path,ca_key,ca_cert,"controller","client")
    state_path=tmp_path/"sofia.db"; state_path.touch()
    node_id=uuid4()
    enroll_node(state_path,node_id=node_id,name="venus",server_certificate=server_cert)
    approve_endpoint(state_path,node_id=node_id,hostname="localhost",port=7443)
    grant=grant_operation(state_path,node_id=node_id,capability="system.inspect",operation="system",hours=1)

    # Remote control now requires active trusted OPS Fleet membership in
    # addition to durable node identity/endpoint records.
    registry=StatePlaneFleetRegistry(
        SQLiteStatePlane(state_path),
        legacy_path=state_path.parent/"fleet.json",
    )
    registry.register_candidate(FleetHost(
        "venus","unknown","unknown",HostLifecycle.CANDIDATE,False
    ))
    registry.authenticate_candidate("venus",node_id)
    registry.transition("venus",HostLifecycle.ENROLLED)

    service=RemoteFleetToolService(
        state_path,ca_file=ca_path,client_certificate=client_cert,client_private_key=client_key
    )
    try:
        nodes=service.nodes()
        assert len(nodes)==1
        assert nodes[0]["node_id"]==str(node_id)
        assert nodes[0]["endpoint"]["hostname"]=="localhost"
        assert nodes[0]["authorized_operations"][0]["capability"]=="system.inspect"
        assert nodes[0]["authorized_operations"][0]["operation"]=="system"
    finally:
        service.close()
    retire_node(state_path,node_id)
    service=RemoteFleetToolService(
        state_path,ca_file=ca_path,client_certificate=client_cert,client_private_key=client_key
    )
    try:
        assert service.nodes()==()
    finally:
        service.close()


def test_agent_replay_id_cannot_be_rebound_to_different_operation(tmp_path:Path):
    from sofia.platform.distributed.agent import AgentRequestLedger
    from sofia.platform.distributed.operations import RemoteOutcome
    node_id=uuid4(); request_id=uuid4()
    ledger=AgentRequestLedger(tmp_path/"ledger.db")
    try:
        assert ledger.reserve(request_id,node_id,"system.inspect","system") is None
        ledger.finish(request_id,RemoteOutcome.REPORTED_SUCCESS,"ok")
        with __import__("pytest").raises(PermissionError):
            ledger.reserve(request_id,node_id,"service.manage","restart")
    finally:
        ledger.close()


def test_agent_parameter_firewall_rejects_execution_and_secret_fields():
    from sofia.platform.distributed.agent import _bounded_parameters
    import pytest
    for key in ("command","shell","argv","token","private_key"):
        with pytest.raises(ValueError):
            _bounded_parameters({key:"x"})
    with pytest.raises(TypeError):
        _bounded_parameters({"nested":{"x":1}})
    with pytest.raises(ValueError):
        _bounded_parameters({"ratio":float("inf")})
