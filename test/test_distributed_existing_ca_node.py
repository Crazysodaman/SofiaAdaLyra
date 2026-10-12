"""Enrollment-ready node credentials must not replace Artemis or Venus keys."""
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from sofia.distributed import pki


def test_new_sofia_node_gets_distinct_leaf_keys_under_existing_ca(tmp_path):
    ca_cert = tmp_path / "operator" / "ca.pem"
    ca_key = tmp_path / "operator" / "ca-private.pem"
    pki.create_ca(certificate_path=ca_cert, private_key_path=ca_key)
    before = ca_key.read_bytes()
    new_node = tmp_path / "new-identity"
    output = pki.issue_node_pair_from_existing_ca(
        ca_certificate_path=ca_cert,
        ca_private_key_path=ca_key,
        output_directory=new_node,
        node_name="Sofia",
        server_dns_names=("Sofia",),
        server_ip_addresses=("192.168.1.68",),
    )
    assert ca_key.read_bytes() == before
    assert not (new_node / ca_key.name).exists()
    assert Path(output["ca_certificate"]).read_bytes() == ca_cert.read_bytes()
    assert output["server_public_key_sha256"] != output["client_public_key_sha256"]
    assert len(output["server_public_key_sha256"]) == 64

    server = x509.load_pem_x509_certificate(
        Path(output["server_certificate"]).read_bytes()
    )
    client = x509.load_pem_x509_certificate(
        Path(output["client_certificate"]).read_bytes()
    )
    sans = server.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert IPv4Address("192.168.1.68") in sans.get_values_for_type(x509.IPAddress)
    server_eku = server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    client_eku = client.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert ExtendedKeyUsageOID.SERVER_AUTH in server_eku
    assert ExtendedKeyUsageOID.CLIENT_AUTH not in server_eku
    assert ExtendedKeyUsageOID.CLIENT_AUTH in client_eku
    assert ExtendedKeyUsageOID.SERVER_AUTH not in client_eku
    with pytest.raises(FileExistsError):
        pki.issue_node_pair_from_existing_ca(
            ca_certificate_path=ca_cert,
            ca_private_key_path=ca_key,
            output_directory=new_node,
            node_name="Sofia",
            server_dns_names=("Sofia",),
            server_ip_addresses=("192.168.1.68",),
        )


@pytest.mark.parametrize("unsafe", ["", "Venus", "Artemis", "../Sofia", "a b"])
def test_existing_ca_enrollment_rejects_unsafe_node_name(tmp_path, unsafe):
    with pytest.raises(ValueError):
        pki.issue_node_pair_from_existing_ca(
            ca_certificate_path=tmp_path / "not-needed-cert",
            ca_private_key_path=tmp_path / "not-needed-key",
            output_directory=tmp_path / "new-identity",
            node_name=unsafe,
            server_dns_names=("Sofia",),
            server_ip_addresses=("192.168.1.68",),
        )
