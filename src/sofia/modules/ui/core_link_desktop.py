"""Core-free remote Desktop conversation client.

This module intentionally imports no SofiaApplication, Core identity assets,
conversation store, or canonical SQLite owner.  It projects authenticated Core
Link responses and retains only client-owned drafts and uncertain request IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from queue import Empty, Queue
from threading import RLock, Thread
from typing import Callable, Protocol
from uuid import uuid4

from sofia.platform.core_link import (
    CORE_LINK_BINDING_STORE_ENV,
    CoreLinkBinding,
    CoreLinkBindingStore,
    CoreLinkEndpoint,
    CoreLinkTLSCredentials,
    PinnedCoreLinkClient,
)
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.state.atomic_file import atomic_write_text
from sofia.sdk.core_link import CoreLinkRequest, CoreLinkResponseStatus
from sofia.modules.ui.process_lock import (
    DesktopAttentionMailbox,
    DesktopProcessAlreadyRunning,
    DesktopProcessLock,
    core_link_profile_anchor,
)


_STATE_SCHEMA = "companion.ui.core_link_desktop_state.v1"


class RemoteTurnUncertain(RuntimeError):
    """The host may still be processing a turn; it must not be resubmitted."""


class CoreLinkTransport(Protocol):
    def request(self, request: CoreLinkRequest): ...


@dataclass(frozen=True, slots=True)
class RemoteUITextMessage:
    message_id: str
    session_id: str
    actor: str
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CoreLinkDesktopState:
    binding_id: str
    core_identity_id: str
    revision: int = 0
    session_id: str | None = None
    draft: str = ""
    pending_idempotency_key: str | None = None
    pending_content: str | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.binding_id or not self.core_identity_id:
            raise ValueError("binding and Core identity required")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("state revision must be nonnegative")
        if self.session_id is not None and not self.session_id.strip():
            raise ValueError("session_id must be nonempty or None")
        if not isinstance(self.draft, str) or len(self.draft) > 64_000:
            raise ValueError("draft must be bounded text")
        pending = self.pending_idempotency_key is not None
        if pending != (self.pending_content is not None):
            raise ValueError("pending request identity and content must coexist")
        if self.pending_content is not None and not self.pending_content.strip():
            raise ValueError("pending content must be nonempty")
        if self.updated_at is not None and (
            self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")


class CoreLinkDesktopStateStore:
    """Protected client-only JSON; never a conversation or memory authority."""

    def __init__(self, path: Path, binding: CoreLinkBinding) -> None:
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("Core Link Desktop state path must be absolute")
        self.path = path
        self.binding = binding
        self._lock = StateProcessLock(
            path, resource="core-link-ui-state",
            owner_label="Core Link Desktop state writer",
        )

    def _default(self) -> CoreLinkDesktopState:
        return CoreLinkDesktopState(
            self.binding.binding_id, self.binding.remote_core_identity_id,
        )

    def load(self) -> CoreLinkDesktopState:
        if not self.path.exists():
            return self._default()
        if self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("Core Link Desktop state must be a regular file")
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            raise PermissionError("Core Link Desktop state permissions are unsafe")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Core Link Desktop state is unreadable") from exc
        keys = {
            "schema", "binding_id", "core_identity_id", "revision",
            "session_id", "draft", "pending_idempotency_key",
            "pending_content", "updated_at",
        }
        if not isinstance(payload, dict) or set(payload) != keys:
            raise ValueError("Core Link Desktop state has unreviewed fields")
        if payload["schema"] != _STATE_SCHEMA:
            raise ValueError("unsupported Core Link Desktop state schema")
        try:
            state = CoreLinkDesktopState(
                binding_id=payload["binding_id"],
                core_identity_id=payload["core_identity_id"],
                revision=payload["revision"], session_id=payload["session_id"],
                draft=payload["draft"],
                pending_idempotency_key=payload["pending_idempotency_key"],
                pending_content=payload["pending_content"],
                updated_at=(
                    None if payload["updated_at"] is None
                    else datetime.fromisoformat(payload["updated_at"])
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Core Link Desktop state is invalid") from exc
        if (
            state.binding_id != self.binding.binding_id
            or state.core_identity_id != self.binding.remote_core_identity_id
        ):
            raise PermissionError("Core Link Desktop state belongs to another Core")
        return state

    def save(self, state: CoreLinkDesktopState) -> CoreLinkDesktopState:
        if not isinstance(state, CoreLinkDesktopState):
            raise TypeError("state must be CoreLinkDesktopState")
        with self._lock:
            current = self.load()
            if state.revision != current.revision:
                raise RuntimeError("Core Link Desktop state revision conflict")
            now = datetime.now(timezone.utc)
            updated = CoreLinkDesktopState(
                binding_id=state.binding_id,
                core_identity_id=state.core_identity_id,
                revision=state.revision + 1,
                session_id=state.session_id, draft=state.draft,
                pending_idempotency_key=state.pending_idempotency_key,
                pending_content=state.pending_content, updated_at=now,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.parent.is_symlink():
                raise PermissionError("Core Link client state directory is a symlink")
            payload = {
                "schema": _STATE_SCHEMA,
                "binding_id": updated.binding_id,
                "core_identity_id": updated.core_identity_id,
                "revision": updated.revision,
                "session_id": updated.session_id,
                "draft": updated.draft,
                "pending_idempotency_key": updated.pending_idempotency_key,
                "pending_content": updated.pending_content,
                "updated_at": updated.updated_at.isoformat(),
            }
            atomic_write_text(self.path, json.dumps(payload, sort_keys=True) + "\n")
            if os.name != "nt":
                self.path.chmod(0o600)
            return updated


class CoreLinkDesktopClient:
    """Stateful remote chat projection with durable uncertain-turn recovery."""

    def __init__(
        self, transport: CoreLinkTransport, binding: CoreLinkBinding,
        state_store: CoreLinkDesktopStateStore, *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not callable(getattr(transport, "request", None)):
            raise TypeError("transport must implement request()")
        if state_store.binding != binding:
            raise ValueError("state store must be bound to the selected Core")
        self.transport = transport
        self.binding = binding
        self.state_store = state_store
        self.clock = clock
        self._state = state_store.load()
        self._messages: tuple[RemoteUITextMessage, ...] = ()
        self._lock = RLock()

    def _request(
        self, operation: str, payload: dict[str, object], *,
        idempotency_key: str | None = None,
    ):
        now = self.clock().astimezone(timezone.utc)
        request = CoreLinkRequest(
            request_id=f"request:{uuid4().hex}",
            idempotency_key=idempotency_key or f"desktop:{uuid4().hex}",
            local_platform_id=self.binding.local_platform_id,
            remote_platform_id=self.binding.remote_platform_id,
            remote_core_identity_id=self.binding.remote_core_identity_id,
            remote_core_generation=self.binding.remote_core_generation,
            operation=operation, payload=payload, created_at=now,
            deadline=now + timedelta(seconds=30),
            protocol=self.binding.protocol_version,
        )
        return self.transport.request(request)

    @staticmethod
    def _require_completed(response, operation: str) -> dict[str, object]:
        if response.status is not CoreLinkResponseStatus.COMPLETED:
            raise RuntimeError(
                f"Core Link {operation} returned {response.status.value}"
            )
        return response.payload

    @property
    def session_id(self) -> str | None:
        return self._state.session_id

    @property
    def draft(self) -> str:
        return self._state.draft

    @property
    def messages(self) -> tuple[RemoteUITextMessage, ...]:
        return self._messages

    def probe_status(self) -> dict[str, object]:
        """Read authenticated host status without creating a conversation."""
        with self._lock:
            return self._require_completed(self._request("status", {}), "status")

    def start(self) -> tuple[RemoteUITextMessage, ...]:
        with self._lock:
            status = self.probe_status()
            if (
                status.get("remote_core_identity_id")
                != self.binding.remote_core_identity_id
                or status.get("remote_core_generation")
                != self.binding.remote_core_generation
            ):
                raise PermissionError("Core Link status identity changed")
            if self._state.session_id is None:
                payload = self._require_completed(
                    self._request(
                        "conversation.create", {},
                        idempotency_key=f"desktop-session:{self.binding.binding_id}",
                    ),
                    "conversation.create",
                )
                self._state = self.state_store.save(CoreLinkDesktopState(
                    self._state.binding_id, self._state.core_identity_id,
                    revision=self._state.revision,
                    session_id=str(payload["session_id"]), draft=self._state.draft,
                    pending_idempotency_key=self._state.pending_idempotency_key,
                    pending_content=self._state.pending_content,
                ))
            else:
                self._require_completed(self._request(
                    "conversation.select", {"session_id": self._state.session_id},
                ), "conversation.select")
            self.reconcile_pending()
            return self.refresh_history()

    def refresh_history(self) -> tuple[RemoteUITextMessage, ...]:
        if self._state.session_id is None:
            raise RuntimeError("Core Link Desktop has no selected conversation")
        payload = self._require_completed(self._request(
            "conversation.history",
            {"session_id": self._state.session_id, "after": None, "limit": 100},
        ), "conversation.history")
        raw = payload.get("messages")
        if not isinstance(raw, list):
            raise RuntimeError("Core Link history payload is invalid")
        messages: list[RemoteUITextMessage] = []
        for item in raw:
            if not isinstance(item, dict) or set(item) != {
                "message_id", "role", "content", "created_at",
            }:
                raise RuntimeError("Core Link history item is invalid")
            role = item["role"]
            if role not in {"user", "assistant"}:
                raise RuntimeError("Core Link history role is invalid")
            messages.append(RemoteUITextMessage(
                message_id=str(item["message_id"]),
                session_id=self._state.session_id,
                actor="user" if role == "user" else "sofia",
                content=str(item["content"]),
                created_at=datetime.fromisoformat(str(item["created_at"])),
            ))
        self._messages = tuple(messages)
        return self._messages

    def save_draft(self, content: str) -> None:
        if not isinstance(content, str) or len(content) > 64_000:
            raise ValueError("draft must be bounded text")
        with self._lock:
            self._state = self.state_store.save(CoreLinkDesktopState(
                self._state.binding_id, self._state.core_identity_id,
                revision=self._state.revision, session_id=self._state.session_id,
                draft=content,
                pending_idempotency_key=self._state.pending_idempotency_key,
                pending_content=self._state.pending_content,
            ))

    def send(self, content: str) -> tuple[RemoteUITextMessage, ...]:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("message must be nonempty text")
        if self._state.session_id is None:
            raise RuntimeError("Core Link Desktop has no selected conversation")
        with self._lock:
            if self._state.pending_idempotency_key is not None:
                raise RemoteTurnUncertain(
                    "an earlier turn has not been reconciled; refusing duplicate send"
                )
            key = f"desktop-turn:{uuid4().hex}"
            self._state = self.state_store.save(CoreLinkDesktopState(
                self._state.binding_id, self._state.core_identity_id,
                revision=self._state.revision, session_id=self._state.session_id,
                draft=content, pending_idempotency_key=key,
                pending_content=content,
            ))
            response = self._request(
                "conversation.send",
                {
                    "session_id": self._state.session_id,
                    "content": content,
                    "client_created_at": self.clock().isoformat(),
                },
                idempotency_key=key,
            )
            if response.status is not CoreLinkResponseStatus.COMPLETED:
                raise RemoteTurnUncertain(
                    f"remote turn outcome is {response.status.value}; reconcile before retry"
                )
            self._clear_settled_turn()
            return self.refresh_history()

    def _clear_settled_turn(self) -> None:
        self._state = self.state_store.save(CoreLinkDesktopState(
            self._state.binding_id, self._state.core_identity_id,
            revision=self._state.revision, session_id=self._state.session_id,
        ))

    def reconcile_pending(self) -> bool:
        key = self._state.pending_idempotency_key
        if key is None:
            return True
        response = self._request(
            "conversation.result", {"idempotency_key": key},
            idempotency_key=f"result:{key}",
        )
        if response.status is CoreLinkResponseStatus.COMPLETED:
            self._clear_settled_turn()
            return True
        return False


def create_core_link_desktop_client_from_environment() -> CoreLinkDesktopClient:
    """Compose a client solely from an approved binding and protected refs."""
    store_raw = os.environ.get(CORE_LINK_BINDING_STORE_ENV, "").strip()
    if not store_raw:
        raise RuntimeError(f"{CORE_LINK_BINDING_STORE_ENV} is required")
    binding_store = CoreLinkBindingStore(Path(store_raw))
    binding = binding_store.load().selected()
    if binding is None:
        raise RuntimeError("no approved Core Link binding is selected")

    endpoint_id = os.environ.get("SOFIA_CORE_LINK_ENDPOINT_ID", "").strip()
    hostname = os.environ.get("SOFIA_CORE_LINK_ENDPOINT_HOST", "").strip()
    credential_ref = os.environ.get("SOFIA_CORE_LINK_CREDENTIAL_REF", "").strip()
    if endpoint_id != binding.endpoint_id or credential_ref != binding.credential_ref:
        raise PermissionError("Core Link endpoint or credential reference changed")
    try:
        port = int(os.environ.get("SOFIA_CORE_LINK_ENDPOINT_PORT", ""))
    except ValueError as exc:
        raise ValueError("SOFIA_CORE_LINK_ENDPOINT_PORT must be an integer") from exc
    endpoint = CoreLinkEndpoint(endpoint_id, hostname, port)

    def path(name: str) -> Path:
        raw = os.environ.get(name, "").strip()
        value = Path(raw)
        if not raw or not value.is_absolute() or not value.is_file():
            raise ValueError(f"{name} must identify an existing absolute file")
        return value

    credentials = CoreLinkTLSCredentials(
        path("SOFIA_CORE_LINK_CLIENT_CA_FILE"),
        path("SOFIA_CORE_LINK_CLIENT_CERTIFICATE"),
        path("SOFIA_CORE_LINK_CLIENT_PRIVATE_KEY"),
    )
    def resolve_credentials(requested: str) -> CoreLinkTLSCredentials:
        if requested != credential_ref:
            raise PermissionError("unknown Core Link credential reference")
        return credentials

    transport = PinnedCoreLinkClient(
        binding_store,
        endpoint_resolver=lambda requested: endpoint if requested == endpoint_id else None,
        credential_resolver=resolve_credentials,
    )
    state_raw = os.environ.get("SOFIA_CORE_LINK_DESKTOP_STATE", "").strip()
    state_path = (
        Path(state_raw)
        if state_raw else core_link_profile_anchor(
            binding_store.path, binding.binding_id,
        ).with_suffix(".desktop-state.json")
    )
    if not state_path.is_absolute():
        raise ValueError("SOFIA_CORE_LINK_DESKTOP_STATE must be absolute")
    return CoreLinkDesktopClient(
        transport, binding, CoreLinkDesktopStateStore(state_path, binding),
    )


def run_core_link_desktop() -> int:
    """Run a minimal authenticated remote chat without constructing Core."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is required for the Desktop client") from exc

    client = create_core_link_desktop_client_from_environment()
    anchor = core_link_profile_anchor(
        client.transport.binding_store.path, client.binding.binding_id,
    )
    lock = DesktopProcessLock(anchor)
    mailbox = DesktopAttentionMailbox(lock)
    try:
        lock.acquire()
    except DesktopProcessAlreadyRunning:
        mailbox.request()
        return 0

    root = tk.Tk()
    root.title(f"Companion Desktop — {client.binding.remote_core_identity_id}")
    root.geometry("760x560")
    history = tk.Text(root, wrap="word", state="disabled")
    history.pack(fill="both", expand=True, padx=10, pady=10)
    entry = ttk.Entry(root)
    entry.pack(fill="x", padx=10, pady=(0, 8))
    status = ttk.Label(root, text="Connecting…")
    status.pack(fill="x", padx=10, pady=(0, 8))
    events: Queue[tuple[str, object]] = Queue()
    busy = {"value": False}

    def render(messages: tuple[RemoteUITextMessage, ...]) -> None:
        history.configure(state="normal")
        history.delete("1.0", "end")
        for message in messages:
            history.insert("end", f"{message.actor}: {message.content}\n\n")
        history.configure(state="disabled")
        history.see("end")

    def task(kind: str, action) -> None:
        if busy["value"]:
            return
        busy["value"] = True
        status.configure(text=f"{kind}…")
        Thread(
            target=lambda: _desktop_task(events, kind, action),
            name=f"core-link-desktop-{kind}", daemon=True,
        ).start()

    def send(_event=None) -> None:
        content = entry.get()
        if not content.strip():
            return
        client.save_draft(content)
        task("Sending", lambda: client.send(content))

    button = ttk.Button(root, text="Send", command=send)
    button.pack(pady=(0, 10))
    entry.bind("<Return>", send)

    def poll() -> None:
        try:
            while True:
                kind, value = events.get_nowait()
                busy["value"] = False
                if kind == "ok":
                    render(value)
                    entry.delete(0, "end")
                    entry.insert(0, client.draft)
                    status.configure(text="Connected")
                else:
                    status.configure(text=f"Disconnected: {type(value).__name__}: {value}")
        except Empty:
            pass
        try:
            if mailbox.consume():
                root.deiconify()
                root.lift()
                root.focus_force()
        except Exception as exc:
            status.configure(text=f"Attention request error: {type(exc).__name__}")
        root.after(250, poll)

    def close() -> None:
        try:
            client.save_draft(entry.get())
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    task("Connecting", client.start)
    try:
        root.mainloop()
    finally:
        lock.release()
    return 0


def _desktop_task(events: Queue[tuple[str, object]], kind: str, action) -> None:
    try:
        events.put(("ok", action()))
    except Exception as exc:
        events.put(("error", exc))
