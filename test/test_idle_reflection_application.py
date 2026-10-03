"""Application owns worker lifecycle; no live inference in this test."""
from threading import RLock
from types import SimpleNamespace

import pytest

from sofia.application import bootstrap


class FakeWorker:
    def __init__(self, *, service, state_path):
        self.service = service
        self.state_path = state_path
        self.events = service.events
        self.events.append("worker:create")


class FakeCoordinator:
    def __init__(
        self,
        *,
        service,
        state_path,
        reflection_enabled=True,
        **_kwargs,
    ):
        self.events = service.events
        self.idle = (
            FakeWorker(service=service, state_path=state_path)
            if reflection_enabled
            else None
        )

    def set_act_delivery(self, _callback):
        pass

    def set_task(self, _task_kind, _callback, **_kwargs):
        pass

    def set_heartbeat(self, _callback):
        pass

    def start(self):
        self.events.append("coordinator:start")

    def stop(self):
        self.events.append("coordinator:stop")


def _application(monkeypatch, tmp_path, *, personality=True):
    events = []
    state_path = tmp_path / "state.db"
    state_path.touch()
    runtime = SimpleNamespace(
        personality=object() if personality else None,
        embodiment=object(),
        workspace_changes=None,
        start=lambda: events.append("runtime:start"),
        shutdown=lambda: events.append("runtime:shutdown"),
        set_avatar_presentation=lambda authority: None,
        set_avatar_matrix_builder=lambda builder: None,
    )
    conversation = SimpleNamespace(
        events=events,
        open=lambda: events.append("conversation:open"),
        start=lambda *, session_id: events.append("conversation:start"),
        deliver_pending_awareness=lambda: events.append("awareness") or None,
        close=lambda: events.append("conversation:close"),
        set_clothing_action_handler=lambda handler: None,
    )
    presentation_bundle = SimpleNamespace(
        authority=object(),
        store=SimpleNamespace(save=lambda authority: None),
        catalog=SimpleNamespace(
            wardrobe=object(),
            presets=(),
        ),
        matrix_for=lambda item_ids: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "load_or_bootstrap_presentation",
        lambda *, embodiment, state_path: presentation_bundle,
    )
    monkeypatch.setattr(
        bootstrap,
        "WardrobeStudio",
        lambda catalog, *, authority=None: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "OutfitPlanner",
        lambda wardrobe, presets: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "HeadlessPresentationRoutine",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "ClothingActionService",
        lambda *args, **kwargs: SimpleNamespace(handle=lambda **kwargs: None),
    )
    app = object.__new__(bootstrap.SofiaApplication)
    app._runtime = runtime
    app._configuration = SimpleNamespace(state_path=state_path)
    app._conversation_service = conversation
    app._channel_conversations = []
    app._idle_worker = None
    app._model_lock = RLock()
    app._tts = SimpleNamespace(
        start=lambda: events.append("tts:start"),
        stop=lambda: events.append("tts:stop"),
    )
    monkeypatch.setattr(bootstrap, "EmotionalConversationService", SimpleNamespace)
    monkeypatch.setattr(
        bootstrap,
        "ApplicationBackgroundCoordinator",
        FakeCoordinator,
    )
    return app, events


def test_opt_in_starts_only_after_awareness_and_stops_before_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "1")
    app, events = _application(monkeypatch, tmp_path)
    app.start()
    assert events == [
        "runtime:start",
        "conversation:open",
        "conversation:start",
        "tts:start",
        "awareness",
        "worker:create",
        "coordinator:start",
    ]
    assert app.idle_reflection_worker is not None
    app.shutdown()
    assert "coordinator:stop" in events
    assert "runtime:shutdown" in events
    assert events[-1] == "conversation:close"
    assert app.idle_reflection_worker is None


@pytest.mark.parametrize("setting", ["", "0", "false", "off"])
def test_disabled_worker_never_starts(monkeypatch, tmp_path, setting):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", setting)
    app, events = _application(monkeypatch, tmp_path)
    app.start()
    assert app.idle_reflection_worker is None
    app.shutdown()
    assert "worker:create" not in events


def test_no_personality_does_not_launch_worker(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "1")
    app, events = _application(monkeypatch, tmp_path, personality=False)
    app.start()
    assert app.idle_reflection_worker is None
    app.shutdown()


def test_invalid_opt_in_is_reported_before_start(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "banana")
    app, events = _application(monkeypatch, tmp_path)
    with pytest.raises(bootstrap.SofiaApplicationError, match="failed to start"):
        app.start()
    assert events == []
