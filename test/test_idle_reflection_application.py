"""Application owns worker lifecycle; no live inference in this test."""
from types import SimpleNamespace

import pytest

from sofia.application import bootstrap


class FakeWorker:
    def __init__(self, *, service, state_path):
        self.service = service
        self.state_path = state_path
        self.events = service.events
        self.events.append("worker:create")

    def start(self):
        self.events.append("worker:start")

    def stop(self):
        self.events.append("worker:stop")


def _application(monkeypatch, tmp_path, *, personality=True):
    events = []
    runtime = SimpleNamespace(
        personality=object() if personality else None,
        start=lambda: events.append("runtime:start"),
        shutdown=lambda: events.append("runtime:shutdown"),
    )
    conversation = SimpleNamespace(
        events=events,
        open=lambda: events.append("conversation:open"),
        start=lambda *, session_id: events.append("conversation:start"),
        deliver_pending_awareness=lambda: events.append("awareness") or None,
        close=lambda: events.append("conversation:close"),
    )
    app = object.__new__(bootstrap.SofiaApplication)
    app._runtime = runtime
    app._configuration = SimpleNamespace(state_path=tmp_path / "state.db")
    app._conversation_service = conversation
    app._idle_worker = None
    monkeypatch.setattr(bootstrap, "EmotionalConversationService", SimpleNamespace)
    monkeypatch.setattr(bootstrap, "IdleReflectionWorker", FakeWorker)
    return app, events


def test_opt_in_starts_only_after_awareness_and_stops_before_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "1")
    app, events = _application(monkeypatch, tmp_path)
    app.start()
    assert events == ["runtime:start", "conversation:open", "conversation:start",
                      "awareness", "worker:create", "worker:start"]
    assert app.idle_reflection_worker is not None
    app.shutdown()
    assert events[-3:] == ["worker:stop", "runtime:shutdown", "conversation:close"]
    assert app.idle_reflection_worker is None


@pytest.mark.parametrize("setting", ["", "0", "false", "off"])
def test_disabled_worker_never_starts(monkeypatch, tmp_path, setting):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", setting)
    app, events = _application(monkeypatch, tmp_path)
    app.start()
    assert app.idle_reflection_worker is None
    app.shutdown()
    assert "worker:start" not in events


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
