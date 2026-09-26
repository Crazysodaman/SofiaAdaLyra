from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.text import UITextMessage


@dataclass
class FakeDraft:
    content: str


class FakeTextUI:
    def __init__(self) -> None:
        self.session_id = "session-1"
        self._draft: FakeDraft | None = None
        self.sent: list[str] = []
        self.fail_send = False
        self._history = (
            UITextMessage(
                message_id="m1",
                session_id="session-1",
                actor="sofia",
                content="ready",
                created_at=datetime.now(timezone.utc),
            ),
        )

    def history(self):
        return self._history

    def draft(self):
        return self._draft

    def save_draft(self, content: str):
        self._draft = None if not content else FakeDraft(content)
        return self._draft

    def send(self):
        if self._draft is None:
            raise ValueError("no draft")
        content = self._draft.content
        self.sent.append(content)
        if self.fail_send:
            raise RuntimeError("provider failed")
        self._draft = None
        return CognitiveResponse(content="response")


class FakeApplication:
    def __init__(self) -> None:
        self.text_ui = FakeTextUI()
        self.started_with = None
        self.shutdown_calls = 0

    def start(self, session_id=None):
        self.started_with = session_id

    def shutdown(self):
        self.shutdown_calls += 1


def test_controller_starts_same_application_session():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)

    history = controller.start(
        session_id="session-1"
    )

    assert controller.started is True
    assert controller.session_id == "session-1"
    assert app.started_with == "session-1"
    assert history == app.text_ui.history()


def test_controller_send_saves_draft_before_generation():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)
    controller.start()

    response = controller.send("hello")

    assert response.content == "response"
    assert app.text_ui.sent == ["hello"]
    assert controller.draft_text() == ""


def test_failed_send_preserves_exact_draft():
    app = FakeApplication()
    app.text_ui.fail_send = True
    controller = DesktopWorkbenchController(app)
    controller.start()

    with pytest.raises(RuntimeError, match="provider failed"):
        controller.send("recover this exact text")

    assert controller.draft_text() == "recover this exact text"


def test_shutdown_preserves_current_draft():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)
    controller.start()

    controller.shutdown(
        current_draft="unfinished window text"
    )

    assert app.shutdown_calls == 1
    assert app.text_ui._draft.content == "unfinished window text"
    assert controller.started is False


def test_shutdown_with_empty_text_clears_saved_draft():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)
    controller.start()
    controller.save_draft("old draft")

    controller.shutdown(current_draft="")

    assert app.text_ui._draft is None


def test_controller_operations_require_start():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)

    with pytest.raises(RuntimeError):
        controller.history()
    with pytest.raises(RuntimeError):
        controller.draft_text()
    with pytest.raises(RuntimeError):
        controller.save_draft("draft")
    with pytest.raises(RuntimeError):
        controller.send("message")
    with pytest.raises(RuntimeError):
        _ = controller.session_id


def test_controller_rejects_double_start():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)
    controller.start()

    with pytest.raises(RuntimeError):
        controller.start()


def test_shutdown_before_start_is_noop():
    app = FakeApplication()
    controller = DesktopWorkbenchController(app)

    controller.shutdown()

    assert app.shutdown_calls == 0
