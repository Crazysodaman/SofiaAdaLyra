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
from sofia.ui.drafts import UIDraft, UIDraftStore
from sofia.ui.text import UITextClient, UITextMessage
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
    "ConflictError",
    "Entry",
    "EntryKind",
    "EntryStatus",
    "ExpressionDelivery",
    "Item",
    "ItemKind",
    "PresentationChannel",
    "PresentationStatus",
    "UIDraft",
    "UIDraftStore",
    "UITextClient",
    "UITextMessage",
    "Workbench",
    "WorkbenchError",
]
