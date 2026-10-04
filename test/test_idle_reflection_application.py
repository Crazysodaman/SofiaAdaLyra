"""Application owns worker lifecycle; no live inference in this test."""
from threading import RLock
from types import SimpleNamespace

import pytest

from sofia.application import bootstrap, background_runtime


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
            blueprints=(),
        ),
        matrix_for=lambda item_ids: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "load_or_bootstrap_presentation",
        lambda *, embodiment, state_path: presentation_bundle,
    )

    def install_presentation_bundle(application, bundle):
        # These tests exercise application lifecycle behavior, not AVATAR
        # composition. Preserve the production PresentationRuntimeBundle type
        # boundary and stub only this unrelated installation seam.
        application._presentation_bundle = bundle
        application._presentation_routine = None
        application._clothing_action_service = None
        application._wardrobe_generation_service = None
        runtime.set_avatar_presentation(bundle.authority)
        runtime.set_avatar_matrix_builder(bundle.matrix_for)

    monkeypatch.setattr(
        bootstrap.SofiaApplication,
        "_install_presentation_bundle",
        install_presentation_bundle,
    )
    monkeypatch.setattr(
        bootstrap,
        "OutfitPlanner",
        lambda wardrobe, presets, **kwargs: None,
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
        background_runtime,
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


def test_failed_coordinator_start_is_owned_and_stopped_during_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "1")
    app, events = _application(monkeypatch, tmp_path)

    def fail_after_starting(coordinator):
        coordinator.events.append("coordinator:partial-start")
        raise RuntimeError("startup failed after acquiring resources")

    monkeypatch.setattr(FakeCoordinator, "start", fail_after_starting)
    with pytest.raises(bootstrap.SofiaApplicationError) as error:
        app.start()

    assert isinstance(error.value.__cause__, RuntimeError)
    assert events.index("coordinator:partial-start") < events.index("coordinator:stop")
    assert events.index("coordinator:stop") < events.index("conversation:close")
    assert app._background is None
    assert app.idle_reflection_worker is None


def test_failed_model_worker_start_is_stopped_during_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    app, events = _application(monkeypatch, tmp_path)
    app._runtime.model_lifecycle = SimpleNamespace(
        install_missing=lambda: None,
        policy=SimpleNamespace(enabled=True, idle_unload_seconds=60),
    )

    class PartialWorker:
        def __init__(self, **kwargs):
            pass

        def start(self):
            events.append("model:partial-start")
            raise RuntimeError("model worker start failed")

        def stop(self):
            events.append("model:stop")

    monkeypatch.setattr(bootstrap, "ModelLifecycleWorker", PartialWorker)
    with pytest.raises(bootstrap.SofiaApplicationError):
        app.start()

    assert events.index("model:partial-start") < events.index("model:stop")
    assert app._model_lifecycle_worker is None
