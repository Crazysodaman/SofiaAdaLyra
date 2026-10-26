"""Read-only Core Link Platform Control Center projection."""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from sofia.modules.ui.core_link_desktop import (
    create_core_link_desktop_client_from_environment,
)
from sofia.modules.ui.core_link_settings import CoreLinkSettingsClient
from sofia.modules.ui.process_lock import (
    ControlCenterProcessAlreadyRunning, ControlCenterProcessLock,
    core_link_profile_anchor,
)


def run_core_link_control_center() -> int:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is required for Platform Control Center") from exc

    desktop = create_core_link_desktop_client_from_environment()
    settings = CoreLinkSettingsClient(desktop.transport, desktop.binding)
    anchor = core_link_profile_anchor(
        desktop.transport.binding_store.path, desktop.binding.binding_id,
    )
    lock = ControlCenterProcessLock(anchor)
    try:
        lock.acquire()
    except ControlCenterProcessAlreadyRunning:
        return 0

    root = tk.Tk()
    root.title(f"Platform Control Center — {desktop.binding.remote_core_identity_id}")
    root.geometry("680x400")
    body = tk.Text(root, wrap="word", state="disabled")
    body.pack(fill="both", expand=True, padx=10, pady=10)
    status_label = ttk.Label(root, text="Connecting…")
    status_label.pack(fill="x", padx=10, pady=(0, 8))
    events: Queue[tuple[bool, object]] = Queue()
    busy = {"value": False}

    def refresh():
        if busy["value"]:
            return
        busy["value"] = True

        def work():
            try:
                events.put((True, (desktop.probe_status(), settings.refresh())))
            except Exception as exc:
                events.put((False, exc))

        Thread(target=work, name="core-link-control-center", daemon=True).start()

    ttk.Button(root, text="Refresh", command=refresh).pack(pady=(0, 10))

    def poll():
        try:
            ok, value = events.get_nowait()
        except Empty:
            pass
        else:
            busy["value"] = False
            if ok:
                host, snapshot = value
                lines = [
                    f"Core identity: {host['remote_core_identity_id']}",
                    f"Core generation: {host['remote_core_generation']}",
                    f"Platform: {host['remote_platform_id']}",
                    f"Runtime state: {host['state']}",
                    f"Operator STOP: {host['operator_stop_active']}",
                    f"Settings saved revision: {snapshot['revision']}",
                    f"Settings effective revision: {snapshot['effective_revision']}",
                    f"Authorized settings fields: {len(snapshot['values'])}",
                ]
                body.configure(state="normal")
                body.delete("1.0", "end")
                body.insert("end", "\n".join(lines))
                body.configure(state="disabled")
                status_label.configure(text="Authenticated observations refreshed")
            else:
                status_label.configure(
                    text=f"Unavailable: {type(value).__name__}: {value}"
                )
        root.after(250, poll)

    root.after(100, poll)
    refresh()
    try:
        root.mainloop()
    finally:
        lock.release()
    return 0
