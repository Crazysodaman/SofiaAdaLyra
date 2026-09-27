from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import sofia.distributed.fleet_probe as probe_module
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.fleet_probe import FleetNodeProbe, _parameters, _paths
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.operations import RemoteOutcome


NODE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
PIN = "b" * 64
NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


def _state(tmp_path: Path) -> Path:
    path = tmp_path / "sofia.db"
    path.touch()
    return path


def _provision(state_path: Path) -> None:
    paths = _paths(state_path)
    identity = DurableNodeIdentityRegistry(paths["identity"])
    endpoint = DurableEndpointPolicy(paths["endpoint"])
    try:
        identity.enroll(
            NodeEnrollment(
                DistributedNode(NODE_ID, "Artemis"),
                PIN,
                NOW,
                "Sparks",
            )
        )
        endpoint.approve(
            ApprovedEndpoint(
                NODE_ID,
                NodeEndpoint("artemis.local", 7443, NodeTransport.HTTPS),
                "Sparks",
            )
        )
    finally:
        identity.close()
        endpoint.close()


def _probe(state_path: Path) -> FleetNodeProbe:
    return FleetNodeProbe(
        state_path=state_path,
        node_id=NODE_ID,
        ca_file=Path("ca.pem"),
        client_certificate=Path("client.pem"),
        client_private_key=Path("client-key.pem"),
    )


def test_probe_requires_durable_active_enrollment(tmp_path):
    state = _state(tmp_path)

    with pytest.raises(LookupError, match="not actively enrolled"):
        _probe(state)


def test_probe_uses_durable_enrollment_and_exact_endpoint(tmp_path):
    state = _state(tmp_path)
    _provision(state)

    probe = _probe(state)

    assert probe.enrollment.node.node_id == NODE_ID
    assert probe.enrollment.node.name == "Artemis"
    assert probe.endpoint == NodeEndpoint(
        "artemis.local",
        7443,
        NodeTransport.HTTPS,
    )


def test_invoke_refuses_without_active_exact_grant(tmp_path):
    state = _state(tmp_path)
    _provision(state)
    probe = _probe(state)

    with pytest.raises(
        PermissionError,
        match="no active exact grant for system.inspect/system",
    ):
        probe.invoke(
            capability="system.inspect",
            operation="system",
            parameters={},
        )


def test_invoke_uses_active_exact_grant_and_durable_control(tmp_path, monkeypatch):
    state = _state(tmp_path)
    _provision(state)
    paths = _paths(state)
    authorization = DurableRemoteAuthorization(paths["grant"])
    grant = RemoteGrant(
        uuid4(),
        NODE_ID,
        "system.inspect",
        "system",
        "Sparks",
        NOW + timedelta(days=365),
    )
    try:
        authorization.add_approved_grant(grant)
    finally:
        authorization.close()

    captured = {}

    class FakeControl:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def invoke(self, enrollment, endpoint, request, *, now):
            captured["enrollment"] = enrollment
            captured["endpoint"] = endpoint
            captured["request"] = request
            captured["now"] = now
            return SimpleNamespace(
                request_id=request.request_id,
                node_id=request.node_id,
                outcome=RemoteOutcome.REPORTED_SUCCESS,
                message="ok",
            )

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(probe_module, "DurableRemoteControl", FakeControl)
    probe = _probe(state)

    result = probe.invoke(
        capability="system.inspect",
        operation="system",
        parameters={},
    )

    assert result.outcome is RemoteOutcome.REPORTED_SUCCESS
    assert captured["request"].grant_id == grant.grant_id
    assert captured["request"].capability == "system.inspect"
    assert captured["request"].operation == "system"
    assert captured["closed"] is True


def test_parameter_parser_preserves_bounded_scalar_types():
    assert _parameters(
        [
            "limit=20",
            "force=false",
            "ratio=1.5",
            "note=venus",
            "empty=null",
        ]
    ) == {
        "limit": 20,
        "force": False,
        "ratio": 1.5,
        "note": "venus",
        "empty": None,
    }


def test_parameter_parser_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="duplicate parameter"):
        _parameters(["limit=1", "limit=2"])
