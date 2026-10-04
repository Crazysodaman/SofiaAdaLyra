"""PKG-UI text-first desktop, tray and draft primitives.

UI presents and transports already-authorized Sofía interaction. It does not
own identity, cognition, memory, authentication, interaction semantics, or
external-action authority.
"""

from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.drafts import UIDraft, UIDraftStore
from sofia.ui.quick_tools import (
    QUICK_TOOLS,
    QuickTool,
    quick_tool_by_label,
    quick_tool_labels,
)
from sofia.ui.text import UITextClient, UITextMessage
from sofia.ui.terminal import ConversationLoop
from sofia.ui.theme import (
    AdaptiveThemePolicy,
    ThemePalette,
    ThemeSignals,
    canonical_theme,
    theme_signals_from_sources,
)
from sofia.ui.control_center import (
    DesktopControlSettings,
    DesktopControlSettingsStore,
    GameMode,
    MASTER_SETTINGS_SECTIONS,
    RemoteChatMode,
    ServiceAction,
    ServiceKind,
    ServiceTarget,
    TrayCommand,
    TrayStatus,
    tray_command_enabled,
    tray_command_requires_confirmation,
    tray_menu_labels,
)
__all__ = [
    'AdaptiveThemePolicy',
    'ConversationLoop',
    'DesktopWorkbenchController',
    'QUICK_TOOLS',
    'QuickTool',
    'ThemePalette',
    'ThemeSignals',
    'UIDraft',
    'UIDraftStore',
    'UITextClient',
    'UITextMessage',
    'canonical_theme',
    'quick_tool_by_label',
    'quick_tool_labels',
    'theme_signals_from_sources',
    'DesktopControlSettings',
    'DesktopControlSettingsStore',
    'GameMode',
    'MASTER_SETTINGS_SECTIONS',
    'RemoteChatMode',
    'ServiceAction',
    'ServiceKind',
    'ServiceTarget',
    'TrayCommand',
    'TrayStatus',
    'tray_command_enabled',
    'tray_command_requires_confirmation',
    'tray_menu_labels',
]
