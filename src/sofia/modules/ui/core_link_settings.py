"""Core-free authenticated Settings client for an approved Core Link."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from queue import Empty, Queue
from threading import RLock, Thread
from time import monotonic
from uuid import uuid4

from sofia.modules.ui.core_link_desktop import (
    create_core_link_transport_from_environment,
)
from sofia.modules.ui.process_lock import (
    SettingsProcessAlreadyRunning, SettingsProcessLock,
    core_link_profile_anchor,
)
from sofia.sdk.core_link import CoreLinkRequest, CoreLinkResponseStatus
from sofia.sdk.module_settings import module_settings_contract_from_document


class CoreLinkSettingsClient:
    """Revisioned settings projection; it never opens canonical state."""

    def __init__(self, transport, binding, *, clock=lambda: datetime.now(timezone.utc)):
        if not callable(getattr(transport, "request", None)):
            raise TypeError("transport must implement request()")
        self.transport = transport
        self.binding = binding
        self.clock = clock
        self._lock = RLock()
        self._snapshot: dict[str, object] | None = None

    def _request(self, operation: str, payload: dict[str, object], *, key=None):
        now = self.clock().astimezone(timezone.utc)
        return self.transport.request(CoreLinkRequest(
            request_id=f"request:{uuid4().hex}",
            idempotency_key=key or f"settings:{uuid4().hex}",
            local_platform_id=self.binding.local_platform_id,
            remote_platform_id=self.binding.remote_platform_id,
            remote_core_identity_id=self.binding.remote_core_identity_id,
            remote_core_generation=self.binding.remote_core_generation,
            operation=operation, payload=payload, created_at=now,
            deadline=now + timedelta(seconds=30),
            protocol=self.binding.protocol_version,
        ))

    @staticmethod
    def _complete(response, operation: str) -> dict[str, object]:
        if response.status is CoreLinkResponseStatus.CONFLICT:
            raise RuntimeError(f"{operation} conflict: {response.payload.get('error', '')}")
        if response.status is not CoreLinkResponseStatus.COMPLETED:
            raise RuntimeError(f"{operation} returned {response.status.value}")
        return response.payload

    @property
    def snapshot(self) -> dict[str, object] | None:
        return self._snapshot

    def refresh(self) -> dict[str, object]:
        with self._lock:
            payload = self._complete(
                self._request("settings.snapshot", {}), "settings snapshot",
            )
            required = {
                "schema_version", "revision", "effective_revision", "values",
                "contracts",
            }
            if set(payload) != required or type(payload["revision"]) is not int:
                raise ValueError("host returned an invalid settings snapshot")
            if not isinstance(payload["values"], dict) or not isinstance(
                payload["contracts"], dict
            ):
                raise ValueError("host returned invalid settings values")
            self._snapshot = payload
            return payload

    def update(self, field: str, value: object, *, idempotency_key=None):
        with self._lock:
            snapshot = self._snapshot or self.refresh()
            contracts = snapshot["contracts"]
            if field not in contracts:
                raise PermissionError("setting is not in the authorized projection")
            response = self._request(
                "settings.update", {
                    "expected_revision": snapshot["revision"],
                    "changes": {field: value},
                }, key=idempotency_key,
            )
            receipt = self._complete(response, "settings update")
            if set(receipt) != {
                "revision", "effective_revision", "apply_state",
                "changed_fields", "apply_classes", "error",
            }:
                raise ValueError("host returned an invalid settings receipt")
            # Always resynchronize the authoritative projection.  This also
            # makes an apply failure visible without pretending the save failed.
            self.refresh()
            return receipt

    def events(self, *, after_revision: int, limit: int = 100):
        response = self._request(
            "settings.events", {"after_revision": after_revision, "limit": limit},
        )
        payload = self._complete(response, "settings events")
        if set(payload) != {"events"} or not isinstance(payload["events"], list):
            raise ValueError("host returned an invalid settings event page")
        return payload["events"]

    def module_catalog(self) -> tuple[dict[str, object], ...]:
        payload = self._complete(
            self._request("module.settings.list", {}), "module settings list",
        )
        if set(payload) != {"modules"} or not isinstance(payload["modules"], list):
            raise ValueError("host returned an invalid module settings catalog")
        modules = tuple(payload["modules"])
        if any(
            not isinstance(item, dict)
            or set(item) != {
                "module_id", "package_digest", "lifecycle",
                "lifecycle_revision", "revision", "effective_revision",
                "settings_identity", "contract",
            }
            for item in modules
        ):
            raise ValueError("host returned an invalid module settings entry")
        for item in modules:
            self._validate_module_projection(item, catalog=True)
        return modules

    @staticmethod
    def _validate_module_projection(
        value: dict[str, object], *, catalog: bool,
    ) -> None:
        digest = value.get("package_digest")
        if (
            not isinstance(value.get("module_id"), str)
            or not value["module_id"]
            or not isinstance(digest, str) or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(value.get("lifecycle"), str)
            or type(value.get("lifecycle_revision")) is not int
            or value["lifecycle_revision"] < 1
            or type(value.get("revision")) is not int
            or value["revision"] < 0
            or type(value.get("effective_revision")) is not int
            or not 0 <= value["effective_revision"] <= value["revision"]
        ):
            raise ValueError("host returned invalid module settings identity")
        if catalog and value.get("settings_identity") not in {
            "current", "migration_required",
        }:
            raise ValueError("host returned invalid module settings state")
        try:
            module_settings_contract_from_document(value.get("contract"))
        except (TypeError, ValueError) as exc:
            raise ValueError("host returned invalid signed settings contract") from exc

    def module_snapshot(self, module_id: str) -> dict[str, object]:
        payload = self._complete(
            self._request("module.settings.snapshot", {"module_id": module_id}),
            "module settings snapshot",
        )
        if set(payload) != {
            "module_id", "package_digest", "lifecycle", "lifecycle_revision",
            "revision", "effective_revision", "values", "contract",
        } or not isinstance(payload["values"], dict) or not isinstance(
            payload["contract"], dict
        ):
            raise ValueError("host returned an invalid module settings snapshot")
        self._validate_module_projection(payload, catalog=False)
        return payload

    def update_module(
        self, snapshot: dict[str, object], changes: dict[str, object], *,
        approval_ref: str, idempotency_key: str | None = None,
    ) -> dict[str, object]:
        required = {
            "module_id", "package_digest", "lifecycle_revision", "revision",
        }
        if not required.issubset(snapshot):
            raise ValueError("module settings snapshot lacks revision identity")
        receipt = self._complete(
            self._request(
                "module.settings.update", {
                    "module_id": snapshot["module_id"],
                    "expected_package_digest": snapshot["package_digest"],
                    "expected_lifecycle_revision": snapshot["lifecycle_revision"],
                    "expected_revision": snapshot["revision"],
                    "approval_ref": approval_ref,
                    "changes": changes,
                }, key=idempotency_key,
            ),
            "module settings update",
        )
        if set(receipt) != {
            "module_id", "package_digest", "revision", "effective_revision",
            "apply_state", "changed_fields", "apply_classes", "error",
        }:
            raise ValueError("host returned an invalid module settings receipt")
        return receipt


def create_core_link_settings_client_from_environment() -> CoreLinkSettingsClient:
    transport, _, binding = create_core_link_transport_from_environment()
    return CoreLinkSettingsClient(transport, binding)


def run_core_link_settings() -> int:
    """Run a typed remote editor with truthful saved/effective status."""
    try:
        import tkinter as tk
        from tkinter import simpledialog, ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is required for the Settings client") from exc

    client = create_core_link_settings_client_from_environment()
    anchor = core_link_profile_anchor(
        client.transport.binding_store.path, client.binding.binding_id,
    )
    lock = SettingsProcessLock(anchor)
    try:
        lock.acquire()
    except SettingsProcessAlreadyRunning:
        return 0

    root = tk.Tk()
    root.title(f"Companion Settings — {client.binding.remote_core_identity_id}")
    root.geometry("900x600")
    tree = ttk.Treeview(
        root, columns=("value", "owner", "apply"), show="tree headings",
    )
    tree.heading("#0", text="Setting")
    tree.heading("value", text="Canonical value")
    tree.heading("owner", text="Owner")
    tree.heading("apply", text="Apply boundary")
    tree.column("#0", width=280)
    tree.column("value", width=330)
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    status = ttk.Label(root, text="Connecting…", wraplength=860)
    status.pack(fill="x", padx=10, pady=(0, 10))
    events: Queue[tuple[str, object]] = Queue()
    busy = {"value": False}
    next_event_poll = {"at": monotonic() + 2.0}

    def render(snapshot):
        tree.delete(*tree.get_children())
        contracts = snapshot["contracts"]
        for field, value in sorted(snapshot["values"].items()):
            contract = contracts[field]
            tree.insert("", "end", iid=field, text=field, values=(
                json.dumps(value, ensure_ascii=False),
                contract["owner"], contract["apply_class"],
            ))
        status.configure(text=(
            f"Connected — saved revision {snapshot['revision']}, "
            f"effective revision {snapshot['effective_revision']}"
        ))

    def task(kind, action):
        if busy["value"]:
            return
        busy["value"] = True
        status.configure(text=f"{kind}…")
        Thread(
            target=lambda: _settings_task(events, kind, action),
            name=f"core-link-settings-{kind}", daemon=True,
        ).start()

    def edit(_event=None):
        selected = tree.selection()
        if not selected or client.snapshot is None:
            return
        field = selected[0]
        current = client.snapshot["values"][field]
        raw = simpledialog.askstring(
            "Edit canonical setting",
            f"{field}\nEnter a JSON value. Validation occurs on the Core Host.",
            initialvalue=json.dumps(current, ensure_ascii=False), parent=root,
        )
        if raw is None:
            return
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            status.configure(text=f"Invalid JSON: {exc}")
            return
        task("Saving", lambda: client.update(field, value))

    tree.bind("<Double-1>", edit)
    controls = ttk.Frame(root)
    controls.pack(pady=(0, 10))
    ttk.Button(controls, text="Refresh", command=lambda: task("Refreshing", client.refresh)).pack(side="left", padx=4)
    ttk.Button(controls, text="Edit selected", command=edit).pack(side="left", padx=4)
    ttk.Button(
        controls, text="Module Settings…",
        command=lambda: _open_module_settings_window(root, client),
    ).pack(side="left", padx=4)
    ttk.Button(controls, text="Close Settings", command=root.destroy).pack(side="left", padx=4)

    def poll():
        try:
            kind, value = events.get_nowait()
        except Empty:
            pass
        else:
            busy["value"] = False
            if kind == "ok":
                if isinstance(value, dict) and "values" in value:
                    render(value)
                else:
                    render(client.snapshot)
                    status.configure(text=(
                        f"Saved revision {value['revision']} — "
                        f"{value['apply_state']}"
                        + ("; " + value["error"] if value.get("error") else "")
                    ))
            elif kind == "changed":
                if value:
                    task("Synchronizing", client.refresh)
                else:
                    render(client.snapshot)
            else:
                status.configure(text=f"Not applied: {type(value).__name__}: {value}")
        if (
            not busy["value"] and client.snapshot is not None
            and monotonic() >= next_event_poll["at"]
        ):
            busy["value"] = True
            next_event_poll["at"] = monotonic() + 2.0

            def check_events():
                try:
                    changed = bool(client.events(
                        after_revision=client.snapshot["revision"], limit=100,
                    ))
                    events.put(("changed", changed))
                except Exception as exc:
                    events.put(("error", exc))

            Thread(
                target=check_events, name="core-link-settings-events", daemon=True,
            ).start()
        root.after(250, poll)

    root.after(100, poll)
    task("Connecting", client.refresh)
    try:
        root.mainloop()
    finally:
        lock.release()
    return 0


def _settings_task(events, kind, action):
    try:
        events.put(("ok", action()))
    except Exception as exc:
        events.put(("error", exc))


def _open_module_settings_window(parent, client: CoreLinkSettingsClient) -> None:
    """Render module-owned fields from authenticated signed contracts."""
    import tkinter as tk
    from tkinter import simpledialog, ttk

    window = tk.Toplevel(parent)
    window.title("Module Settings")
    window.geometry("980x620")
    modules = ttk.Treeview(
        window, columns=("lifecycle", "saved", "effective"),
        show="tree headings", height=8,
    )
    modules.heading("#0", text="Module")
    modules.heading("lifecycle", text="Lifecycle")
    modules.heading("saved", text="Saved")
    modules.heading("effective", text="Effective")
    modules.pack(fill="x", padx=10, pady=(10, 5))
    fields = ttk.Treeview(
        window, columns=("value", "type", "apply"), show="tree headings",
    )
    fields.heading("#0", text="Setting")
    fields.heading("value", text="Value")
    fields.heading("type", text="Type")
    fields.heading("apply", text="Apply boundary")
    fields.column("#0", width=260)
    fields.column("value", width=340)
    fields.pack(fill="both", expand=True, padx=10, pady=5)
    status = ttk.Label(
        window,
        text="Loading authenticated module contracts…",
        wraplength=940,
    )
    status.pack(fill="x", padx=10, pady=5)
    events: Queue[tuple[str, object]] = Queue()
    state: dict[str, object] = {"busy": False, "snapshot": None}

    def start(kind, action):
        if state["busy"]:
            return
        state["busy"] = True
        status.configure(text=f"{kind}…")
        Thread(
            target=lambda: _settings_task(events, kind, action),
            name="core-link-module-settings", daemon=True,
        ).start()

    def render_catalog(catalog):
        modules.delete(*modules.get_children())
        for item in catalog:
            modules.insert(
                "", "end", iid=item["module_id"], text=item["module_id"],
                values=(
                    item["lifecycle"], item["revision"],
                    item["effective_revision"],
                ),
            )
        status.configure(text=(
            "Select an installed module. Values remain canonical on the Core "
            "Host; this client has no SQLite access."
        ))

    def render_snapshot(snapshot):
        state["snapshot"] = snapshot
        fields.delete(*fields.get_children())
        values = snapshot["values"]
        contract_fields = snapshot["contract"].get("fields", [])
        for field in contract_fields:
            field_id = field["field_id"]
            value = values.get(field_id, "<not configured>")
            fields.insert(
                "", "end", iid=field_id, text=field["label"],
                values=(
                    json.dumps(value, ensure_ascii=False),
                    field["value_type"], field["apply_class"],
                ),
            )
        status.configure(text=(
            f"{snapshot['module_id']} — saved revision {snapshot['revision']}; "
            f"effective revision {snapshot['effective_revision']}; "
            f"lifecycle {snapshot['lifecycle']}"
        ))

    def selected_module(_event=None):
        selected = modules.selection()
        if selected:
            start(
                "Loading module settings",
                lambda: client.module_snapshot(selected[0]),
            )

    def edit_field(_event=None):
        selected = fields.selection()
        snapshot = state["snapshot"]
        if not selected or not isinstance(snapshot, dict):
            return
        field_id = selected[0]
        current = snapshot["values"].get(field_id)
        field_contract = next(
            item for item in snapshot["contract"].get("fields", [])
            if item.get("field_id") == field_id
        )
        if field_contract.get("secret_reference"):
            current = None
        raw = simpledialog.askstring(
            "Edit module setting",
            f"{field_id}\nEnter a JSON value. The signed module contract "
            "validates it on the Core Host.",
            initialvalue=("" if current is None else json.dumps(
                current, ensure_ascii=False,
            )),
            parent=window,
        )
        if raw is None:
            return
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            status.configure(text=f"Invalid JSON: {exc}")
            return
        approval = simpledialog.askstring(
            "Owner approval required",
            "Enter the exact unconsumed owner/FIDO approval reference for "
            "this package, revision, audience, and field set.",
            parent=window,
        )
        if not approval:
            status.configure(text="No change sent: exact owner approval is required.")
            return
        start(
            "Saving module setting",
            lambda: (
                client.update_module(
                    snapshot, {field_id: value}, approval_ref=approval,
                ),
                client.module_snapshot(snapshot["module_id"]),
            ),
        )

    modules.bind("<<TreeviewSelect>>", selected_module)
    fields.bind("<Double-1>", edit_field)
    controls = ttk.Frame(window)
    controls.pack(pady=(0, 10))
    ttk.Button(
        controls, text="Refresh modules",
        command=lambda: start("Refreshing modules", client.module_catalog),
    ).pack(side="left", padx=4)
    ttk.Button(
        controls, text="Edit selected setting", command=edit_field,
    ).pack(side="left", padx=4)
    ttk.Button(controls, text="Close", command=window.destroy).pack(
        side="left", padx=4,
    )

    def poll():
        try:
            kind, value = events.get_nowait()
        except Empty:
            pass
        else:
            state["busy"] = False
            if kind == "error":
                status.configure(text=f"Not applied: {type(value).__name__}: {value}")
            elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], dict):
                receipt, snapshot = value
                render_snapshot(snapshot)
                status.configure(text=(
                    f"Saved revision {receipt['revision']} — "
                    f"{receipt['apply_state']}"
                    + (f"; {receipt['error']}" if receipt.get("error") else "")
                ))
            elif isinstance(value, tuple):
                render_catalog(value)
            elif isinstance(value, dict) and "contract" in value:
                render_snapshot(value)
        if window.winfo_exists():
            window.after(200, poll)

    window.after(100, poll)
    start("Loading modules", client.module_catalog)
