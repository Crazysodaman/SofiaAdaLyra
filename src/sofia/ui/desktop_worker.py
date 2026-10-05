"""Single-owner worker thread for the desktop Sofía client.

Tk widgets live on the main thread. The selected local or authenticated remote
application and every controller call live on exactly one dedicated worker
thread for the lifetime of the desktop session.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from sofia.config import SofiaConfiguration
from sofia.discord.live import (
    DiscordBackgroundService,
    compose_live_discord_for_conversation,
    discord_bound_session_id,
)
from sofia.discord.provisioning import DiscordProvisioning
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.desktop_application import create_desktop_application
from sofia.ui.theme import canonical_theme
from sofia.mobile.gateway import MobileCompanionGateway
from sofia.mobile.provisioning import MobileProvisioning
from sofia.mobile.server import MobileCompanionServer


class _WorkerMobileGateway:
    """Synchronously marshal HTTP requests onto the application owner thread."""

    def __init__(self, commands: Queue[tuple[str, object]]) -> None:
        self._commands = commands

    def _call(self, method: str, *args, **kwargs):
        reply: Queue[tuple[bool, object]] = Queue(maxsize=1)
        self._commands.put(("mobile", (method, args, kwargs, reply)))
        try:
            ok, value = reply.get(timeout=130)
        except Empty as exc:
            raise TimeoutError("mobile application request timed out") from exc
        if ok:
            return value
        if isinstance(value, BaseException):
            raise value
        raise RuntimeError("mobile application request failed without an exception")

    def ingest_sensors(self, payload):
        return self._call("ingest_sensors", payload)

    def chat(self, **kwargs):
        return self._call("chat", **kwargs)

    def state(self, **kwargs):
        return self._call("state", **kwargs)

    def claim_notification(self, **kwargs):
        return self._call("claim_notification", **kwargs)

    def acknowledge_notification(self, **kwargs):
        return self._call("acknowledge_notification", **kwargs)


class DesktopApplicationWorker:
    """Serialize all application/controller work onto one owner thread."""

    def __init__(
        self,
        *,
        configuration: SofiaConfiguration,
        session_id: str | None,
        events: Queue[tuple[str, object]],
        discord_provisioning: DiscordProvisioning | None = None,
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
        if (
            discord_provisioning is not None
            and not isinstance(
                discord_provisioning,
                DiscordProvisioning,
            )
        ):
            raise TypeError(
                "discord_provisioning must be DiscordProvisioning or None"
            )

        self._configuration = configuration
        self._session_id = session_id
        self._events = events
        self._discord_provisioning = discord_provisioning
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
        mobile_server: MobileCompanionServer | None = None
        mobile_gateway: MobileCompanionGateway | None = None
        try:
            provisioning = (
                self._discord_provisioning
                if self._discord_provisioning is not None
                else DiscordProvisioning.from_runtime(
                    self._configuration
                )
            )
            application = create_desktop_application(
                self._configuration
            )
            controller = DesktopWorkbenchController(
                application
            )
            history = controller.start(
                session_id=self._session_id
            )

            mobile = MobileProvisioning.from_runtime(self._configuration)
            if mobile.enabled:
                mobile_gateway = MobileCompanionGateway(
                    application,
                    state_path=self._configuration.state_path,
                )
                mobile_server = MobileCompanionServer(
                    _WorkerMobileGateway(self._commands),
                    token=mobile.require_token(),
                    configuration=mobile.server,
                )
                mobile_server.start()

            if provisioning.enabled:
                if getattr(application, "runtime", None) is None:
                    raise RuntimeError(
                        "provisioned Discord must run on the canonical "
                        "runtime host, not through a remote desktop client"
                    )
                open_channel = getattr(
                    application,
                    "open_channel_conversation",
                    None,
                )
                if not callable(open_channel):
                    raise RuntimeError(
                        "canonical runtime does not expose channel "
                        "conversation composition"
                    )
                discord_session_id = discord_bound_session_id(
                    provisioning,
                    configuration=self._configuration,
                )
                conversation = open_channel(
                    session_id=discord_session_id,
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
            self._events.put(
                ("persistence", controller.persistence_status())
            )
            if discord_service is not None:
                self._events.put(("discord_started", None))
            else:
                self._events.put(("discord_disabled", None))
            if mobile_server is not None:
                self._events.put(("mobile_started", mobile_server.address))
        except Exception as exc:
            if mobile_server is not None:
                try:
                    mobile_server.close()
                except Exception:
                    pass
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

            if kind == "mobile":
                method, args, kwargs, reply = payload
                try:
                    if mobile_gateway is None:
                        raise RuntimeError("mobile companion is not running")
                    value = getattr(mobile_gateway, method)(*args, **kwargs)
                except Exception as exc:
                    reply.put((False, exc))
                else:
                    reply.put((True, value))
                continue

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
                    matrix_status = controller.matrix_status()
                    self._events.put(
                        ("persistence", controller.persistence_status())
                    )
                    self._events.put(
                        ("sent", (history, palette, matrix_status))
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
                if mobile_server is not None:
                    try:
                        mobile_server.close()
                    except Exception as exc:
                        shutdown_error = exc
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
