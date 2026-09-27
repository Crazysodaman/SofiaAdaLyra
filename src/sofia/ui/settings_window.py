"""Tkinter master settings window for the Sofía desktop/tray client."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from sofia.config import create_default_configuration
from .control_center import (
    DesktopControlSettings,
    DesktopControlSettingsStore,
    GameMode,
    MASTER_SETTINGS_SECTIONS,
    RemoteChatMode,
)
from .windows_startup import configure_windows_startup


def _ensure_state_database(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path):
            pass


def run_settings_window() -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    config = create_default_configuration()
    _ensure_state_database(config.state_path)
    store = DesktopControlSettingsStore(config.state_path)
    current = store.load()

    root = tk.Tk()
    root.title("Sofía Settings")
    root.geometry("860x620")
    root.minsize(720, 520)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=12)

    frames = {}
    for name in MASTER_SETTINGS_SECTIONS:
        frame = ttk.Frame(notebook, padding=14)
        notebook.add(frame, text=name)
        frames[name] = frame

    close_to_tray = tk.BooleanVar(value=current.close_to_tray)
    start_windows = tk.BooleanVar(value=current.start_with_windows)
    game_mode = tk.StringVar(value=current.game_mode.value)
    remote_mode = tk.StringVar(value=current.remote_chat_mode.value)
    pinned_endpoint = tk.StringVar(value=current.pinned_chat_endpoint or "")
    runtime_service = tk.StringVar(value=current.runtime_service_name)
    llm_service = tk.StringVar(value=current.llm_service_name)

    general = frames["General"]
    ttk.Checkbutton(general, text="Close chat window to system tray", variable=close_to_tray).pack(anchor="w", pady=4)
    ttk.Checkbutton(general, text="Start tray client with Windows", variable=start_windows).pack(anchor="w", pady=4)

    workloads = frames["Workloads"]
    ttk.Label(workloads, text="Game Mode").pack(anchor="w")
    ttk.Combobox(
        workloads,
        textvariable=game_mode,
        values=tuple(value.value for value in GameMode),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 10))
    ttk.Label(
        workloads,
        text="Auto uses observed activity. On protects this machine for gaming. Off disables gaming protection.",
        wraplength=680,
    ).pack(anchor="w")

    chat = frames["Chat"]
    ttk.Label(chat, text="Desktop chat routing").pack(anchor="w")
    ttk.Combobox(
        chat,
        textvariable=remote_mode,
        values=tuple(value.value for value in RemoteChatMode),
        state="readonly",
    ).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(chat, text="Pinned runtime endpoint").pack(anchor="w")
    ttk.Entry(chat, textvariable=pinned_endpoint).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(
        chat,
        text="Fleet-auto follows the currently authoritative ready Sofía runtime. Network transport still requires an authenticated remote-chat adapter.",
        wraplength=680,
    ).pack(anchor="w")

    models = frames["Models"]
    ttk.Label(models, text="LLM service name").pack(anchor="w")
    ttk.Entry(models, textvariable=llm_service).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(models, text="Sofía runtime service name").pack(anchor="w")
    ttk.Entry(models, textvariable=runtime_service).pack(anchor="w", fill="x", pady=(2, 8))
    ttk.Label(
        models,
        text="LLM start/stop/restart is independent from the Sofía runtime. Model unload keeps the Ollama service running.",
        wraplength=680,
    ).pack(anchor="w")

    descriptions = {
        "Sofía": "Identity/personality presentation controls live here without granting protected-state mutation.",
        "ACT": "Initiative, quiet hours, delivery channels, mute/stop and notification policy.",
        "Fleet": "Hosts, enrollment, discovery scope, maintenance policy and health.",
        "Integrations": "Discord, Home Assistant, JMRI, GitHub, Steam/local gaming evidence and other adapters.",
        "Environment": "Configured site/host location, weather and environment providers.",
        "Avatar": "Presentation, wardrobe, appearance and renderer controls.",
        "Memory": "Retention, review, promotion and privacy controls.",
        "EVOLVE": "Reviewed revisions, approvals and rollback history.",
        "Safety & Authority": "Standing grants, revocations, emergency controls and approval policy.",
        "Advanced": "Certificates, logs, databases, networking and diagnostics.",
    }
    for section, description in descriptions.items():
        ttk.Label(frames[section], text=description, wraplength=680).pack(anchor="w")

    status = tk.StringVar(value="")
    bottom = ttk.Frame(root, padding=(12, 0, 12, 12))
    bottom.pack(fill="x")
    ttk.Label(bottom, textvariable=status).pack(side="left")

    def save() -> None:
        try:
            updated = DesktopControlSettings(
                close_to_tray=bool(close_to_tray.get()),
                start_with_windows=bool(start_windows.get()),
                game_mode=GameMode(game_mode.get()),
                remote_chat_mode=RemoteChatMode(remote_mode.get()),
                pinned_chat_endpoint=(pinned_endpoint.get().strip() or None),
                runtime_service_name=runtime_service.get().strip(),
                llm_service_name=llm_service.get().strip(),
            )
            configure_windows_startup(updated.start_with_windows)
            store.save(updated, at=datetime.now(timezone.utc))
            status.set("Saved")
        except Exception as exc:
            messagebox.showerror("Settings not saved", f"{type(exc).__name__}: {exc}", parent=root)

    ttk.Button(bottom, text="Save", command=save).pack(side="right")
    ttk.Button(bottom, text="Close", command=root.destroy).pack(side="right", padx=(0, 8))

    root.mainloop()
    return 0


def main() -> int:
    return run_settings_window()


if __name__ == "__main__":
    raise SystemExit(main())
