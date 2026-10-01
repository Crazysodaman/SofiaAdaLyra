from datetime import datetime, timezone

from sofia.cognition.activity import (
    CognitiveActivityState,
    CognitiveModelActivityStore,
)
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.routing import (
    CognitiveEngineRegistry,
    RoutingCognitiveEngine,
)
from sofia.config.model import ProviderConfiguration


NOW = datetime(2026, 10, 1, 22, 0, tzinfo=timezone.utc)


def test_activity_store_round_trip_and_crash_recovery(tmp_path):
    store = CognitiveModelActivityStore(tmp_path / "sofia.db")
    store.mark_busy(
        role="primary",
        model="vendor/primary:9b",
        at=NOW,
    )

    busy = store.get("primary")
    assert busy is not None
    assert busy.state is CognitiveActivityState.BUSY
    assert busy.updated_at == NOW

    store.clear_stale_busy()
    assert store.get("primary") is None

    store.mark_finished(
        role="primary",
        model="vendor/primary:9b",
        host="venus",
        succeeded=True,
        at=NOW,
    )
    ready = store.get("primary")
    assert ready is not None
    assert ready.state is CognitiveActivityState.READY
    assert ready.host == "venus"


class ObservingEngine(CognitiveEngine):
    def __init__(
        self,
        *,
        role: str,
        model: str,
        store: CognitiveModelActivityStore,
        content: str,
    ) -> None:
        self.role = role
        self.configuration = ProviderConfiguration(
            provider="test-llm",
            model=model,
        )
        self.store = store
        self.content = content
        self.observed_states = []

    def respond(self, request):
        current = self.store.get(self.role)
        self.observed_states.append(
            None if current is None else current.state
        )
        return CognitiveResponse(content=self.content)


def test_verify_router_publishes_real_busy_state_for_each_model_call(tmp_path):
    store = CognitiveModelActivityStore(tmp_path / "sofia.db")
    primary = ObservingEngine(
        role="primary",
        model="vendor/primary:9b",
        store=store,
        content="primary",
    )
    secondary = ObservingEngine(
        role="secondary",
        model="vendor/secondary:4b",
        store=store,
        content="critique",
    )
    router = RoutingCognitiveEngine(
        CognitiveEngineRegistry(
            primary=primary,
            secondary=secondary,
        ),
        activity_store=store,
    )

    router.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="verify this",
                ),
            ),
            allow_tools=False,
            route_hint="verify",
        )
    )

    assert primary.observed_states == [
        CognitiveActivityState.BUSY,
        CognitiveActivityState.BUSY,
    ]
    assert secondary.observed_states == [
        CognitiveActivityState.BUSY,
    ]
    assert store.get("primary").state is CognitiveActivityState.READY
    assert store.get("secondary").state is CognitiveActivityState.READY
