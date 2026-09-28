from pathlib import Path
from types import SimpleNamespace

import pytest

import sofia.distributed.capability as fleet_capability
from sofia.distributed.capability import RemoteFleetToolService


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
        ("endpoint:open", "remote-endpoints.db"),
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
