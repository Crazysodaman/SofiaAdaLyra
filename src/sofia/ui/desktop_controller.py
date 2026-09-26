"""Application-facing controller for the Windows text workbench.

The controller owns no cognition, memory, identity, or conversation storage.
It coordinates the canonical SofiaApplication.text_ui surface and makes draft
preservation explicit around sends and shutdown.
"""
from __future__ import annotations

from typing import Protocol

from sofia.cognition.model import CognitiveResponse
from sofia.ui.text import UITextClient, UITextMessage


class DesktopApplication(Protocol):
    @property
    def text_ui(self) -> UITextClient: ...

    def start(self, session_id: str | None = None): ...

    def shutdown(self) -> None: ...


class DesktopWorkbenchController:
    """Small testable boundary between a desktop renderer and SofiaApplication."""

    def __init__(self, application: DesktopApplication) -> None:
        if not hasattr(application, "text_ui"):
            raise TypeError("application must expose text_ui")
        if not callable(getattr(application, "start", None)):
            raise TypeError("application must expose start(session_id)")
        if not callable(getattr(application, "shutdown", None)):
            raise TypeError("application must expose shutdown()")
        self._application = application
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def session_id(self) -> str:
        if not self._started:
            raise RuntimeError("desktop workbench is not started")
        return self._application.text_ui.session_id

    def start(
        self,
        *,
        session_id: str | None = None,
    ) -> tuple[UITextMessage, ...]:
        if self._started:
            raise RuntimeError("desktop workbench is already started")
        self._application.start(session_id=session_id)
        self._started = True
        return self.history()

    def history(self) -> tuple[UITextMessage, ...]:
        if not self._started:
            raise RuntimeError("desktop workbench is not started")
        return self._application.text_ui.history()

    def draft_text(self) -> str:
        if not self._started:
            raise RuntimeError("desktop workbench is not started")
        draft = self._application.text_ui.draft()
        return "" if draft is None else draft.content

    def save_draft(self, content: str) -> None:
        if not self._started:
            raise RuntimeError("desktop workbench is not started")
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        self._application.text_ui.save_draft(content)

    def send(self, content: str) -> CognitiveResponse:
        """Persist the text as a draft, then send through canonical conversation.

        Saving before generation means a provider/runtime failure leaves the exact
        unsent text recoverable on the next desktop launch.
        """
        if not self._started:
            raise RuntimeError("desktop workbench is not started")
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if not content.strip():
            raise ValueError("content must not be blank")

        self._application.text_ui.save_draft(content)
        return self._application.text_ui.send()

    def shutdown(self, *, current_draft: str | None = None) -> None:
        if not self._started:
            return
        if current_draft is not None:
            if not isinstance(current_draft, str):
                raise TypeError("current_draft must be a string or None")
            self._application.text_ui.save_draft(current_draft)
        self._application.shutdown()
        self._started = False
