from __future__ import annotations

from datetime import datetime,timedelta,timezone
from ipaddress import ip_address
from pathlib import Path
import socket
import threading
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID,NameOID

from sofia.distributed.agent import RemoteAgentConfig,RemoteAgentDispatcher,RemoteAgentServer
from sofia.distributed.https_transport import PinnedHttpsRemoteTransport
from sofia.distributed.capability import RemoteFleetToolService
from sofia.distributed.operator import enroll_node,approve_endpoint,grant_operation,retire_node
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import DistributedNode,NodeEndpoint,NodeTransport
from sofia.distributed.operations import RemoteOperationRequest,RemoteOutcome
from sofia.distributed.tls import public_key_fingerprint_from_pem_certificate


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
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True))
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
    from sofia.distributed.agent import AgentRequestLedger
    from sofia.distributed.operations import RemoteOutcome
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
    from sofia.distributed.agent import _bounded_parameters
    import pytest
    for key in ("command","shell","argv","token","private_key"):
        with pytest.raises(ValueError):
            _bounded_parameters({key:"x"})
    with pytest.raises(TypeError):
        _bounded_parameters({"nested":{"x":1}})
    with pytest.raises(ValueError):
        _bounded_parameters({"ratio":float("inf")})
