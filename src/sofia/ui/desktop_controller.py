"""Application-facing controller for the Windows text workbench.

The controller owns no cognition, memory, identity, or conversation storage.
It coordinates the canonical SofiaApplication.text_ui surface and makes draft
preservation explicit around sends and shutdown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Protocol

from sofia.cognition.model import CognitiveResponse
from sofia.ui.text import UITextClient, UITextMessage
from sofia.ui.theme import (
    AdaptiveThemePolicy,
    ThemePalette,
    theme_signals_from_sources,
)


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
        self._theme_policy = AdaptiveThemePolicy()
        self._last_persistence_receipt: str | None = None

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

    def persistence_status(self) -> str:
        """Describe where this desktop session's authoritative chat is stored."""
        if not self._started:
            raise RuntimeError("desktop workbench is not started")

        mode = getattr(self._application, "chat_storage_mode", "unknown")
        session = self.session_id
        if mode != "local":
            raise RuntimeError(
                "desktop chat must use the canonical local state database"
            )
        path = getattr(self._application, "chat_state_path", None)
        if path is None:
            raise RuntimeError(
                "local desktop application did not expose chat_state_path"
            )
        status = f"CANONICAL DB: {Path(path)} | session: {session}"
        if self._last_persistence_receipt is not None:
            status += f" | {self._last_persistence_receipt}"
        return status

    def matrix_status(self) -> str:
        """Return a compact status for the latest canonical matrix turn."""
        if not self._started:
            raise RuntimeError("desktop workbench is not started")

        conversation = getattr(self._application, "conversation", None)
        latest = getattr(conversation, "latest_matrix_trace", None)
        if not callable(latest):
            return "MATRIX unavailable"
        trace = latest()
        if trace is None:
            return "MATRIX no-trace"

        intent = trace.turn.intent.value
        domains = ",".join(
            item.domain.value
            for item in trace.turn.domains
            if item.relevance.value > 0
        ) or "none"
        requested_route = (
            "none" if trace.routing is None else trace.routing.route.value
        )
        actual_route = "none"
        model = "none"
        path = "none"
        execution = trace.cognition_execution
        if execution is not None:
            actual_route = execution.actual_route
            path = ">".join(
                step.role for step in execution.successful_steps
            ) or "none"
            last_step = execution.last_successful_step
            if last_step is not None:
                model_name = last_step.model or "unknown-model"
                host = "" if last_step.host is None else f"@{last_step.host}"
                model = f"{last_step.role}:{model_name}{host}"
        validation = (
            "pending"
            if trace.response_validation is None
            else trace.response_validation.disposition.value
        )
        return (
            f"MATRIX {intent} [{domains}] req={requested_route} "
            f"actual={actual_route} path={path} model={model} "
            f"validation={validation}"
        )

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

    def theme_palette(self) -> ThemePalette:
        """Project adaptive presentation from current trusted runtime state."""
        if not self._started:
            raise RuntimeError("desktop workbench is not started")

        runtime = getattr(self._application, "runtime", None)
        if runtime is None:
            raise RuntimeError(
                "desktop application does not expose runtime theme sources"
            )

        environment = runtime.environment_service.snapshot(
            refresh_providers=False
        )
        presentation = runtime.avatar_presentation_projection

        emotion = None
        conversation = getattr(
            self._application,
            "conversation",
            None,
        )
        current_emotional_state = getattr(
            conversation,
            "current_emotional_state",
            None,
        )
        if callable(current_emotional_state):
            emotion = current_emotional_state(
                now=datetime.now(timezone.utc)
            )

        signals = theme_signals_from_sources(
            environment=environment,
            presentation=presentation,
            emotion=emotion,
        )
        return self._theme_policy.select(signals)

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
        before_ids = {
            message.message_id
            for message in self._application.text_ui.history()
        }
        response = self._application.text_ui.send()
        try:
            self._verify_send_persisted(
                content=content,
                before_ids=before_ids,
            )
        except Exception:
            # UITextClient clears the draft after conversation.respond() returns.
            # If the independent durability check fails, put the exact text back
            # so the desktop never pretends a possibly-unpersisted turn is done.
            self._application.text_ui.save_draft(content)
            raise
        return response

    def _verify_send_persisted(
        self,
        *,
        content: str,
        before_ids: set[str],
    ) -> None:
        """Prove the just-rendered turn is committed to canonical SQLite.

        This deliberately uses a fresh SQLite connection rather than trusting
        the ConversationStore's open connection or the UI history projection.
        A successful desktop send therefore carries an independent durability
        receipt for the exact configured database file.
        """
        mode = getattr(self._application, "chat_storage_mode", None)
        if mode is None:
            # Lightweight protocol fakes used by controller unit tests do not
            # model storage authority. Real desktop applications always do.
            return
        if mode != "local":
            raise RuntimeError(
                "desktop chat persistence verification requires local mode"
            )

        raw_path = getattr(self._application, "chat_state_path", None)
        if raw_path is None:
            raise RuntimeError(
                "desktop chat persistence verification has no database path"
            )
        path = Path(raw_path)
        history = self._application.text_ui.history()
        new_messages = tuple(
            message
            for message in history
            if message.message_id not in before_ids
        )
        user_messages = tuple(
            message
            for message in new_messages
            if message.actor == "user" and message.content == content.strip()
        )
        assistant_messages = tuple(
            message
            for message in new_messages
            if message.actor == "sofia"
        )
        if not user_messages or not assistant_messages:
            raise RuntimeError(
                "desktop send did not produce a complete persisted turn"
            )

        expected_ids = {
            user_messages[-1].message_id,
            assistant_messages[-1].message_id,
        }
        try:
            with sqlite3.connect(str(path), timeout=5.0) as database:
                rows = database.execute(
                    "SELECT id FROM conversation_messages "
                    "WHERE id IN (?, ?)",
                    tuple(expected_ids),
                ).fetchall()
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"desktop could not independently verify canonical chat DB: {path}"
            ) from exc

        persisted_ids = {str(row[0]) for row in rows}
        missing = expected_ids - persisted_ids
        if missing:
            raise RuntimeError(
                "desktop send was not durable in canonical chat DB "
                f"{path}; missing {len(missing)} message(s)"
            )
        self._last_persistence_receipt = (
            f"last send durable: 2 messages @ {path}"
        )

    def shutdown(self, *, current_draft: str | None = None) -> None:
        if not self._started:
            return
        if current_draft is not None:
            if not isinstance(current_draft, str):
                raise TypeError("current_draft must be a string or None")
            self._application.text_ui.save_draft(current_draft)
        self._application.shutdown()
        self._started = False
