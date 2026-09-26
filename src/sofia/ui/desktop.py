"""Low-resource Windows desktop shell for Sofía.

Tkinter is imported lazily so headless tests and non-desktop package consumers
do not require a display server. The shell uses one canonical SofiaApplication
and its text_ui adapter. No renderer, voice, browser, or raw OS-control surface
is introduced here.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Any

from sofia.application import SofiaApplication
from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.theme import ThemePalette, canonical_theme


class _TkDesktopWorkbench:
    def __init__(
        self,
        *,
        tk: Any,
        ttk: Any,
        root: Any,
        controller: DesktopWorkbenchController,
        session_id: str | None,
    ) -> None:
        self._tk = tk
        self._ttk = ttk
        self._root = root
        self._controller = controller
        self._session_id = session_id
        self._events: Queue[tuple[str, object]] = Queue()
        self._busy = False
        self._close_requested = False
        self._last_rendered_ids: tuple[str, ...] = ()
        self._palette = canonical_theme()
        self._adaptive_theme = self._tk.BooleanVar(
            master=self._root,
            value=True,
        )
        self._theme_name = self._tk.StringVar(
            master=self._root,
            value="Theme: canonical",
        )

        self._configure_window()
        self._build_widgets()
        self._set_enabled(False)
        self._status.set("Starting Sofía...")
        self._root.protocol("WM_DELETE_WINDOW", self._request_close)
        self._root.after(80, self._poll_events)
        self._root.after(
            60_000,
            self._refresh_theme_timer,
        )
        self._start_background()

    def _configure_window(self) -> None:
        self._root.title("Sofía Ada Lyra")
        self._root.geometry("1040x720")
        self._root.minsize(720, 480)
        self._root.configure(
            bg=self._palette.background
        )

        self._style = self._ttk.Style(self._root)
        try:
            self._style.theme_use("clam")
        except self._tk.TclError:
            pass
        self._configure_ttk_palette(
            self._palette
        )

    def _build_widgets(self) -> None:
        outer = self._ttk.Frame(
            self._root,
            style="Sofia.TFrame",
            padding=14,
        )
        outer.pack(fill="both", expand=True)

        header = self._ttk.Frame(
            outer,
            style="Sofia.TFrame",
        )
        header.pack(fill="x", pady=(0, 10))

        title = self._ttk.Label(
            header,
            text="SOFÍA ADA LYRA  //  LOCAL WORKBENCH",
            style="Sofia.TLabel",
        )
        title.pack(side="left")

        theme_label = self._ttk.Label(
            header,
            textvariable=self._theme_name,
            style="SofiaStatus.TLabel",
        )
        theme_label.pack(
            side="left",
            padx=(16, 0),
        )

        adaptive = self._ttk.Checkbutton(
            header,
            text="Adaptive theme",
            variable=self._adaptive_theme,
            command=self._refresh_theme,
            style="Sofia.TCheckbutton",
        )
        adaptive.pack(
            side="right",
            padx=(10, 0),
        )

        self._status = self._tk.StringVar(value="")
        status = self._ttk.Label(
            header,
            textvariable=self._status,
            style="SofiaStatus.TLabel",
        )
        status.pack(side="right")

        self._history = self._tk.Text(
            outer,
            wrap="word",
            state="disabled",
            bg=self._palette.panel,
            fg=self._palette.text,
            insertbackground=self._palette.secondary,
            selectbackground=self._palette.primary,
            relief="flat",
            padx=14,
            pady=14,
            font=("Segoe UI", 11),
        )
        self._history.pack(fill="both", expand=True)
        self._history.tag_configure(
            "user",
            foreground=self._palette.secondary,
            spacing1=8,
            spacing3=4,
        )
        self._history.tag_configure(
            "sofia",
            foreground=self._palette.tertiary,
            spacing1=8,
            spacing3=4,
        )
        self._history.tag_configure(
            "body",
            foreground=self._palette.text,
            lmargin1=12,
            lmargin2=12,
            spacing3=8,
        )

        composer = self._ttk.Frame(
            outer,
            style="Sofia.TFrame",
        )
        composer.pack(fill="x", pady=(10, 0))

        self._input = self._tk.Text(
            composer,
            height=5,
            wrap="word",
            bg=self._palette.panel,
            fg=self._palette.text,
            insertbackground=self._palette.secondary,
            selectbackground=self._palette.primary,
            relief="flat",
            padx=10,
            pady=10,
            font=("Segoe UI", 11),
            undo=True,
        )
        self._input.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self._input.bind("<Return>", self._on_return)
        self._input.bind("<Shift-Return>", self._on_shift_return)
        self._input.bind("<<Modified>>", self._on_modified)
        self._input.edit_modified(False)

        self._send = self._ttk.Button(
            composer,
            text="Send",
            style="Sofia.TButton",
            command=self._send_current,
        )
        self._send.pack(
            side="right",
            padx=(10, 0),
            fill="y",
        )

    def _start_background(self) -> None:
        self._busy = True
        Thread(
            target=self._background_start,
            name="sofia-ui-start",
            daemon=True,
        ).start()

    def _background_start(self) -> None:
        try:
            history = self._controller.start(
                session_id=self._session_id
            )
            draft = self._controller.draft_text()
            self._events.put(
                ("started", (history, draft))
            )
        except Exception as exc:
            self._events.put(("startup_error", exc))

    def _on_shift_return(self, _event):
        self._input.insert("insert", "\n")
        return "break"

    def _on_return(self, _event):
        if not self._busy:
            self._send_current()
        return "break"

    def _on_modified(self, _event) -> None:
        if not self._input.edit_modified():
            return
        self._input.edit_modified(False)
        if not self._controller.started or self._busy:
            return
        try:
            self._controller.save_draft(
                self._input.get("1.0", "end-1c")
            )
        except Exception as exc:
            self._status.set(
                f"Draft save failed: {type(exc).__name__}"
            )

    def _send_current(self) -> None:
        if self._busy or not self._controller.started:
            return
        content = self._input.get("1.0", "end-1c")
        if not content.strip():
            return

        self._busy = True
        self._set_enabled(False)
        self._status.set("Sofía is responding...")
        Thread(
            target=self._background_send,
            args=(content,),
            name="sofia-ui-send",
            daemon=True,
        ).start()

    def _background_send(self, content: str) -> None:
        try:
            self._controller.send(content)
            history = self._controller.history()
            self._events.put(("sent", history))
        except Exception as exc:
            self._events.put(("send_error", exc))

    def _poll_events(self) -> None:
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except Empty:
                break

            if kind == "started":
                history, draft = payload
                self._busy = False
                self._render_history(history)
                self._replace_input(draft)
                self._set_enabled(True)
                self._status.set("Ready")
                self._refresh_theme()
                self._input.focus_set()
                if self._close_requested:
                    self._finish_close()
                    return
            elif kind == "sent":
                self._busy = False
                self._render_history(payload)
                self._replace_input("")
                self._set_enabled(True)
                self._status.set("Ready")
                self._refresh_theme()
                self._input.focus_set()
                if self._close_requested:
                    self._finish_close()
                    return
            elif kind == "startup_error":
                self._busy = False
                self._status.set(
                    f"Startup failed: {type(payload).__name__}"
                )
                self._show_error(
                    "Sofía could not start",
                    str(payload),
                )
                self._finish_close()
                return
            elif kind == "send_error":
                self._busy = False
                self._set_enabled(True)
                self._status.set(
                    f"Response failed: {type(payload).__name__}"
                )
                self._show_error(
                    "Response failed",
                    str(payload),
                )
                self._input.focus_set()
                if self._close_requested:
                    self._finish_close()
                    return

        self._root.after(80, self._poll_events)

    def _configure_ttk_palette(
        self,
        palette: ThemePalette,
    ) -> None:
        self._style.configure(
            "Sofia.TFrame",
            background=palette.background,
        )
        self._style.configure(
            "SofiaPanel.TFrame",
            background=palette.panel,
        )
        self._style.configure(
            "Sofia.TLabel",
            background=palette.background,
            foreground=palette.text,
        )
        self._style.configure(
            "SofiaStatus.TLabel",
            background=palette.background,
            foreground=palette.muted,
        )
        self._style.configure(
            "Sofia.TButton",
            background=palette.primary,
            foreground=palette.text,
            padding=(14, 8),
        )
        self._style.configure(
            "Sofia.TCheckbutton",
            background=palette.background,
            foreground=palette.text,
        )

    def _apply_theme(
        self,
        palette: ThemePalette,
    ) -> None:
        self._palette = palette
        self._root.configure(
            bg=palette.background
        )
        self._configure_ttk_palette(
            palette
        )
        self._history.configure(
            bg=palette.panel,
            fg=palette.text,
            insertbackground=palette.secondary,
            selectbackground=palette.primary,
        )
        self._history.tag_configure(
            "user",
            foreground=palette.secondary,
        )
        self._history.tag_configure(
            "sofia",
            foreground=palette.tertiary,
        )
        self._history.tag_configure(
            "body",
            foreground=palette.text,
        )
        self._input.configure(
            bg=palette.panel,
            fg=palette.text,
            insertbackground=palette.secondary,
            selectbackground=palette.primary,
        )
        label = (
            " · ".join(palette.drivers[:3])
            if palette.drivers
            else palette.name
        )
        self._theme_name.set(
            f"Theme: {label}"
        )

    def _refresh_theme(self) -> None:
        palette = canonical_theme()
        if (
            self._adaptive_theme.get()
            and self._controller.started
        ):
            try:
                palette = (
                    self._controller.theme_palette()
                )
            except Exception:
                # Theme projection is optional presentation. A theme-source
                # failure must never take down conversation.
                palette = canonical_theme()
        self._apply_theme(palette)

    def _refresh_theme_timer(self) -> None:
        self._refresh_theme()
        self._root.after(
            60_000,
            self._refresh_theme_timer,
        )

    def _render_history(self, messages) -> None:
        ids = tuple(message.message_id for message in messages)
        if ids == self._last_rendered_ids:
            return

        self._history.configure(state="normal")
        self._history.delete("1.0", "end")
        for message in messages:
            label = "YOU" if message.actor == "user" else "SOFÍA"
            tag = "user" if message.actor == "user" else "sofia"
            self._history.insert("end", f"{label}\n", tag)
            self._history.insert(
                "end",
                f"{message.content}\n",
                "body",
            )
        self._history.configure(state="disabled")
        self._history.see("end")
        self._last_rendered_ids = ids

    def _replace_input(self, content: str) -> None:
        self._input.edit_modified(False)
        self._input.delete("1.0", "end")
        if content:
            self._input.insert("1.0", content)
        self._input.edit_modified(False)

    def _set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._input.configure(state=state)
        self._send.configure(state=state)

    def _request_close(self) -> None:
        if self._busy:
            self._close_requested = True
            self._status.set(
                "Finishing current operation before shutdown..."
            )
            return
        self._finish_close()

    def _finish_close(self) -> None:
        draft = ""
        try:
            if self._controller.started:
                if str(self._input.cget("state")) != "disabled":
                    draft = self._input.get("1.0", "end-1c")
                self._controller.shutdown(
                    current_draft=draft,
                )
        finally:
            self._root.destroy()

    def _show_error(self, title: str, message: str) -> None:
        try:
            from tkinter import messagebox
            messagebox.showerror(
                title,
                message or title,
                parent=self._root,
            )
        except Exception:
            pass


def run_desktop(
    configuration: SofiaConfiguration | None = None,
    *,
    session_id: str | None = None,
) -> int:
    """Run the local desktop workbench until its window closes."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as exc:
        raise RuntimeError(
            "Tkinter is required for the local desktop workbench."
        ) from exc

    config = configuration or create_default_configuration()
    application = SofiaApplication(config)
    controller = DesktopWorkbenchController(application)
    root = tk.Tk()
    _TkDesktopWorkbench(
        tk=tk,
        ttk=ttk,
        root=root,
        controller=controller,
        session_id=session_id,
    )
    root.mainloop()
    return 0


def main() -> int:
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
