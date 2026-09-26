"""PKG-UI text-first and workbench primitives.

UI presents and transports already-authorized Sofía interaction. It does not
own identity, cognition, memory, authentication, interaction semantics, or
external-action authority.
"""

from sofia.ui.delivery import (
    ExpressionDelivery,
    PresentationChannel,
    PresentationStatus,
)
from sofia.ui.desktop_controller import DesktopWorkbenchController
from sofia.ui.drafts import UIDraft, UIDraftStore
from sofia.ui.text import UITextClient, UITextMessage
from sofia.ui.theme import (
    AdaptiveThemePolicy,
    ThemePalette,
    ThemeSignals,
    canonical_theme,
    theme_signals_from_sources,
)
from sofia.ui.workbench import (
    AccessDenied,
    ConflictError,
    Entry,
    EntryKind,
    EntryStatus,
    Item,
    ItemKind,
    Workbench,
    WorkbenchError,
)

__all__ = [
    "AccessDenied",
    "AdaptiveThemePolicy",
    "ConflictError",
    "DesktopWorkbenchController",
    "Entry",
    "EntryKind",
    "EntryStatus",
    "ExpressionDelivery",
    "Item",
    "ItemKind",
    "PresentationChannel",
    "PresentationStatus",
    "ThemePalette",
    "ThemeSignals",
    "UIDraft",
    "UIDraftStore",
    "UITextClient",
    "UITextMessage",
    "Workbench",
    "WorkbenchError",
    "canonical_theme",
    "theme_signals_from_sources",
]
