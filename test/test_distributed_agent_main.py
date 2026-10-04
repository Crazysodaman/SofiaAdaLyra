import json
from pathlib import Path
from uuid import UUID

import pytest

from sofia.distributed.agent_main import configuration_from_file


NODE_ID = UUID("11111111-2222-3333-4444-555555555555")
PIN = "a" * 64


def _write_config(tmp_path: Path, **overrides) -> Path:
    payload = {
        "node_id": str(NODE_ID),
        "node_name": "Artemis",
        "listen_host": "0.0.0.0",
        "listen_port": 7443,
        "server_certificate": "certs/artemis-server.pem",
        "server_private_key": "certs/artemis-server-key.pem",
        "client_ca_file": "certs/fleet-ca.pem",
        "expected_client_public_key_sha256": PIN,
        "ledger_path": "state/agent-ledger.db",
    }
    payload.update(overrides)
    path = tmp_path / "agent.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_file_config_resolves_relative_paths_from_config_directory(tmp_path):
    path = _write_config(tmp_path)

    config = configuration_from_file(path)

    assert config.node_id == NODE_ID
    assert config.node_name == "Artemis"
    assert config.listen_port == 7443
    assert config.server_certificate == (
        tmp_path / "certs" / "artemis-server.pem"
    ).resolve()
    assert config.server_private_key == (
        tmp_path / "certs" / "artemis-server-key.pem"
    ).resolve()
    assert config.client_ca_file == (
        tmp_path / "certs" / "fleet-ca.pem"
    ).resolve()
    assert config.ledger_path == (
        tmp_path / "state" / "agent-ledger.db"
    ).resolve()


def test_file_config_rejects_unknown_keys(tmp_path):
    path = _write_config(tmp_path, surprise="nope")

    with pytest.raises(ValueError, match="Unsupported Fleet agent config keys"):
        configuration_from_file(path)


def test_file_config_rejects_missing_required_key(tmp_path):
    path = _write_config(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["server_private_key"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="server_private_key"):
        configuration_from_file(path)


def test_file_config_defaults_listener_when_omitted(tmp_path):
    path = _write_config(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["listen_host"]
    del payload["listen_port"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    config = configuration_from_file(path)

    assert config.listen_host == "0.0.0.0"
    assert config.listen_port == 7443


def test_file_config_accepts_utf8_bom(tmp_path):
    path = _write_config(tmp_path)
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw, encoding="utf-8-sig")

    config = configuration_from_file(path)

    assert config.node_id == NODE_ID
    assert config.node_name == "Artemis"



def test_file_config_inference_is_opt_in_and_model_names_are_owner_data(tmp_path):
    path = _write_config(
        tmp_path,
        inference_models=[
            "vendor/primary:anything",
            "vendor/secondary:anything",
        ],
        inference_max_context_size=24576,
        inference_allow_tools=False,
    )

    config = configuration_from_file(path)

    assert config.inference_models == (
        "vendor/primary:anything",
        "vendor/secondary:anything",
    )
    assert config.inference_max_context_size == 24576
    assert config.inference_allow_tools is False


def test_file_config_defaults_to_no_remote_inference(tmp_path):
    config = configuration_from_file(_write_config(tmp_path))

    assert config.inference_models == ()
    assert config.inference_max_context_size == 65536
    assert config.inference_allow_tools is True


def test_file_config_rejects_duplicate_inference_models(tmp_path):
    path = _write_config(
        tmp_path,
        inference_models=["vendor/model:any","vendor/model:any"],
    )

    with pytest.raises(ValueError, match="duplicates"):
        configuration_from_file(path)


def test_file_config_release_management_is_opt_in_and_resolves_paths(tmp_path):
    path = _write_config(
        tmp_path,
        release_state_path="state/sofia.db",
        release_root="runtime/releases",
        release_inbox="releases/inbox",
        release_trusted_key_file="certs/release-public.pem",
        release_trusted_key_id="production-release",
    )

    config = configuration_from_file(path)

    assert config.release_state_path == (tmp_path / "state" / "sofia.db").resolve()
    assert config.release_root == (tmp_path / "runtime" / "releases").resolve()
    assert config.release_inbox == (tmp_path / "releases" / "inbox").resolve()
    assert config.release_trusted_key_file == (
        tmp_path / "certs" / "release-public.pem"
    ).resolve()
    assert config.release_trusted_key_id == "production-release"


def test_file_config_rejects_partial_release_management(tmp_path):
    path = _write_config(
        tmp_path,
        release_state_path="state/sofia.db",
        release_inbox="releases/inbox",
    )

    with pytest.raises(ValueError, match="release management requires"):
        configuration_from_file(path)


def test_file_config_rejects_null_release_signer_id(tmp_path):
    path = _write_config(
        tmp_path,
        release_state_path="state/sofia.db",
        release_inbox="releases/inbox",
        release_trusted_key_file="certs/release-public.pem",
        release_trusted_key_id=None,
    )

    with pytest.raises(ValueError, match="release management requires"):
        configuration_from_file(path)
