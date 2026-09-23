"""Public application exports without an eager bootstrap/import cycle.

Importing a conversation implementation must not initialize the application
bootstrap, which itself imports that implementation. Resolve the bootstrap and
terminal loop only when callers explicitly request those public symbols.
"""
from __future__ import annotations

from sofia.application.conversation_service import ConversationService
from sofia.application.metadata import application_name, application_version

__all__ = [
    "ConversationLoop",
    "ConversationService",
    "SofiaApplication",
    "SofiaApplicationError",
    "application_name",
    "application_version",
]


def __getattr__(name: str):
    if name in ("SofiaApplication", "SofiaApplicationError"):
        from sofia.application.bootstrap import SofiaApplication, SofiaApplicationError
        value = {"SofiaApplication": SofiaApplication,
                 "SofiaApplicationError": SofiaApplicationError}[name]
    elif name == "ConversationLoop":
        from sofia.application.conversation import ConversationLoop
        value = ConversationLoop
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
