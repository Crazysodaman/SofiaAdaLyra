"""Low-resource Windows desktop shell for Sofía.

Tkinter is imported lazily so headless tests and non-desktop package consumers
do not require a display server. The shell uses one canonical SofiaApplication
and its text_ui adapter. Its optional avatar and push-to-talk controls are
presentation surfaces over application-owned decisions, never state authority.
"""
from __future__ import annotations

import json
from queue import Empty, Queue
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.ui.control_center import DesktopControlSettingsStore
import traceback
from typing import Any

from sofia.config import SofiaConfiguration, create_production_configuration
from sofia.ui.desktop_worker import DesktopApplicationWorker
from sofia.ui.quick_tools import (
    quick_tool_by_label,
    quick_tool_labels,
)
from sofia.ui.theme import ThemePalette, canonical_theme
from sofia.ui.avatar_renderer import AvatarRenderRequest, TkAvatarRenderer
from sofia.voice import SpeechInputState


def settings_window_command(state_path: Path) -> tuple[str, ...]:
    """Return the exact isolated settings process command."""
    return (
        sys.executable,
        "-m",
        "sofia.ui.settings_window",
        "--state-path",
        str(Path(state_path)),
    )


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
        self._configuration = configuration
        self._session_id = session_id
        self._events: Queue[tuple[str, object]] = Queue()
        self._worker = DesktopApplicationWorker(
            configuration=configuration,
            session_id=session_id,
            events=self._events,
            expression_events=True,
        )
        self._application_ready = False
        self._busy = False
        self._listening = False
        self._persistence_status = ""
        self._matrix_status = ""
        self._close_requested = False
        self._last_rendered_ids: tuple[str, ...] = ()
        self._tool_specs = ()
        self._palette = canonical_theme()
        runtime_settings = RuntimeUserSettingsStore(configuration.state_path).load()
        self._avatar_renderer_enabled = runtime_settings.avatar_renderer_enabled
        self._voice_input_enabled = (
            runtime_settings.voice_input_enabled and not runtime_settings.voice_muted
        )
        self._adaptive_theme = self._tk.BooleanVar(
            master=self._root,
            value=runtime_settings.adaptive_theme,
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
        self._root.geometry("1040x820")
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
            command=self._save_theme,
            style="Sofia.TCheckbutton",
        )
        adaptive.pack(
            side="right",
            padx=(10, 0),
        )

        self._settings_button = self._ttk.Button(
            header,
            text="Settings",
            command=self._open_settings,
            style="Sofia.TButton",
        )
        self._settings_button.pack(side="right", padx=(10, 0))

        self._tools_button = self._ttk.Button(
            header,
            text="Tools",
            command=self._open_tools,
            style="Sofia.TButton",
        )
        self._tools_button.pack(side="right", padx=(10, 0))

        self._stop_gesture_button = self._ttk.Button(
            header,
            text="Stop gesture",
            command=self._stop_avatar_gesture,
            style="Sofia.TButton",
        )
        self._stop_gesture_button.pack(side="right", padx=(10, 0))

        self._voice_button = self._ttk.Button(
            header,
            text="Talk",
            command=self._toggle_voice_input,
            style="Sofia.TButton",
        )
        self._voice_button.pack(side="right", padx=(10, 0))

        self._status = self._tk.StringVar(value="")
        status = self._ttk.Label(
            header,
            textvariable=self._status,
            style="SofiaStatus.TLabel",
        )
        status.pack(side="right")

        self._avatar_canvas = self._tk.Canvas(
            outer,
            height=300,
            highlightthickness=1,
            highlightbackground=self._palette.primary,
            bd=0,
            relief="flat",
            bg=self._palette.panel,
        )
        if self._avatar_renderer_enabled:
            self._avatar_canvas.pack(fill="x", pady=(0, 10))
        self._avatar_renderer = TkAvatarRenderer(
            root=self._root, canvas=self._avatar_canvas,
        )

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

    def _open_settings(self) -> None:
        try:
            subprocess.Popen(
                settings_window_command(self._configuration.state_path),
                cwd=str(Path.cwd()),
                start_new_session=True,
            )
        except Exception as exc:
            self._show_error("Settings could not open", str(exc))

    def _open_tools(self) -> None:
        if self._busy or not self._application_ready or not self._tool_specs:
            return
        from tkinter import messagebox

        window = self._tk.Toplevel(self._root)
        window.title("Sofía · Owner-direct private tools")
        window.geometry("700x540")
        window.minsize(560, 420)
        window.configure(bg=self._palette.background)
        body = self._ttk.Frame(window, padding=14, style="Sofia.TFrame")
        body.pack(fill="both", expand=True)

        self._ttk.Label(
            body,
            text=(
                "You choose and run the tool. Sofía receives the settled result "
                "and responds through cognition; she does not select the command."
            ),
            wraplength=650,
            style="Sofia.TLabel",
        ).pack(fill="x", pady=(0, 10))

        by_name = {item.tool_name: item for item in self._tool_specs}
        selection = self._tk.StringVar(value=self._tool_specs[0].tool_name)
        chooser = self._ttk.Combobox(
            body,
            textvariable=selection,
            values=tuple(by_name),
            state="readonly",
            style="Sofia.TCombobox",
        )
        chooser.pack(fill="x")
        detail = self._tk.StringVar()
        self._ttk.Label(
            body,
            textvariable=detail,
            wraplength=650,
            style="SofiaStatus.TLabel",
        ).pack(fill="x", pady=(8, 8))

        self._ttk.Label(
            body,
            text="Parameters (JSON object)",
            style="Sofia.TLabel",
        ).pack(anchor="w")
        parameters = self._tk.Text(
            body,
            height=12,
            wrap="word",
            bg=self._palette.panel,
            fg=self._palette.text,
            insertbackground=self._palette.secondary,
            selectbackground=self._palette.primary,
            relief="flat",
            padx=8,
            pady=8,
            font=("Consolas", 10),
        )
        parameters.pack(fill="both", expand=True, pady=(4, 10))
        parameters.insert("1.0", "{}")

        def refresh_detail(_event=None) -> None:
            spec = by_name[selection.get()]
            required = spec.parameter_schema.get("required", ())
            required_text = ", ".join(required) if required else "none"
            detail.set(
                f"Capability: {spec.capability_name} · Level "
                f"{int(spec.permission_level)} · {spec.privacy.value} · "
                f"required: {required_text}\n{spec.description}"
            )

        def run_selected() -> None:
            spec = by_name[selection.get()]
            try:
                parsed = json.loads(parameters.get("1.0", "end-1c"))
                if not isinstance(parsed, dict):
                    raise ValueError("parameters must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                messagebox.showerror(
                    "Invalid tool parameters",
                    str(exc),
                    parent=window,
                )
                return
            if int(spec.permission_level) >= 3 and not messagebox.askyesno(
                "Run consequential private tool?",
                (
                    f"Run {spec.tool_name} as an owner-direct private action?\n\n"
                    "The normal capability policy and any required exact approval "
                    "still apply. This click cannot be forged by the LLM."
                ),
                parent=window,
            ):
                return
            window.destroy()
            self._busy = True
            self._set_enabled(False)
            self._status.set(f"Running private tool: {spec.tool_name}...")
            self._worker.run_tool(spec.tool_name, parsed)

        chooser.bind("<<ComboboxSelected>>", refresh_detail)
        controls = self._ttk.Frame(body, style="Sofia.TFrame")
        controls.pack(fill="x")
        self._ttk.Button(
            controls,
            text="Run privately",
            command=run_selected,
            style="Sofia.TButton",
        ).pack(side="right")
        self._ttk.Button(
            controls,
            text="Cancel",
            command=window.destroy,
            style="Sofia.TButton",
        ).pack(side="right", padx=(0, 8))
        refresh_detail()
        chooser.focus_set()

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

    def _ready_status(self) -> str:
        parts = ["Ready"]
        if self._persistence_status:
            parts.append(self._persistence_status)
        if self._matrix_status:
            parts.append(self._matrix_status)
        return " | ".join(parts)

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
                self._worker.load_tools()
                self._status.set(self._ready_status())
                if self._adaptive_theme.get():
                    self._apply_theme(palette)
                else:
                    self._apply_theme(canonical_theme())
                self._input.focus_set()
                if self._close_requested:
                    self._begin_shutdown()
                    return
            elif kind == "avatar_idle":
                if self._avatar_renderer_enabled:
                    self._avatar_renderer.render_idle(payload)
            elif kind == "persistence":
                self._persistence_status = str(payload)
                if self._application_ready and not self._busy:
                    self._status.set(self._ready_status())
            elif kind == "tools":
                self._tool_specs = tuple(payload)
                self._set_enabled(self._application_ready and not self._busy)
            elif kind == "sent":
                history, palette, matrix_status = payload
                self._matrix_status = str(matrix_status)
                self._busy = False
                self._render_history(history)
                self._replace_input("")
                self._set_enabled(True)
                self._status.set(self._ready_status())
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
            elif kind == "tool_complete":
                history, palette, matrix_status, result = payload
                self._matrix_status = str(matrix_status)
                self._busy = False
                self._render_history(history)
                self._set_enabled(True)
                self._status.set(
                    self._ready_status()
                    + f" · Tool {result.capability}: {result.kind.value}"
                )
                self._apply_theme(
                    palette if self._adaptive_theme.get() else canonical_theme()
                )
                self._input.focus_set()
            elif kind == "expression":
                self._render_expression(payload)
            elif kind == "tool_error":
                self._busy = False
                self._set_enabled(True)
                self._status.set(f"Tool failed: {type(payload).__name__}")
                self._show_error(
                    "Private tool failed",
                    _format_exception_chain(payload),
                )
            elif kind == "theme":
                if self._adaptive_theme.get():
                    self._apply_theme(payload)
            elif kind == "discord_started":
                self._status.set(
                    self._ready_status() + " · Discord connecting"
                )
            elif kind == "discord_disabled":
                self._status.set(
                    self._ready_status() + " · Discord disabled"
                )
            elif kind == "discord_error":
                self._status.set(
                    f"Discord failed: {type(payload).__name__}"
                )
                detail = _format_exception_chain(payload)
                traceback.print_exception(
                    type(payload),
                    payload,
                    payload.__traceback__,
                )
                self._show_error(
                    "Discord transport failed",
                    detail,
                )
            elif kind == "cloudflare_started":
                self._status.set(
                    self._ready_status() + " · Mobile tunnel online"
                )
            elif kind == "draft_error":
                self._status.set(
                    f"Draft save failed: {type(payload).__name__}"
                )
            elif kind == "shutdown_complete":
                settings = DesktopControlSettingsStore(self._configuration.state_path)
                if not settings.load().close_to_tray:
                    settings.request_tray_exit()
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
            elif kind == "avatar_error":
                self._status.set(
                    f"Avatar output failed: {type(payload).__name__}"
                )
            elif kind == "voice_input":
                receipt = payload
                if receipt.state is SpeechInputState.LISTENING:
                    self._listening = True
                    self._voice_button.configure(text="Cancel listening", state="normal")
                    self._status.set("Listening through the selected microphone...")
                elif receipt.state is SpeechInputState.COMPLETED:
                    self._listening = False
                    self._busy = False
                    self._voice_button.configure(text="Talk")
                    self._replace_input(receipt.transcript or "")
                    self._set_enabled(True)
                    self._send_current()
                else:
                    self._listening = False
                    self._busy = False
                    self._voice_button.configure(text="Talk")
                    self._set_enabled(True)
                    self._status.set(
                        f"Speech input {receipt.state.value}: "
                        f"{receipt.error or 'no transcript'}"
                    )
            elif kind == "voice_input_error":
                self._listening = False
                self._busy = False
                self._voice_button.configure(text="Talk")
                self._set_enabled(True)
                self._status.set(f"Speech input failed: {type(payload).__name__}")

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
        self._avatar_canvas.configure(
            bg=palette.panel,
            highlightbackground=palette.primary,
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

    def _render_expression(self, output) -> None:
        if output is None or not self._avatar_renderer_enabled:
            return
        decision, presentation = output
        if decision is None or presentation is None:
            return

        def completed(decision_id: str, rendered: bool, detail: str) -> None:
            self._worker.acknowledge_avatar(
                decision_id,
                rendered=rendered,
                backend=self._avatar_renderer.backend_name,
                detail=detail,
            )

        self._avatar_renderer.render(
            AvatarRenderRequest(decision, presentation),
            completed=completed,
        )

    def _stop_avatar_gesture(self) -> None:
        decision_id = self._avatar_renderer.stop()
        if decision_id is not None:
            self._worker.acknowledge_avatar(
                decision_id,
                rendered=False,
                backend=self._avatar_renderer.backend_name,
                detail="operator stopped gesture before completion",
            )

    def _toggle_voice_input(self) -> None:
        if self._listening:
            self._worker.cancel_listening()
            return
        if self._busy or not self._application_ready:
            return
        self._busy = True
        self._set_enabled(False)
        self._voice_button.configure(state="normal", text="Cancel listening")
        self._status.set("Opening microphone for one push-to-talk capture...")
        self._worker.listen_once()

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
        self._tools_button.configure(
            state=("normal" if enabled and self._tool_specs else "disabled")
        )
        self._voice_button.configure(
            state=(
                "normal"
                if self._listening or (enabled and self._voice_input_enabled)
                else "disabled"
            )
        )

    def _save_theme(self) -> None:
        try:
            store = RuntimeUserSettingsStore(self._configuration.state_path)
            store.save(replace(store.load(), adaptive_theme=bool(self._adaptive_theme.get())))
        except Exception as exc:
            self._show_error("Theme preference not saved", str(exc))
            return
        self._refresh_theme()

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

    config = configuration or create_production_configuration()
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


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Sofía desktop")
    parser.add_argument("--state-path", type=Path)
    args = parser.parse_args(argv)
    return run_desktop(create_production_configuration(state_path=args.state_path))


if __name__ == "__main__":
    raise SystemExit(main())
