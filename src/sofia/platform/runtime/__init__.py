"""Runtime package public surface without eager SofiaRuntime import.

Submodules such as sofia.platform.runtime.clock are foundational dependencies used by
PKG-ENVIRONMENT. Importing them must not eagerly import sofia.platform.runtime.runtime,
which itself depends on ENVIRONMENT.
"""
from __future__ import annotations

from sofia.platform.runtime.model import RuntimeState

__all__ = [
    "RuntimeState",
    "SofiaRuntime",
    "SofiaRuntimeError",
]


def __getattr__(name: str):
    if name in {"SofiaRuntime", "SofiaRuntimeError"}:
        from sofia.platform.runtime.runtime import SofiaRuntime, SofiaRuntimeError

        globals()["SofiaRuntime"] = SofiaRuntime
        globals()["SofiaRuntimeError"] = SofiaRuntimeError
        return globals()[name]
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
