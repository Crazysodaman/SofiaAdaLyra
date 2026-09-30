from datetime import datetime, timezone
from uuid import UUID

import sofia.ops.discovery_canary as canary
from sofia.ops.discovery import FleetDiscoveryEvidence


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
NODE = UUID("11111111-2222-3333-4444-555555555555")


class FakeSource:
    def __init__(self, observations):
        self.observations = observations

    def discover(self):
        return self.observations


def observation():
    return FleetDiscoveryEvidence(
        host_id="Artemis",
        hostname="artemis.local",
        platform="windows",
        architecture="amd64",
        observed_at=NOW,
        source="mtls-agent-discovery",
        inside_approved_scope=True,
        installed_protocol_version="1.0",
        observed_node_id=NODE,
        observed_public_key_sha256="a" * 64,
        observed_endpoint_hostname="artemis.local",
        observed_endpoint_port=9999,
        capabilities_verified=True,
        capability_names=("ops.telemetry", "system.inspect"),
    )


def test_read_only_canary_creates_only_in_memory_untrusted_candidate():
    result = canary.preview_candidate(FakeSource((observation(),)))

    assert result["status"] == "verified_agent_observed_untrusted_candidate"
    assert result["host_id"] == "Artemis"
    assert result["node_id"] == str(NODE)
    assert result["capabilities_verified"] is True
    assert result["candidate_created_in_memory"] is True
    assert result["candidate_trusted"] is False
    assert result["enrolled"] is False
    assert result["persistent_changes"] is False


def test_canary_reports_no_agent_without_enrolling():
    result = canary.preview_candidate(FakeSource(()))

    assert result == {
        "status": "no_verified_agent_observed",
        "persistent_changes": False,
    }


def test_canary_requires_existing_credential_paths(tmp_path, capsys):
    status = canary.main(
        [
            "--host", "Artemis",
            "--ca-file", str(tmp_path / "missing-ca"),
            "--client-cert", str(tmp_path / "missing-cert"),
            "--client-key", str(tmp_path / "missing-key"),
        ]
    )

    assert status == 2
    assert '"status": "canary_error"' in capsys.readouterr().out


def test_canary_expected_node_mismatch_is_explicit_and_read_only(
    tmp_path, monkeypatch, capsys
):
    files = [tmp_path / name for name in ("ca.pem", "client.pem", "key.pem")]
    for path in files:
        path.write_text("synthetic test credential", encoding="utf-8")
    monkeypatch.setattr(
        canary,
        "MtlsAgentDiscoverySource",
        lambda *args, **kwargs: FakeSource((observation(),)),
    )

    status = canary.main(
        [
            "--host", "Artemis",
            "--port", "9999",
            "--ca-file", str(files[0]),
            "--client-cert", str(files[1]),
            "--client-key", str(files[2]),
            "--expected-node-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ]
    )

    output = capsys.readouterr().out
    assert status == 3
    assert '"status": "operator_expected_identity_mismatch"' in output
    assert '"persistent_changes": false' in output
