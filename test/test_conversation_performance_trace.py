"""Lock timing measures contention without recording conversation content."""
from threading import Event, RLock, Thread
from time import monotonic

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService


def test_conversation_trace_is_content_free(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    monkeypatch.setattr(ConversationService, "respond", lambda _self, _content: "ok")
    service = object.__new__(EmotionalConversationService)
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic()
    assert service.respond("canary-private-prompt") == "ok"
    trace = capsys.readouterr().err
    assert "[sofia-perf] conversation lock_wait_ms=" in trace
    assert "elapsed_ms=" in trace
    assert "canary" not in trace
    assert service._active_user_requests == 0


def test_reflection_trace_is_content_free(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    monkeypatch.setattr(EmotionalConversationService, "_reflect_on_event_locked",
                        lambda _self, *, event_id: "ok")
    service = object.__new__(EmotionalConversationService)
    service._model_lock = RLock()
    assert service.reflect_on_event(event_id="canary-event-id") == "ok"
    trace = capsys.readouterr().err
    assert "[sofia-perf] idle_reflection lock_wait_ms=" in trace
    assert "elapsed_ms=" in trace
    assert "canary" not in trace


def test_contention_produces_nonzero_wait_without_data_leak(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PERF_TRACE", "1")
    monkeypatch.setattr(ConversationService, "respond", lambda _self, _content: "ok")
    service = object.__new__(EmotionalConversationService)
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic()
    entered = Event()
    release = Event()

    def hold_lock():
        with service._model_lock:
            entered.set()
            assert release.wait(timeout=3)

    holder = Thread(target=hold_lock)
    holder.start()
    assert entered.wait(timeout=3)
    result = []
    waiting = Thread(target=lambda: result.append(service.respond("canary-private-prompt")))
    waiting.start()
    assert not result
    release.set()
    holder.join(timeout=3)
    waiting.join(timeout=3)
    assert not holder.is_alive() and not waiting.is_alive()
    assert result == ["ok"]
    trace = capsys.readouterr().err
    assert "[sofia-perf] conversation lock_wait_ms=" in trace
    assert "canary" not in trace
