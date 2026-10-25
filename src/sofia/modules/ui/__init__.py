"""PKG-UI exports loaded lazily for Core-free Platform clients."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "DesktopWorkbenchController": ("desktop_controller", "DesktopWorkbenchController"),
    "UIDraft": ("drafts", "UIDraft"),
    "UIDraftStore": ("drafts", "UIDraftStore"),
    "QUICK_TOOLS": ("quick_tools", "QUICK_TOOLS"),
    "QuickTool": ("quick_tools", "QuickTool"),
    "quick_tool_by_label": ("quick_tools", "quick_tool_by_label"),
    "quick_tool_labels": ("quick_tools", "quick_tool_labels"),
    "UITextClient": ("text", "UITextClient"),
    "UITextMessage": ("text", "UITextMessage"),
    "ConversationLoop": ("terminal", "ConversationLoop"),
    "AdaptiveThemePolicy": ("theme", "AdaptiveThemePolicy"),
    "ThemePalette": ("theme", "ThemePalette"),
    "ThemeSignals": ("theme", "ThemeSignals"),
    "canonical_theme": ("theme", "canonical_theme"),
    "theme_signals_from_sources": ("theme", "theme_signals_from_sources"),
    "DesktopControlSettings": ("control_center", "DesktopControlSettings"),
    "DesktopControlSettingsStore": ("control_center", "DesktopControlSettingsStore"),
    "GameMode": ("control_center", "GameMode"),
    "MASTER_SETTINGS_SECTIONS": ("control_center", "MASTER_SETTINGS_SECTIONS"),
    "RemoteChatMode": ("control_center", "RemoteChatMode"),
    "ServiceAction": ("control_center", "ServiceAction"),
    "ServiceKind": ("control_center", "ServiceKind"),
    "ServiceTarget": ("control_center", "ServiceTarget"),
    "TrayCommand": ("control_center", "TrayCommand"),
    "TrayStatus": ("control_center", "TrayStatus"),
    "tray_command_enabled": ("control_center", "tray_command_enabled"),
    "tray_command_requires_confirmation": (
        "control_center", "tray_command_requires_confirmation",
    ),
    "tray_menu_labels": ("control_center", "tray_menu_labels"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
