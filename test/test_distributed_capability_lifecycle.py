from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import sofia.distributed.capability as fleet_capability
from sofia.distributed.capability import RemoteFleetToolService
from sofia.distributed.operations import RemoteOperationResult, RemoteOutcome


def _service(tmp_path: Path) -> RemoteFleetToolService:
    state = tmp_path / "sofia.db"
    state.touch()
    return RemoteFleetToolService(
        state,
        ca_file=tmp_path / "ca.pem",
        client_certificate=tmp_path / "client.pem",
        client_private_key=tmp_path / "client-key.pem",
    )


def test_remote_fleet_service_opens_and_closes_durable_state_per_tool_call(
    tmp_path,
    monkeypatch,
):
    events = []

    class FakeEndpointPolicy:
        def __init__(self, path):
            events.append(("endpoint:open", Path(path).name))

        def get(self, _node_id):
            return None

        def close(self):
            events.append(("endpoint:close", None))

    class FakeTransport:
        def __init__(self, endpoint_lookup, **_kwargs):
            assert callable(endpoint_lookup)
            events.append(("transport:create", None))

    class FakeControl:
        def __init__(self, **_kwargs):
            events.append(("control:open", None))
            self.identities = SimpleNamespace(active=lambda: ())
            self.endpoints = SimpleNamespace(get=lambda _node_id: None)
            self.authorization = SimpleNamespace(
                active_grants_for_node=lambda _node_id, now: ()
            )

        def close(self):
            events.append(("control:close", None))

    monkeypatch.setattr(
        fleet_capability,
        "DurableEndpointPolicy",
        FakeEndpointPolicy,
    )
    monkeypatch.setattr(
        fleet_capability,
        "PinnedHttpsRemoteTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        fleet_capability,
        "DurableRemoteControl",
        FakeControl,
    )

    service = _service(tmp_path)

    # Construction registers a reusable service but owns no live remote DB
    # handles. Those belong only to an individual tool call.
    assert events == []

    assert service.nodes() == ()
    assert events == [
        ("endpoint:open", "sofia.db"),
        ("transport:create", None),
        ("control:open", None),
        ("control:close", None),
        ("endpoint:close", None),
    ]

    events.clear()
    assert service.nodes() == ()
    assert events[-2:] == [
        ("control:close", None),
        ("endpoint:close", None),
    ]


def test_remote_fleet_tool_call_closes_durable_state_on_failure(
    tmp_path,
    monkeypatch,
):
    events = []

    class FakeEndpointPolicy:
        def __init__(self, _path):
            events.append("endpoint:open")

        def get(self, _node_id):
            return None

        def close(self):
            events.append("endpoint:close")

    class FakeTransport:
        def __init__(self, endpoint_lookup, **_kwargs):
            assert callable(endpoint_lookup)

    class FakeControl:
        def __init__(self, **_kwargs):
            events.append("control:open")

            def fail():
                raise RuntimeError("probe failed")

            self.identities = SimpleNamespace(active=fail)

        def close(self):
            events.append("control:close")

    monkeypatch.setattr(
        fleet_capability,
        "DurableEndpointPolicy",
        FakeEndpointPolicy,
    )
    monkeypatch.setattr(
        fleet_capability,
        "PinnedHttpsRemoteTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        fleet_capability,
        "DurableRemoteControl",
        FakeControl,
    )

    service = _service(tmp_path)

    with pytest.raises(RuntimeError, match="probe failed"):
        service.nodes()

    assert events == [
        "endpoint:open",
        "control:open",
        "control:close",
        "endpoint:close",
    ]


def test_enrolled_remote_read_only_inspection_needs_no_human_grant(
    tmp_path,
    monkeypatch,
):
    node_id = uuid4()
    generated_grant = SimpleNamespace(grant_id=uuid4())
    calls = []

    class FakeEndpointPolicy:
        def __init__(self, _path):
            pass

        def get(self, _node_id):
            return SimpleNamespace()

        def close(self):
            pass

    class FakeTransport:
        def __init__(self, endpoint_lookup, **_kwargs):
            assert callable(endpoint_lookup)

    class FakeAuthorization:
        def find_active(self, *, node_id, capability, operation, now):
            calls.append(("find", node_id, capability, operation))
            return None

        def ensure_read_only_policy_grant(
            self,
            *,
            node_id,
            capability,
            operation,
            now,
        ):
            calls.append(("policy", node_id, capability, operation))
            return generated_grant

    class FakeControl:
        def __init__(self, **_kwargs):
            self.identities = SimpleNamespace(
                get=lambda requested: (
                    SimpleNamespace(node=SimpleNamespace(node_id=node_id))
                    if requested == node_id
                    else None
                )
            )
            self.endpoints = SimpleNamespace(
                get=lambda requested: (
                    SimpleNamespace() if requested == node_id else None
                )
            )
            self.authorization = FakeAuthorization()

        def invoke(self, enrollment, endpoint, request, *, now):
            assert request.grant_id == generated_grant.grant_id
            assert request.capability == "system.inspect"
            assert request.operation == "hardware"
            calls.append(("invoke", request.node_id))
            return RemoteOperationResult(
                request.request_id,
                request.node_id,
                RemoteOutcome.REPORTED_SUCCESS,
                "hardware observed",
            )

        def close(self):
            pass

    monkeypatch.setattr(
        fleet_capability,
        "DurableEndpointPolicy",
        FakeEndpointPolicy,
    )
    monkeypatch.setattr(
        fleet_capability,
        "PinnedHttpsRemoteTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        fleet_capability,
        "DurableRemoteControl",
        FakeControl,
    )

    service = _service(tmp_path)
    monkeypatch.setattr(
        service,
        "_ops_host_for_node",
        lambda requested: (
            SimpleNamespace(host_id="worker")
            if requested == node_id
            else None
        ),
    )
    result = service.invoke(
        str(node_id),
        "system.inspect",
        "hardware",
        {},
    )

    assert result["outcome"] == "reported_success"
    assert any(item[0] == "policy" for item in calls)
    assert any(item[0] == "invoke" for item in calls)


def test_remote_mutation_without_human_grant_stays_denied(
    tmp_path,
    monkeypatch,
):
    node_id = uuid4()
    invoked = []

    class FakeEndpointPolicy:
        def __init__(self, _path):
            pass

        def get(self, _node_id):
            return SimpleNamespace()

        def close(self):
            pass

    class FakeTransport:
        def __init__(self, endpoint_lookup, **_kwargs):
            assert callable(endpoint_lookup)

    class FakeAuthorization:
        def find_active(self, *, node_id, capability, operation, now):
            return None

        def ensure_read_only_policy_grant(self, **_kwargs):
            raise AssertionError("mutation must never receive a read-only policy grant")

    class FakeControl:
        def __init__(self, **_kwargs):
            self.identities = SimpleNamespace(
                get=lambda requested: (
                    SimpleNamespace(node=SimpleNamespace(node_id=node_id))
                    if requested == node_id
                    else None
                )
            )
            self.endpoints = SimpleNamespace(
                get=lambda requested: (
                    SimpleNamespace() if requested == node_id else None
                )
            )
            self.authorization = FakeAuthorization()

        def invoke(self, *_args, **_kwargs):
            invoked.append(True)
            raise AssertionError("remote mutation must not execute")

        def close(self):
            pass

    monkeypatch.setattr(
        fleet_capability,
        "DurableEndpointPolicy",
        FakeEndpointPolicy,
    )
    monkeypatch.setattr(
        fleet_capability,
        "PinnedHttpsRemoteTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        fleet_capability,
        "DurableRemoteControl",
        FakeControl,
    )

    service = _service(tmp_path)
    monkeypatch.setattr(
        service,
        "_ops_host_for_node",
        lambda requested: (
            SimpleNamespace(host_id="worker")
            if requested == node_id
            else None
        ),
    )
    with pytest.raises(PermissionError, match="human grant"):
        service.invoke(
            str(node_id),
            "service.manage",
            "restart",
            {"name": "example"},
        )
    assert invoked == []


def test_remote_tools_reject_identity_record_without_ops_fleet_membership(
    tmp_path,
    monkeypatch,
):
    node_id = uuid4()
    opened = []

    class FakeEndpointPolicy:
        def __init__(self, _path):
            opened.append("endpoint")
        def get(self, _node_id):
            return SimpleNamespace()
        def close(self):
            pass

    class FakeTransport:
        def __init__(self, endpoint_lookup, **_kwargs):
            assert callable(endpoint_lookup)

    class FakeControl:
        def __init__(self, **_kwargs):
            opened.append("control")
        def close(self):
            pass

    monkeypatch.setattr(
        fleet_capability,
        "DurableEndpointPolicy",
        FakeEndpointPolicy,
    )
    monkeypatch.setattr(
        fleet_capability,
        "PinnedHttpsRemoteTransport",
        FakeTransport,
    )
    monkeypatch.setattr(
        fleet_capability,
        "DurableRemoteControl",
        FakeControl,
    )

    service = _service(tmp_path)
    monkeypatch.setattr(
        service,
        "_ops_host_for_node",
        lambda _requested: None,
    )

    with pytest.raises(PermissionError, match="OPS Fleet member"):
        service.invoke(
            str(node_id),
            "system.inspect",
            "hardware",
            {},
        )
    # Admission fails before any remote control/session is opened.
    assert opened == []
