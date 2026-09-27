import os
from pathlib import Path
import shutil
import tempfile

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from sofia.distributed.pki import _refuse_network_secret_root, bootstrap_pair
from sofia.distributed.tls import public_key_fingerprint_from_pem_certificate


@pytest.fixture
def local_tmp_path(local_tmp_path: Path):
    resolved = tmp_path.resolve()
    if not str(resolved).startswith("\\\\"):
        yield resolved
        return

    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    root = Path(tempfile.mkdtemp(prefix="sofia-pki-test-", dir=base))
    try:
        _refuse_network_secret_root(root.resolve())
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)



def test_bootstrap_pair_creates_ca_client_and_server_material(local_tmp_path: Path):
    result = bootstrap_pair(
        output_directory=local_tmp_path / "fleet-pki",
        server_name="Artemis",
        server_dns_names=("Artemis", "artemis.local"),
        controller_name="Venus",
    )

    ca_cert = Path(result["ca_certificate"])
    controller_cert = Path(result["controller_certificate"])
    controller_key = Path(result["controller_private_key"])
    server_cert = Path(result["server_certificate"])
    server_key = Path(result["server_private_key"])

    assert ca_cert.is_file()
    assert controller_cert.is_file()
    assert controller_key.is_file()
    assert server_cert.is_file()
    assert server_key.is_file()

    ca = x509.load_pem_x509_certificate(ca_cert.read_bytes())
    assert ca.extensions.get_extension_for_class(
        x509.BasicConstraints
    ).value.ca is True

    controller = x509.load_pem_x509_certificate(controller_cert.read_bytes())
    controller_eku = controller.extensions.get_extension_for_class(
        x509.ExtendedKeyUsage
    ).value
    assert ExtendedKeyUsageOID.CLIENT_AUTH in controller_eku
    assert ExtendedKeyUsageOID.SERVER_AUTH not in controller_eku

    server = x509.load_pem_x509_certificate(server_cert.read_bytes())
    server_eku = server.extensions.get_extension_for_class(
        x509.ExtendedKeyUsage
    ).value
    assert ExtendedKeyUsageOID.SERVER_AUTH in server_eku
    assert ExtendedKeyUsageOID.CLIENT_AUTH not in server_eku

    sans = server.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert set(sans.get_values_for_type(x509.DNSName)) == {
        "Artemis",
        "artemis.local",
    }


def test_bootstrap_pair_returns_spki_fingerprints(local_tmp_path: Path):
    result = bootstrap_pair(
        output_directory=local_tmp_path / "fleet-pki",
        server_name="Artemis",
        server_dns_names=("Artemis",),
    )

    assert result["controller_public_key_sha256"] == (
        public_key_fingerprint_from_pem_certificate(
            result["controller_certificate"]
        )
    )
    assert result["server_public_key_sha256"] == (
        public_key_fingerprint_from_pem_certificate(
            result["server_certificate"]
        )
    )
    assert len(result["controller_public_key_sha256"]) == 64
    assert len(result["server_public_key_sha256"]) == 64


def test_bootstrap_pair_refuses_implicit_key_replacement(local_tmp_path: Path):
    root = local_tmp_path / "fleet-pki"
    bootstrap_pair(
        output_directory=root,
        server_name="Artemis",
        server_dns_names=("Artemis",),
    )

    with pytest.raises(FileExistsError, match="implicit key replacement"):
        bootstrap_pair(
            output_directory=root,
            server_name="Artemis",
            server_dns_names=("Artemis",),
        )


def test_bootstrap_pair_can_include_server_ip_san(local_tmp_path: Path):
    result = bootstrap_pair(
        output_directory=local_tmp_path / "fleet-pki",
        server_name="Artemis",
        server_dns_names=("Artemis",),
        server_ip_addresses=("192.0.2.44",),
    )

    server = x509.load_pem_x509_certificate(
        Path(result["server_certificate"]).read_bytes()
    )
    sans = server.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert str(sans.get_values_for_type(x509.IPAddress)[0]) == "192.0.2.44"


def test_refuse_network_secret_root():
    with pytest.raises(ValueError, match="local storage"):
        _refuse_network_secret_root(Path(r"\\\\Artemis\\Hestia\\fleet-pki"))
