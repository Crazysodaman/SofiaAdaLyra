from datetime import datetime, timezone
from threading import Barrier

from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.routing import CognitiveEngineRegistry, RoutingCognitiveEngine
from sofia.cognition.runtime_state import CognitionRuntimeStateStore
from sofia.config.model import ProviderConfiguration


NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _store(tmp_path):
    store = CognitionRuntimeStateStore(tmp_path / "sofia.db")
    store.configure(
        models={"primary": "primary:model", "secondary": "secondary:model"},
        residency_mode="resource_aware",
        routing_mode="dual",
        parallel_workers=2,
        at=NOW,
    )
    return store


def test_runtime_state_round_trip_includes_lifecycle_and_history(tmp_path):
    store = _store(tmp_path)
    store.publish_lifecycle(
        role="primary", model="primary:model", host="venus",
        installed=True, residency="ready", at=NOW,
    )
    store.mark_request(role="primary", model="primary:model", host="venus", at=NOW)
    store.mark_result(
        role="primary", model="primary:model", host="venus",
        route="standard", succeeded=True, at=NOW,
    )
    store.publish_route("standard", at=NOW)

    state = store.snapshot()

    assert state is not None
    assert state.latest_route == "standard"
    assert state.models[0].installed is True
    assert state.models[0].residency == "ready"
    assert state.models[0].last_request_at == NOW
    assert state.models[0].last_success_at == NOW
    assert store.history()[0]["model"] == "primary:model"


class BarrierEngine(CognitiveEngine):
    def __init__(self, role, model, store, barrier):
        self.role = role
        self.configuration = ProviderConfiguration(provider="test-llm", model=model)
        self.store = store
        self.barrier = barrier
        self.observed = None
        self.observed_workers = None
        self.calls = 0

    def respond(self, request):
        self.calls += 1
        if self.calls == 1:
            self.barrier.wait(timeout=5)
            snapshot = self.store.snapshot()
            self.observed = {item.role: item.activity for item in snapshot.models}
            self.observed_workers = snapshot.parallel_workers
        return CognitiveResponse(content=f"{self.role} response")


def test_parallel_workers_are_both_authoritatively_busy(tmp_path):
    store = _store(tmp_path)
    barrier = Barrier(2)
    primary = BarrierEngine("primary", "primary:model", store, barrier)
    secondary = BarrierEngine("secondary", "secondary:model", store, barrier)
    router = RoutingCognitiveEngine(
        CognitiveEngineRegistry(primary=primary, secondary=secondary),
        runtime_state_store=store,
        local_host_id="venus",
    )

    router.respond(CognitiveRequest(
        messages=(CognitiveMessage(role=CognitiveRole.USER, content="analyze deeply"),),
        route_hint="deep",
    ))

    assert primary.observed == {"primary": "busy", "secondary": "busy"}
    assert secondary.observed == {"primary": "busy", "secondary": "busy"}
    assert primary.observed_workers == 2
    assert secondary.observed_workers == 2
    state = store.snapshot()
    assert state.latest_route == "deep"
    assert {item.activity for item in state.models} == {"ready"}
    assert state.parallel_workers == 0
