"""Single-owner worker thread for the desktop Sofía client.

Tk widgets live on the main thread. The selected local or authenticated remote
application and every controller call live on exactly one dedicated worker
thread for the lifetime of the desktop session.
"""
from __future__ import annotations

from queue import Queue
from threading import Thread

from sofia.config import SofiaConfiguration
from sofia.discord.live import (
    DiscordBackgroundService,
    compose_live_discord_for_conversation,
    discord_bound_session_id,
)
from sofia.discord.provisioning import DiscordProvisioning
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.remote_application import create_desktop_application
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
        controller = None
        discord_service: DiscordBackgroundService | None = None
        try:
            provisioning = DiscordProvisioning.from_environment()
            session_id = self._session_id
            if provisioning.enabled:
                bound_session = discord_bound_session_id(
                    provisioning,
                    configuration=self._configuration,
                )
                if (
                    session_id is not None
                    and bound_session is not None
                    and session_id != bound_session
                ):
                    raise RuntimeError(
                        "requested desktop session conflicts with the "
                        "durable Discord conversation binding"
                    )
                if session_id is None:
                    session_id = bound_session

            application = create_desktop_application(
                self._configuration
            )
            controller = DesktopWorkbenchController(
                application
            )
            history = controller.start(
                session_id=session_id
            )

            if provisioning.enabled:
                conversation = getattr(
                    application,
                    "conversation",
                    None,
                )
                if conversation is None:
                    raise RuntimeError(
                        "provisioned Discord requires the canonical "
                        "desktop conversation"
                    )
                channel = compose_live_discord_for_conversation(
                    provisioning,
                    conversation=conversation,
                    configuration=self._configuration,
                )
                discord_service = DiscordBackgroundService(
                    provisioning,
                    channel,
                    on_error=lambda exc: self._events.put(
                        ("discord_error", exc)
                    ),
                )
                discord_service.start()

            draft = controller.draft_text()
            try:
                palette = controller.theme_palette()
            except Exception:
                palette = canonical_theme()
            self._events.put(
                ("started", (history, draft, palette))
            )
            if discord_service is not None:
                self._events.put(("discord_started", None))
        except Exception as exc:
            if discord_service is not None:
                try:
                    discord_service.stop()
                except Exception:
                    pass
            if controller is not None and controller.started:
                try:
                    controller.shutdown()
                except Exception:
                    pass
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
                shutdown_error = None
                if discord_service is not None:
                    try:
                        discord_service.stop()
                    except Exception as exc:
                        shutdown_error = exc
                try:
                    controller.shutdown(
                        current_draft=payload
                    )
                except Exception as exc:
                    shutdown_error = shutdown_error or exc
                if shutdown_error is None:
                    self._events.put(("shutdown_complete", None))
                else:
                    self._events.put(
                        ("shutdown_error", shutdown_error)
                    )
                return

            self._events.put(
                (
                    "worker_error",
                    RuntimeError(
                        f"unknown desktop command: {kind}"
                    ),
                )
            )
