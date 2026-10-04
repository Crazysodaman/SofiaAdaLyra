"""Public application exports without an eager bootstrap/import cycle.

Importing conversation services must not initialize the application bootstrap,
which itself imports those services. Resolve bootstrap-owned public symbols only
when callers explicitly request them.
"""
from __future__ import annotations

from sofia.application.conversation_service import ConversationService
from sofia.application.metadata import application_name, application_version

__all__ = [
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
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
