"""Plain-text CLI/TUI projection for the shared Aegis chat experience."""
from __future__ import annotations

import json
from pathlib import Path
import textwrap

from sofia.platform.chat_clients.controller import (
    ChannelView,
    ClientSnapshot,
    NotificationMode,
    NoticeSeverity,
    PendingSendStatus,
)
from sofia.platform.chat_clients.contracts import ConnectionState, RoomKind

_THEME_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "ui" / "aegis-theme-v1.json"
)

_ANSI = {
    "primary": "38;2;148;0;211",
    "accent": "38;2;0;194;255",
    "success": "38;2;57;255;20",
    "warning": "38;2;255;176;0",
    "error": "38;2;159;2;2",
    "muted": "38;2;148;163;184",
    "text_main": "38;2;229;231;235",
}


def shared_theme_tokens() -> dict[str, str]:
    try:
        document = json.loads(_THEME_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tokens = document.get("tokens")
    return dict(tokens) if isinstance(tokens, dict) else {}


def _paint(text: str, role: str, *, color: bool, no_color: bool) -> str:
    if not color or no_color:
        return text
    code = _ANSI.get(role)
    return f"\x1b[{code}m{text}\x1b[0m" if code is not None else text


def connection_label(state: ConnectionState) -> str:
    return {
        ConnectionState.CONNECTED: "CONNECTED",
        ConnectionState.OFFLINE: "OFFLINE",
        ConnectionState.CONNECTING: "CONNECTING",
        ConnectionState.DEGRADED: "DEGRADED",
        ConnectionState.REVOKED: "REVOKED",
    }[state]


def _room_marker(kind: RoomKind) -> str:
    return {
        RoomKind.GENERAL: "#",
        RoomKind.DIRECT: "@",
        RoomKind.PRIVATE_GROUP: "+",
    }[kind]


def _notification_label(mode: NotificationMode) -> str:
    return {
        NotificationMode.ALL: "all",
        NotificationMode.MENTIONS: "mentions",
        NotificationMode.MUTED: "muted",
    }[mode]


def _notice_label(severity: NoticeSeverity) -> str:
    return {
        NoticeSeverity.INFO: "INFO",
        NoticeSeverity.WARNING: "WARNING",
        NoticeSeverity.ERROR: "ERROR",
        NoticeSeverity.DENIED: "DENIED",
        NoticeSeverity.OFFLINE: "OFFLINE",
    }[severity]


def _wrap(prefix: str, body: str, width: int) -> list[str]:
    available = max(20, width - len(prefix))
    lines = textwrap.wrap(
        body, width=available, replace_whitespace=False,
        drop_whitespace=False, break_long_words=True,
    ) or [""]
    return [prefix + lines[0]] + [" " * len(prefix) + line for line in lines[1:]]


def render_sidebar(
    snapshot: ClientSnapshot, *, width: int = 80, color: bool = False,
    no_color: bool = False,
) -> list[str]:
    core = snapshot.selected_core
    header = (
        f"CORE: {core.display_name} [{core.core_id[:8]}] "
        f"generation={core.generation}"
        if core is not None else "CORE: <none selected>"
    )
    status = f"CONNECTION: {connection_label(snapshot.connection)}"
    if snapshot.connection is not ConnectionState.CONNECTED:
        status += " (cached view)"
    lines = [
        _paint("AEGIS CHAT", "primary", color=color, no_color=no_color),
        header[:width],
        _paint(status, "warning" if snapshot.connection is not ConnectionState.CONNECTED
               else "success", color=color, no_color=no_color),
        "",
        "CHANNELS",
    ]
    for index, channel in enumerate(snapshot.channels, start=1):
        selected = ">" if channel.active else " "
        badges = []
        if channel.unread:
            badges.append(f"unread={channel.unread}")
        if channel.mentions:
            badges.append(f"mentions={channel.mentions}")
        if channel.notification is not NotificationMode.ALL:
            badges.append(_notification_label(channel.notification))
        if channel.membership_status is not None and (
            channel.membership_status.value != "active"
        ):
            badges.append(channel.membership_status.value)
        suffix = f" [{' '.join(badges)}]" if badges else ""
        lines.append(
            (f"{selected} {index}. {_room_marker(channel.kind)} "
             f"{channel.title}{suffix}")[:width]
        )
    if not snapshot.channels:
        lines.append("  (no visible channels)")
    return lines


def render_messages(
    snapshot: ClientSnapshot, *, width: int = 80, color: bool = False,
    no_color: bool = False,
) -> list[str]:
    if snapshot.active_room_id is None:
        return ["Open a channel to view history."]
    if snapshot.has_older:
        lines = ["[older history available: press PgUp]"]
    else:
        lines = ["[start of available history]"]
    for message in snapshot.messages:
        speaker = {
            "owner": "OWNER",
            "core": "CORE",
            "system": "SYSTEM",
        }[message.speaker_kind.value]
        role = (
            "accent" if message.speaker_kind.value == "owner"
            else "primary" if message.speaker_kind.value == "core"
            else "muted"
        )
        prefix = _paint(
            f"[{speaker}] {message.speaker_label}: ", role,
            color=color, no_color=no_color,
        )
        if message.reply_to:
            prefix += f"(reply to {message.reply_to[:8]}) "
        lines.extend(_wrap(prefix, message.body, width))
    for pending in snapshot.pending:
        label = {
            PendingSendStatus.PENDING: "[PENDING]",
            PendingSendStatus.UNCERTAIN: "[UNCERTAIN]",
            PendingSendStatus.DENIED: "[DENIED]",
        }[pending.status]
        lines.extend(_wrap(
            _paint(f"{label} you: ", "warning", color=color, no_color=no_color),
            pending.body, width,
        ))
    return lines


def render_notices(snapshot: ClientSnapshot, *, width: int = 80) -> list[str]:
    return [
        f"[{_notice_label(notice.severity)}] {notice.message}"[:width]
        for notice in snapshot.notices
    ]


def render_chat_screen(
    snapshot: ClientSnapshot, *, width: int = 80, color: bool = False,
    no_color: bool = False,
) -> str:
    sidebar = render_sidebar(
        snapshot, width=width, color=color, no_color=no_color
    )
    body = render_messages(
        snapshot, width=width, color=color, no_color=no_color
    )
    notices = render_notices(snapshot, width=width)
    sections = ["\n".join(sidebar), "\n".join(body)]
    if notices:
        sections.append("\n".join(notices))
    if snapshot.draft is not None:
        sections.append(f"DRAFT: {snapshot.draft.content}")
    return "\n\n".join(sections)


def render_channel_list(channels: tuple[ChannelView, ...]) -> str:
    return "\n".join(
        f"{index}. {channel.kind.value}: {channel.title} "
        f"(unread={channel.unread}, mentions={channel.mentions})"
        for index, channel in enumerate(channels, start=1)
    )
