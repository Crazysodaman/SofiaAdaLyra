import importlib
import sys

from sofia.modules.ui.desktop import (
    _TkDesktopWorkbench,
    _chamfer_points,
    _format_exception_chain,
    _inference_failure_message,
    main,
    settings_window_command,
)


def test_desktop_module_import_does_not_eagerly_import_tkinter():
    sys.modules.pop("sofia.modules.ui.desktop", None)
    before = set(sys.modules)

    importlib.import_module("sofia.modules.ui.desktop")

    added = set(sys.modules) - before
    assert "tkinter" not in added
    assert "tkinter.ttk" not in added


def test_desktop_main_is_callable():
    assert callable(main)


def test_settings_button_uses_current_python_and_exact_state_path(tmp_path):
    command = settings_window_command(tmp_path / "sofia.db")

    assert command[1:3] == ("-m", "sofia.modules.ui.settings_window")
    assert command[-2:] == ("--state-path", str(tmp_path / "sofia.db"))


def test_exception_chain_includes_root_cause():
    try:
        try:
            raise ValueError("inner failure")
        except ValueError as exc:
            raise RuntimeError("outer failure") from exc
    except RuntimeError as error:
        detail = _format_exception_chain(error)

    assert "RuntimeError: outer failure" in detail
    assert "Caused by: ValueError: inner failure" in detail


def test_exception_chain_rejects_non_exception():
    import pytest

    with pytest.raises(TypeError):
        _format_exception_chain("not an exception")


def _ollama_failure(cause: Exception):
    from sofia.core.cognition.engine import CognitiveEngineError
    from sofia.core.cognition.provider import LLMProviderError

    provider_error = LLMProviderError("Ollama failed to process the cognitive request.")
    provider_error.__cause__ = cause
    cognitive_error = CognitiveEngineError("LLM provider failed to process the cognitive request.")
    cognitive_error.__cause__ = provider_error
    return cognitive_error


def test_inference_failure_identifies_missing_runner_without_exposing_paths():
    error = _ollama_failure(
        RuntimeError("error starting llama-server: llama-server binary not found "
                     "(checked: C:\\secret\\personal\\runner.exe)")
    )
    detail = _inference_failure_message(error)

    assert "model runner is missing" in detail
    assert "ollama.com/download/windows" in detail
    assert "C:\\secret" not in detail
    assert "did not generate a reply" in detail


def test_inference_failure_distinguishes_offline_model_missing_and_unknown():
    offline = _inference_failure_message(
        _ollama_failure(ConnectionRefusedError("connection refused"))
    )
    missing_model = _inference_failure_message(
        _ollama_failure(RuntimeError("model 'qwen' not found"))
    )
    unknown = _inference_failure_message(
        _ollama_failure(RuntimeError("private provider diagnostic"))
    )

    assert "cannot reach Ollama" in offline
    assert "model is not installed" in missing_model
    assert "could not generate a response" in unknown
    assert "private provider diagnostic" not in unknown


def test_inference_failure_does_not_misclassify_unrelated_errors():
    assert _inference_failure_message(RuntimeError("llama-server binary not found")) is None


def test_desktop_inference_error_is_actionable_without_traceback(monkeypatch):
    from queue import Queue
    from types import SimpleNamespace

    events = Queue()
    events.put((
        "send_error",
        _ollama_failure(RuntimeError("llama-server binary not found")),
    ))
    statuses = []
    dialogs = []
    focus = []
    enabled = []
    callbacks = []
    fake = SimpleNamespace(
        _events=events,
        _busy=True,
        _close_requested=False,
        _status=SimpleNamespace(set=statuses.append),
        _set_enabled=enabled.append,
        _show_error=lambda title, detail: dialogs.append((title, detail)),
        _input=SimpleNamespace(focus_set=lambda: focus.append(True)),
        _root=SimpleNamespace(after=lambda ms, callback: callbacks.append((ms, callback))),
        _poll_events=lambda: None,
    )

    def fail_if_traceback(*args, **kwargs):
        raise AssertionError("expected inference outages must not dump a traceback")

    monkeypatch.setattr(
        "sofia.modules.ui.desktop.traceback.print_exception",
        fail_if_traceback,
    )
    _TkDesktopWorkbench._poll_events(fake)

    assert fake._busy is False
    assert enabled == [True]
    assert statuses == ["Ollama inference unavailable"]
    assert dialogs[0][0] == "Ollama inference unavailable"
    assert "model runner is missing" in dialogs[0][1]
    assert focus == [True]
    assert callbacks == [(80, fake._poll_events)]


def test_chamfer_points_use_shallow_45_degree_cuts():
    assert _chamfer_points(100, 60, 10) == (
        10, 0,
        90, 0,
        100, 10,
        100, 50,
        90, 60,
        10, 60,
        0, 50,
        0, 10,
    )


def test_chamfer_points_clamp_for_small_controls():
    points = _chamfer_points(12, 8, 10)

    assert min(points) >= 0
    assert max(points[0::2]) <= 12
    assert max(points[1::2]) <= 8


class _FakeText:
    def __init__(self):
        self.state = "disabled"
        self.content = "old text"
        self.modified = True

    def cget(self, key):
        assert key == "state"
        return self.state

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def edit_modified(self, value):
        self.modified = value

    def delete(self, start, end):
        assert start == "1.0"
        assert end == "end"
        if self.state != "disabled":
            self.content = ""

    def insert(self, start, content):
        assert start == "1.0"
        if self.state != "disabled":
            self.content = content


def test_replace_input_clears_disabled_composer_and_restores_state():
    fake = type("WorkbenchStub", (), {})()
    fake._input = _FakeText()

    _TkDesktopWorkbench._replace_input(fake, "")

    assert fake._input.content == ""
    assert fake._input.state == "disabled"
    assert fake._input.modified is False


def test_clear_screen_missing_anchor_recovers_only_newer_messages():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from sofia.modules.ui.desktop import _visible_history_after_clear
    marker = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    history = (
        SimpleNamespace(message_id="old", created_at=marker - timedelta(seconds=1)),
        SimpleNamespace(message_id="new", created_at=marker + timedelta(seconds=1)),
    )
    visible = _visible_history_after_clear(
        history, hidden_id="pruned-anchor", hidden_at=marker,
    )
    assert tuple(x.message_id for x in visible) == ("new",)
    # An intact anchor preserves exact visibility independent of clock precision.
    assert tuple(x.message_id for x in _visible_history_after_clear(
        history, hidden_id="old", hidden_at=marker + timedelta(days=1),
    )) == ("new",)
    assert _visible_history_after_clear(
        history, hidden_id="legacy-anchor", hidden_at=None,
    ) == ()


def test_clear_screen_missing_anchor_does_not_reset_memory_or_visibility_cursor(tmp_path):
    from datetime import datetime, timezone
    import json
    from sofia.modules.ui.desktop import _TkDesktopWorkbench

    dummy = type("DesktopStub", (), {})()
    dummy._session_id = "session:main"
    dummy._visibility_path = tmp_path / "display.json"
    dummy._latest_history_ids = ("turn:last",)
    dummy._last_rendered_ids = ("turn:last",)
    class Widget:
        def __init__(self):
            self.calls = []
        def configure(self, **kw):
            self.calls.append(("configure", kw))
        def delete(self, start, end):
            self.calls.append(("delete", start, end))
    class Status:
        def __init__(self): self.value = ""
        def set(self, value): self.value = value
    dummy._history = Widget()
    dummy._status = Status()
    _TkDesktopWorkbench._clear_screen(dummy)
    persisted = json.loads(dummy._visibility_path.read_text(encoding="utf-8"))
    assert persisted["hidden_through_id"] == "turn:last"
    assert datetime.fromisoformat(persisted["hidden_at"]).tzinfo is not None
    assert dummy._last_rendered_ids == ()
    assert dummy._status.value == "Screen cleared; conversation preserved"

