from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.fleet_engine import (
    FleetCognitionPolicy,
    FleetPlacedCognitiveEngine,
)
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
    CognitiveToolCall,
)
from sofia.config.model import ProviderConfiguration
from sofia.ops.capability import OpsToolService
from sofia.ops.model import FleetHost, HostLifecycle, HostTelemetry
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW=datetime(2026,9,29,20,0,tzinfo=timezone.utc)


class LocalEngine(CognitiveEngine):
    def __init__(self):
        self.calls=[]

    def respond(self,request):
        self.calls.append(request)
        return CognitiveResponse(content="local")


def _ops(tmp_path,hosts):
    state=tmp_path/"sofia.db"
    ops=OpsToolService(
        state,
        state_plane=SQLiteStatePlane(state),
    )
    for host in hosts:
        ops.registry.register_candidate(host)
    return ops


def _host(
    host_id,
    *,
    cpu,
    node_id=None,
    lifecycle=HostLifecycle.HEALTHY,
    trusted=True,
):
    return FleetHost(
        host_id,
        "windows",
        "x86_64",
        lifecycle,
        trusted,
        HostTelemetry(
            NOW,
            cpu_percent=cpu,
            ram_used_bytes=4,
            ram_total_bytes=32,
            gpu_percent=cpu,
            vram_used_bytes=1,
            vram_total_bytes=12,
            storage_free_bytes=100,
        ),
        node_id=node_id,
    )


def _engine(tmp_path,*,hosts,policy=None,remote=None):
    local=LocalEngine()
    ops=_ops(tmp_path,hosts)
    calls=[]
    def remote_infer(node_id,provider,request):
        calls.append((node_id,provider,request))
        if remote is not None:
            return remote(node_id,provider,request)
        return CognitiveResponse(content="remote")
    engine=FleetPlacedCognitiveEngine(
        local=local,
        provider=ProviderConfiguration(
            provider="ollama",
            model="owner/model:any",
        ),
        ops=ops,
        local_host_id="local",
        remote_infer=remote_infer,
        policy=policy or FleetCognitionPolicy(enabled=True),
        workload_id="cognition-primary",
    )
    return engine,local,calls


def test_fleet_engine_places_on_lower_pressure_bound_remote_host(tmp_path):
    remote_node=uuid4()
    engine,local,calls=_engine(
        tmp_path,
        hosts=(
            _host("local",cpu=80),
            _host("remote",cpu=10,node_id=remote_node),
        ),
    )

    response=engine.respond(CognitiveRequest(messages=()))

    assert response.content=="remote"
    assert local.calls==[]
    assert calls[0][0]==remote_node
    assert calls[0][1].model=="owner/model:any"
    assert engine.last_host_id=="remote"
    assert engine.last_remote is True


def test_unbound_remote_host_is_not_a_remote_cognition_candidate(tmp_path):
    engine,local,calls=_engine(
        tmp_path,
        hosts=(
            _host("local",cpu=70),
            _host("unbound",cpu=1,node_id=None),
        ),
    )

    response=engine.respond(CognitiveRequest(messages=()))

    assert response.content=="local"
    assert len(local.calls)==1
    assert calls==[]


def test_remote_failure_falls_back_local_when_owner_policy_allows(tmp_path):
    def fail(*_):
        raise RuntimeError("remote failed")
    engine,local,calls=_engine(
        tmp_path,
        hosts=(
            _host("local",cpu=80),
            _host("remote",cpu=10,node_id=uuid4()),
        ),
        remote=fail,
    )

    assert engine.respond(CognitiveRequest(messages=())).content=="local"
    assert len(calls)==1
    assert len(local.calls)==1
    assert engine.last_remote is False


def test_remote_failure_does_not_fallback_when_policy_disables_it(tmp_path):
    def fail(*_):
        raise RuntimeError("remote failed")
    engine,local,calls=_engine(
        tmp_path,
        hosts=(
            _host("local",cpu=80),
            _host("remote",cpu=10,node_id=uuid4()),
        ),
        policy=FleetCognitionPolicy(
            enabled=True,
            local_fallback=False,
        ),
        remote=fail,
    )

    with pytest.raises(CognitiveEngineError,match="fallback is disabled"):
        engine.respond(CognitiveRequest(messages=()))

    assert len(calls)==1
    assert local.calls==[]


def test_remote_tool_calls_are_returned_for_authoritative_runtime_dispatch(tmp_path):
    call=CognitiveToolCall(
        name="inspect_system",
        arguments={"detail":"summary"},
        call_id="remote-call",
    )
    engine,local,calls=_engine(
        tmp_path,
        hosts=(
            _host("local",cpu=80),
            _host("remote",cpu=10,node_id=uuid4()),
        ),
        remote=lambda *_:CognitiveResponse(
            content="",
            tool_calls=(call,),
        ),
    )

    response=engine.respond(CognitiveRequest(messages=()))

    assert response.tool_calls==(call,)
    assert local.calls==[]
