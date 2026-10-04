"""Public application exports without an eager bootstrap/import cycle.

Package and metadata imports must not initialize conversation, runtime or
bootstrap dependencies. Resolve each public symbol from its owning module only
when callers explicitly request it.
"""
from __future__ import annotations

from importlib import import_module

_EXPORT_MODULES = {
    "ConversationService": "sofia.application.conversation_service",
    "SofiaApplication": "sofia.application.bootstrap",
    "SofiaApplicationError": "sofia.application.bootstrap",
    "application_name": "sofia.package_metadata",
    "application_version": "sofia.package_metadata",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
