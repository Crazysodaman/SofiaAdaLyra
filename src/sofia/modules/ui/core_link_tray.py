"""Core-free tray/status fallback for an explicitly selected remote Core."""
from __future__ import annotations

from queue import Empty, Queue
import subprocess
import sys
from threading import Thread

from sofia.modules.ui.core_link_desktop import (
    create_core_link_desktop_client_from_environment,
)
from sofia.modules.ui.process_lock import (
    TrayProcessAlreadyRunning, TrayProcessLock, core_link_profile_anchor,
)


def run_core_link_tray() -> int:
    """Run an independent status window where no native tray is guaranteed."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is required for the Core Link status client") from exc

    client = create_core_link_desktop_client_from_environment()
    anchor = core_link_profile_anchor(
        client.transport.binding_store.path, client.binding.binding_id,
    )
    lock = TrayProcessLock(anchor)
    try:
        lock.acquire()
    except TrayProcessAlreadyRunning:
        return 0

    root = tk.Tk()
    root.title(f"Companion Status — {client.binding.remote_core_identity_id}")
    root.geometry("420x150")
    label = ttk.Label(root, text="Connecting…", wraplength=390)
    label.pack(fill="both", expand=True, padx=12, pady=12)
    events: Queue[tuple[bool, object]] = Queue()
    busy = {"value": False}

    def refresh() -> None:
        if busy["value"]:
            return
        busy["value"] = True

        def probe() -> None:
            try:
                events.put((True, client.probe_status()))
            except Exception as exc:
                events.put((False, exc))

        Thread(target=probe, name="core-link-tray-status", daemon=True).start()

    def open_desktop() -> None:
        subprocess.Popen(
            [sys.executable, "-m", "sofia.platform.launcher", "desktop"],
            close_fds=True,
        )

    controls = ttk.Frame(root)
    controls.pack(pady=(0, 10))
    ttk.Button(controls, text="Open Desktop", command=open_desktop).pack(
        side="left", padx=4,
    )
    ttk.Button(controls, text="Refresh", command=refresh).pack(side="left", padx=4)
    ttk.Button(controls, text="Exit Tray", command=root.destroy).pack(
        side="left", padx=4,
    )

    def poll() -> None:
        try:
            ok, value = events.get_nowait()
        except Empty:
            pass
        else:
            busy["value"] = False
            if ok:
                stop = "STOP active" if value.get("operator_stop_active") else "ready"
                label.configure(text=(
                    f"Connected to {value['remote_core_identity_id']} "
                    f"generation {value['remote_core_generation']} — {stop}"
                ))
            else:
                label.configure(text=f"Disconnected: {type(value).__name__}: {value}")
        root.after(500, poll)

    root.after(100, poll)
    refresh()
    try:
        root.mainloop()
    finally:
        lock.release()
    return 0
