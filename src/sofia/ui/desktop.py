"""Low-resource Windows desktop shell for Sofía.

Tkinter is imported lazily so headless tests and non-desktop package consumers
do not require a display server. The shell uses one canonical SofiaApplication
and its text_ui adapter. No renderer, voice, browser, or raw OS-control surface
is introduced here.
"""
from __future__ import annotations

from queue import Empty, Queue
import traceback
from typing import Any

from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.ui.desktop_worker import DesktopApplicationWorker
from sofia.ui.quick_tools import (
    quick_tool_by_label,
    quick_tool_labels,
)
from sofia.ui.theme import ThemePalette, canonical_theme


def _format_exception_chain(
    error: BaseException,
) -> str:
    """Return concise nested failure detail without discarding root cause."""
    if not isinstance(error, BaseException):
        raise TypeError("error must be an exception")

    lines: list[str] = []
    current: BaseException | None = error
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        line = type(current).__name__
        if message:
            line += f": {message}"
        lines.append(line)
        current = (
            current.__cause__
            if current.__cause__ is not None
            else current.__context__
        )

    return "\nCaused by: ".join(lines)


def _chamfer_points(
    width: int,
    height: int,
    cut: int = 10,
) -> tuple[int, ...]:
    """Return a shallow 45-degree chamfer polygon for a rectangle."""
    if type(width) is not int or type(height) is not int or type(cut) is not int:
        raise TypeError("chamfer dimensions must be integers")
    if width <= 0 or height <= 0:
        raise ValueError("chamfer width and height must be positive")
    if cut <= 0:
        raise ValueError("chamfer cut must be positive")

    actual = min(
        cut,
        max(1, (width - 1) // 2),
        max(1, (height - 1) // 2),
    )
    return (
        actual, 0,
        width - actual, 0,
        width, actual,
        width, height - actual,
        width - actual, height,
        actual, height,
        0, height - actual,
        0, actual,
    )


class _ChamferButton:
    """Small Canvas button with shallow 45-degree corners."""

    def __init__(
        self,
        *,
        tk: Any,
        parent: Any,
        text: str,
        command,
        palette: ThemePalette,
        width: int = 112,
        cut: int = 10,
    ) -> None:
        self._tk = tk
        self._command = command
        self._text = text
        self._palette = palette
        self._cut = cut
        self._state = "normal"
        self._canvas = tk.Canvas(
            parent,
            width=width,
            height=72,
            highlightthickness=0,
            bd=0,
            relief="flat",
            bg=palette.background,
            cursor="hand2",
        )
        self._canvas.bind("<Configure>", self._redraw)
        self._canvas.bind("<Button-1>", self._invoke)
        self._canvas.bind("<Return>", self._invoke)
        self._canvas.bind("<space>", self._invoke)

    def pack(self, **kwargs) -> None:
        self._canvas.pack(**kwargs)

    def focus_set(self) -> None:
        self._canvas.focus_set()

    def configure(self, **kwargs) -> None:
        state = kwargs.pop("state", None)
        if kwargs:
            raise TypeError(
                f"unsupported ChamferButton options: {tuple(kwargs)}"
            )
        if state is not None:
            if state not in {"normal", "disabled"}:
                raise ValueError("state must be normal or disabled")
            self._state = state
            self._canvas.configure(
                cursor="hand2" if state == "normal" else "",
            )
            self._redraw()

    config = configure

    def apply_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        self._canvas.configure(
            bg=palette.background
        )
        self._redraw()

    def _invoke(self, _event=None):
        if self._state == "normal":
            self._command()
        return "break"

    def _redraw(self, _event=None) -> None:
        width = max(2, int(self._canvas.winfo_width()))
        height = max(2, int(self._canvas.winfo_height()))
        self._canvas.delete("all")
        points = _chamfer_points(
            width - 1,
            height - 1,
            self._cut,
        )
        if self._state == "normal":
            fill = self._palette.primary
            outline = self._palette.secondary
            text_color = self._palette.text
        else:
            fill = self._palette.panel
            outline = self._palette.muted
            text_color = self._palette.muted
        self._canvas.create_polygon(
            points,
            fill=fill,
            outline=outline,
            width=1,
        )
        self._canvas.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=text_color,
            font=("Segoe UI Semibold", 10),
        )


class _TkDesktopWorkbench:
    def __init__(
        self,
        *,
        tk: Any,
        ttk: Any,
        root: Any,
        configuration: SofiaConfiguration,
        session_id: str | None,
    ) -> None:
        self._tk = tk
        self._ttk = ttk
        self._root = root
        self._session_id = session_id
        self._events: Queue[tuple[str, object]] = Queue()
        self._worker = DesktopApplicationWorker(
            configuration=configuration,
            session_id=session_id,
            events=self._events,
        )
        self._application_ready = False
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
        self._root.title("Sofía")
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
            text="SOFÍA",
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

        self._quick_tool_selection = self._tk.StringVar(
            master=self._root,
            value="Quick Tools",
        )
        self._quick_tools = self._ttk.Combobox(
            header,
            textvariable=self._quick_tool_selection,
            values=quick_tool_labels(),
            state="disabled",
            width=20,
            style="Sofia.TCombobox",
        )
        self._quick_tools.pack(
            side="left",
            padx=(16, 0),
        )
        self._quick_tools.bind(
            "<<ComboboxSelected>>",
            self._on_quick_tool_selected,
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

        self._history_shell = self._tk.Canvas(
            outer,
            highlightthickness=0,
            bd=0,
            relief="flat",
            bg=self._palette.background,
        )
        self._history_shell.pack(
            fill="both",
            expand=True,
        )
        self._history = self._tk.Text(
            self._history_shell,
            wrap="word",
            state="disabled",
            bg=self._palette.panel,
            fg=self._palette.text,
            insertbackground=self._palette.secondary,
            selectbackground=self._palette.primary,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            font=("Segoe UI", 11),
        )
        self._history_window = self._history_shell.create_window(
            10,
            10,
            anchor="nw",
            window=self._history,
        )
        self._history_shell.bind(
            "<Configure>",
            self._layout_history_shell,
        )
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

        self._input_shell = self._tk.Canvas(
            composer,
            height=104,
            highlightthickness=0,
            bd=0,
            relief="flat",
            bg=self._palette.background,
        )
        self._input_shell.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self._input = self._tk.Text(
            self._input_shell,
            height=5,
            wrap="word",
            bg=self._palette.panel,
            fg=self._palette.text,
            insertbackground=self._palette.secondary,
            selectbackground=self._palette.primary,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=8,
            font=("Segoe UI", 11),
            undo=True,
        )
        self._input_window = self._input_shell.create_window(
            10,
            10,
            anchor="nw",
            window=self._input,
        )
        self._input_shell.bind(
            "<Configure>",
            self._layout_input_shell,
        )
        self._input.bind("<Return>", self._on_return)
        self._input.bind("<Shift-Return>", self._on_shift_return)
        self._input.bind("<<Modified>>", self._on_modified)
        self._input.edit_modified(False)

        self._send = _ChamferButton(
            tk=self._tk,
            parent=composer,
            text="Send",
            command=self._send_current,
            palette=self._palette,
            width=112,
            cut=10,
        )
        self._send.pack(
            side="right",
            padx=(10, 0),
            fill="y",
        )

    def _layout_history_shell(self, _event=None) -> None:
        self._layout_chamfer_shell(
            self._history_shell,
            self._history_window,
            accent=self._palette.secondary,
        )

    def _layout_input_shell(self, _event=None) -> None:
        self._layout_chamfer_shell(
            self._input_shell,
            self._input_window,
            accent=self._palette.primary,
        )

    def _layout_chamfer_shell(
        self,
        canvas,
        window_id,
        *,
        accent: str,
    ) -> None:
        width = max(24, int(canvas.winfo_width()))
        height = max(24, int(canvas.winfo_height()))
        cut = 10
        canvas.delete("chamfer")
        canvas.create_polygon(
            _chamfer_points(
                width - 1,
                height - 1,
                cut,
            ),
            fill=self._palette.panel,
            outline=accent,
            width=1,
            tags=("chamfer",),
        )
        canvas.tag_lower("chamfer")
        inset = cut
        canvas.coords(
            window_id,
            inset,
            inset,
        )
        canvas.itemconfigure(
            window_id,
            width=max(1, width - (inset * 2)),
            height=max(1, height - (inset * 2)),
        )

    def _on_quick_tool_selected(self, _event=None) -> None:
        if self._busy or not self._application_ready:
            return
        label = self._quick_tool_selection.get()
        try:
            tool = quick_tool_by_label(label)
        except (KeyError, ValueError):
            return

        current = self._input.get("1.0", "end-1c")
        if current.strip():
            self._status.set(
                "Composer already has text; quick tool was not loaded."
            )
            self._quick_tool_selection.set(
                "Quick Tools"
            )
            return

        self._replace_input(tool.prompt)
        self._worker.save_draft(tool.prompt)
        self._quick_tool_selection.set(
            "Quick Tools"
        )
        self._status.set(
            f"Loaded {tool.label}. Press Send to run."
        )
        self._input.focus_set()

    def _start_background(self) -> None:
        self._busy = True
        self._worker.start()

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
        if not self._application_ready or self._busy:
            return
        try:
            self._worker.save_draft(
                self._input.get("1.0", "end-1c")
            )
        except Exception as exc:
            self._status.set(
                f"Draft queue failed: {type(exc).__name__}"
            )

    def _send_current(self) -> None:
        if self._busy or not self._application_ready:
            return
        content = self._input.get("1.0", "end-1c")
        if not content.strip():
            return

        self._busy = True
        self._set_enabled(False)
        self._status.set("Sofía is responding...")
        self._worker.send(content)

    def _poll_events(self) -> None:
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except Empty:
                break

            if kind == "started":
                history, draft, palette = payload
                self._application_ready = True
                self._busy = False
                self._render_history(history)
                self._replace_input(draft)
                self._set_enabled(True)
                self._status.set("Ready")
                if self._adaptive_theme.get():
                    self._apply_theme(palette)
                else:
                    self._apply_theme(canonical_theme())
                self._input.focus_set()
                if self._close_requested:
                    self._begin_shutdown()
                    return
            elif kind == "sent":
                history, palette = payload
                self._busy = False
                self._render_history(history)
                self._replace_input("")
                self._set_enabled(True)
                self._status.set("Ready")
                if self._adaptive_theme.get():
                    self._apply_theme(palette)
                else:
                    self._apply_theme(canonical_theme())
                self._input.focus_set()
                if self._close_requested:
                    self._begin_shutdown()
                    return
            elif kind == "startup_error":
                self._busy = False
                self._status.set(
                    f"Startup failed: {type(payload).__name__}"
                )
                detail = _format_exception_chain(payload)
                traceback.print_exception(
                    type(payload),
                    payload,
                    payload.__traceback__,
                )
                self._show_error(
                    "Sofía could not start",
                    detail,
                )
                self._root.destroy()
                return
            elif kind == "send_error":
                self._busy = False
                self._set_enabled(True)
                self._status.set(
                    f"Response failed: {type(payload).__name__}"
                )
                detail = _format_exception_chain(payload)
                traceback.print_exception(
                    type(payload),
                    payload,
                    payload.__traceback__,
                )
                self._show_error(
                    "Response failed",
                    detail,
                )
                self._input.focus_set()
                if self._close_requested:
                    self._begin_shutdown()
                    return
            elif kind == "theme":
                if self._adaptive_theme.get():
                    self._apply_theme(payload)
            elif kind == "draft_error":
                self._status.set(
                    f"Draft save failed: {type(payload).__name__}"
                )
            elif kind == "shutdown_complete":
                self._application_ready = False
                self._root.destroy()
                return
            elif kind == "shutdown_error":
                detail = _format_exception_chain(payload)
                traceback.print_exception(
                    type(payload),
                    payload,
                    payload.__traceback__,
                )
                self._show_error(
                    "Sofía could not shut down cleanly",
                    detail,
                )
                self._application_ready = False
                self._root.destroy()
                return
            elif kind == "worker_error":
                self._show_error(
                    "Desktop worker error",
                    _format_exception_chain(payload),
                )

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
        header_font = ("Segoe UI Semibold", 10)
        self._style.configure(
            "Sofia.TLabel",
            background=palette.background,
            foreground=palette.text,
            font=header_font,
        )
        self._style.configure(
            "SofiaStatus.TLabel",
            background=palette.background,
            foreground=palette.muted,
            font=header_font,
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
        self._style.configure(
            "Sofia.TCombobox",
            fieldbackground=palette.panel,
            background=palette.panel,
            foreground=palette.text,
            arrowcolor=palette.secondary,
            selectbackground=palette.primary,
            selectforeground=palette.text,
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
        self._history_shell.configure(
            bg=palette.background
        )
        self._input_shell.configure(
            bg=palette.background
        )
        self._send.apply_palette(
            palette
        )
        self._layout_history_shell()
        self._layout_input_shell()
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
            and self._application_ready
        ):
            try:
                self._worker.refresh_theme()
                return
            except Exception:
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
        """Replace composer text even when the widget is temporarily disabled."""
        if not isinstance(content, str):
            raise TypeError("content must be a string")

        previous_state = str(self._input.cget("state"))
        if previous_state == "disabled":
            self._input.configure(state="normal")

        try:
            self._input.edit_modified(False)
            self._input.delete("1.0", "end")
            if content:
                self._input.insert("1.0", content)
            self._input.edit_modified(False)
        finally:
            if previous_state == "disabled":
                self._input.configure(state="disabled")

    def _set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._input.configure(state=state)
        self._send.configure(state=state)
        self._quick_tools.configure(
            state="readonly" if enabled else "disabled"
        )

    def _request_close(self) -> None:
        self._close_requested = True
        if self._busy:
            self._status.set(
                "Finishing current operation before shutdown..."
            )
            return
        self._begin_shutdown()

    def _begin_shutdown(self) -> None:
        if not self._application_ready:
            self._root.destroy()
            return
        draft = ""
        if str(self._input.cget("state")) != "disabled":
            draft = self._input.get("1.0", "end-1c")
        self._busy = True
        self._set_enabled(False)
        self._status.set("Shutting down Sofía...")
        self._worker.shutdown(draft)

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
    root = tk.Tk()
    _TkDesktopWorkbench(
        tk=tk,
        ttk=ttk,
        root=root,
        configuration=config,
        session_id=session_id,
    )
    root.mainloop()
    return 0


def main() -> int:
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
