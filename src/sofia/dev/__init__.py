"""PKG-DEV bounded engineering primitives."""
from __future__ import annotations

from typing import Any

from .opencode import (
    EngineeringExecutionRequest,
    EngineeringExecutionResult,
    OpenCodeAdapter,
    OpenCodeCommand,
    OpenCodeExecutionError,
    OpenCodeConfigurationError,
    OpenCodeMissingExecutableError,
    OpenCodeTimeoutError,
    OpenCodeScopeError,
)
from sofia.dev.opencode import WorkspaceGuard, WorkspaceViolation
from .git_workspace import (
    GitSnapshot,
    GitWorkspace,
    GitWorkspaceError,
    DirtyScopeError,
    ChangeScopeError,
    path_in_scope,
)
from .workflow import EngineeringCandidate, EngineeringWorkflow

__all__ = [
    "WorkspaceGuard",
    "WorkspaceViolation",
    'EngineeringExecutionRequest',
    'EngineeringExecutionResult',
    'OpenCodeAdapter',
    'OpenCodeCommand',
    'OpenCodeExecutionError',
    'OpenCodeConfigurationError',
    'OpenCodeMissingExecutableError',
    'OpenCodeTimeoutError',
    'OpenCodeScopeError',
    'GitSnapshot',
    'GitWorkspace',
    'GitWorkspaceError',
    'DirtyScopeError',
    'ChangeScopeError',
    'path_in_scope',
    'EngineeringCandidate',
    'EngineeringWorkflow',
    'DevCandidateStore',
    'DevToolService',
    'DevCapabilitySet',
    'create_dev_tool_bindings',
]


def __getattr__(name: str) -> Any:
    if name in {
        "DevCandidateStore",
        "DevToolService",
        "DevCapabilitySet",
        "create_dev_tool_bindings",
    }:
        from .capability import (
            DevCandidateStore,
            DevToolService,
            DevCapabilitySet,
            create_dev_tool_bindings,
        )

        return {
            "DevCandidateStore": DevCandidateStore,
            "DevToolService": DevToolService,
            "DevCapabilitySet": DevCapabilitySet,
            "create_dev_tool_bindings": create_dev_tool_bindings,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
