"""Single-owner worker thread for the desktop Sofía application.

Tk widgets live on the main thread. SofiaApplication and every controller call
live on exactly one dedicated worker thread for the lifetime of the desktop
session. This preserves SQLite thread affinity without globally disabling
SQLite's safety checks.
"""
from __future__ import annotations

from queue import Queue
from threading import Thread
from sofia.application import SofiaApplication
from sofia.config import SofiaConfiguration
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.theme import canonical_theme


class DesktopApplicationWorker:
    """Serialize all application/controller work onto one owner thread."""

    def __init__(
        self,
        *,
        configuration: SofiaConfiguration,
        session_id: str | None,
        events: Queue[tuple[str, object]],
    ) -> None:
        if not isinstance(configuration, SofiaConfiguration):
            raise TypeError("configuration must be SofiaConfiguration")
        if session_id is not None and (
            not isinstance(session_id, str)
            or not session_id.strip()
        ):
            raise ValueError("session_id must be nonempty or None")
        if not isinstance(events, Queue):
            raise TypeError("events must be a Queue")

        self._configuration = configuration
        self._session_id = session_id
        self._events = events
        self._commands: Queue[tuple[str, object]] = Queue()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("desktop application worker already started")
        self._thread = Thread(
            target=self._run,
            name="sofia-ui-application",
            daemon=True,
        )
        self._thread.start()

    def save_draft(self, content: str) -> None:
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        self._submit("save_draft", content)

    def send(self, content: str) -> None:
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if not content.strip():
            raise ValueError("content must not be blank")
        self._submit("send", content)

    def refresh_theme(self) -> None:
        self._submit("theme", None)

    def shutdown(self, current_draft: str) -> None:
        if not isinstance(current_draft, str):
            raise TypeError("current_draft must be a string")
        self._submit("shutdown", current_draft)

    def _submit(self, kind: str, payload: object) -> None:
        if self._thread is None:
            raise RuntimeError("desktop application worker is not started")
        self._commands.put((kind, payload))

    def _run(self) -> None:
        try:
            application = SofiaApplication(
                self._configuration
            )
            controller = DesktopWorkbenchController(
                application
            )
            history = controller.start(
                session_id=self._session_id
            )
            draft = controller.draft_text()
            try:
                palette = controller.theme_palette()
            except Exception:
                palette = canonical_theme()
            self._events.put(
                ("started", (history, draft, palette))
            )
        except Exception as exc:
            self._events.put(("startup_error", exc))
            return

        while True:
            kind, payload = self._commands.get()

            if kind == "save_draft":
                try:
                    controller.save_draft(payload)
                except Exception as exc:
                    self._events.put(("draft_error", exc))
                continue

            if kind == "send":
                try:
                    controller.send(payload)
                    history = controller.history()
                    try:
                        palette = controller.theme_palette()
                    except Exception:
                        palette = canonical_theme()
                    self._events.put(
                        ("sent", (history, palette))
                    )
                except Exception as exc:
                    self._events.put(("send_error", exc))
                continue

            if kind == "theme":
                try:
                    self._events.put(
                        ("theme", controller.theme_palette())
                    )
                except Exception:
                    self._events.put(
                        ("theme", canonical_theme())
                    )
                continue

            if kind == "shutdown":
                try:
                    controller.shutdown(
                        current_draft=payload
                    )
                except Exception as exc:
                    self._events.put(("shutdown_error", exc))
                else:
                    self._events.put(("shutdown_complete", None))
                return

            self._events.put(
                (
                    "worker_error",
                    RuntimeError(
                        f"unknown desktop command: {kind}"
                    ),
                )
            )
