import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import UUID

import pytest
from cryptography import x509

from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.model import NodeTransport
from sofia.distributed.pki import _refuse_network_secret_root, bootstrap_pair
from sofia.ops.windows_rekey_bootstrap import (
    _enroll_fresh_controller,
    _prepare_bundle,
)


NODE_ID = UUID("cedf5c64-f3f5-46e0-8c5b-4f85089fcaba")


@pytest.fixture
def local_tmp_path(tmp_path: Path):
    resolved = tmp_path.resolve()
    if not str(resolved).startswith("\\\\"):
        yield resolved
        return

    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    root = Path(tempfile.mkdtemp(prefix="sofia-rekey-test-", dir=base))
    try:
        _refuse_network_secret_root(root.resolve())
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_bundle_rewrites_port_and_client_pin(local_tmp_path: Path):
    pki = bootstrap_pair(
        output_directory=local_tmp_path / "pki",
        server_name="Artemis",
        server_dns_names=("Artemis", "Artemis.local"),
        server_ip_addresses=("192.168.1.55",),
        controller_name="Venus",
    )
    template = local_tmp_path / "agent.json"
    template.write_text(
        json.dumps(
            {
                "node_id": str(NODE_ID),
                "node_name": "Artemis",
                "listen_host": "0.0.0.0",
                "listen_port": 7443,
                "server_certificate": "certs/old-server.pem",
                "server_private_key": "certs/old-key.pem",
                "client_ca_file": "certs/old-ca.pem",
                "expected_client_public_key_sha256": "0" * 64,
                "ledger_path": "state/agent-ledger.db",
            }
        ),
        encoding="utf-8",
    )

    bundle, payload = _prepare_bundle(
        template_config=template,
        output_directory=local_tmp_path / "bundle",
        pki_result=pki,
        listen_port=9999,
    )

    assert payload["listen_port"] == 9999
    assert payload["expected_client_public_key_sha256"] == pki[
        "controller_public_key_sha256"
    ]
    assert payload["server_certificate"] == "certs/artemis-server.pem"
    assert payload["server_private_key"] == "certs/artemis-server-key.pem"
    assert payload["client_ca_file"] == "certs/fleet-ca.pem"
    assert (bundle / "certs" / "artemis-server.pem").read_bytes() == Path(
        pki["server_certificate"]
    ).read_bytes()
    assert (bundle / "certs" / "artemis-server-key.pem").read_bytes() == Path(
        pki["server_private_key"]
    ).read_bytes()


def test_strict_pki_leafs_have_authority_key_identifier(local_tmp_path: Path):
    pki = bootstrap_pair(
        output_directory=local_tmp_path / "pki",
        server_name="Artemis",
        server_dns_names=("Artemis", "Artemis.local"),
        server_ip_addresses=("192.168.1.55",),
        controller_name="Venus",
    )

    ca = x509.load_pem_x509_certificate(Path(pki["ca_certificate"]).read_bytes())
    ca_ski = ca.extensions.get_extension_for_class(
        x509.SubjectKeyIdentifier
    ).value.digest

    for key in ("controller_certificate", "server_certificate"):
        cert = x509.load_pem_x509_certificate(Path(pki[key]).read_bytes())
        aki = cert.extensions.get_extension_for_class(
            x509.AuthorityKeyIdentifier
        ).value
        assert aki.key_identifier == ca_ski


def test_fresh_controller_enrollment_uses_new_server_pin_and_endpoint(local_tmp_path: Path):
    pki = bootstrap_pair(
        output_directory=local_tmp_path / "pki",
        server_name="Artemis",
        server_dns_names=("Artemis", "Artemis.local"),
        server_ip_addresses=("192.168.1.55",),
        controller_name="Venus",
    )
    state_path = local_tmp_path / "controller" / "state.db"

    _enroll_fresh_controller(
        state_path=state_path,
        node_id=NODE_ID,
        node_name="Artemis",
        server_certificate=Path(pki["server_certificate"]),
        endpoint_hostname="192.168.1.55",
        endpoint_port=9999,
        approved_by="Sparks",
    )

    identities = DurableNodeIdentityRegistry(state_path)
    endpoints = DurableEndpointPolicy(state_path)
    try:
        enrollment = identities.get(NODE_ID)
        endpoint = endpoints.get(NODE_ID)
    finally:
        identities.close()
        endpoints.close()

    assert enrollment is not None
    assert enrollment.public_key_sha256 == pki["server_public_key_sha256"]
    assert endpoint is not None
    assert endpoint.hostname == "192.168.1.55"
    assert endpoint.port == 9999
    assert endpoint.transport is NodeTransport.HTTPS
