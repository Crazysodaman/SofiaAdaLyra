"""Keyboard-only and reduced-cognitive-load layout for chat clients."""
from __future__ import annotations

from dataclasses import dataclass

from sofia.platform.chat_clients.controller import ClientSnapshot


@dataclass(frozen=True, slots=True)
class KeyboardCommand:
    key: str
    description: str
    enabled: bool = True


def keyboard_commands(snapshot: ClientSnapshot) -> tuple[KeyboardCommand, ...]:
    can_send = snapshot.active_room_id is not None and snapshot.connection.value == (
        "connected"
    )
    commands = [
        KeyboardCommand("Ctrl+K", "select Core by exact enrolled identity"),
        KeyboardCommand("1..9", "open a numbered channel"),
        KeyboardCommand("Tab", "move focus to the next control"),
        KeyboardCommand("Shift+Tab", "move focus to the previous control"),
        KeyboardCommand("Enter", "send the composed message"),
        KeyboardCommand("Shift+Enter", "insert a newline in the composer"),
        KeyboardCommand("Ctrl+R", "reply to the focused message"),
        KeyboardCommand("Ctrl+S", "save draft"),
        KeyboardCommand("PgUp", "load older history", snapshot.has_older),
        KeyboardCommand("M", "cycle notification mode for the active channel"),
        KeyboardCommand("G", "create a private group"),
        KeyboardCommand("I", "invite a Core to the active private group"),
        KeyboardCommand("L", "leave the active private group"),
        KeyboardCommand("F5", "reconnect and resync"),
        KeyboardCommand("Escape", "close dialog or clear focus"),
        KeyboardCommand("?", "show keyboard help"),
        KeyboardCommand("Q", "quit without sending"),
    ]
    if not can_send:
        commands = [
            item if item.key != "Enter" else KeyboardCommand(
                item.key, item.description, False
            )
            for item in commands
        ]
    return tuple(commands)


def focus_order(snapshot: ClientSnapshot) -> tuple[str, ...]:
    channels = tuple(f"channel:{item.room_id}" for item in snapshot.channels)
    return (
        "core_selector",
        *channels,
        "messages",
        "composer",
        "send_button",
        "notification_control",
        "membership_control",
    )


def accessibility_summary(snapshot: ClientSnapshot) -> dict[str, object]:
    return {
        "core_label": (
            f"{snapshot.selected_core.display_name} "
            f"generation {snapshot.selected_core.generation}"
            if snapshot.selected_core is not None else "no Core selected"
        ),
        "connection": snapshot.connection.value.upper(),
        "channel_count": len(snapshot.channels),
        "active_channel": snapshot.active_room_id,
        "unread_total": sum(item.unread for item in snapshot.channels),
        "mention_total": sum(item.mentions for item in snapshot.channels),
        "pending_total": len(snapshot.pending),
        "has_draft": snapshot.draft is not None,
        "focus_order": focus_order(snapshot),
        "commands": tuple(
            (item.key, item.description, item.enabled)
            for item in keyboard_commands(snapshot)
        ),
        "uses_color_for_status": False,
    }
