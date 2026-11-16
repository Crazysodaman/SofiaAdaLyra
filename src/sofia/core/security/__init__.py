"""Core-side permission boundaries over existing principal authority.

This package adds no approval, grant, credential or operator-state store.  It
classifies an already authenticated ``PrincipalContext`` for protected Core
resources and delegates every consequential STOP or approval decision to the
canonical Platform owner, re-read at execution time.
"""
from sofia.core.security.boundary import (
    CoreAccessDecision,
    CoreAccessDenial,
    CoreAccessDenied,
    CoreAccessPolicy,
    CoreOperation,
    CorePrincipalRole,
    CoreProtectedResource,
    CoreSecurityBoundary,
    PrincipalVerifier,
    assert_protected_core_path,
)
from sofia.core.security.protected import (
    ProtectedCoreState,
    ProtectedCoreStateError,
    ProtectedIdentityView,
)

__all__ = [
    "CoreAccessDecision",
    "CoreAccessDenial",
    "CoreAccessDenied",
    "CoreAccessPolicy",
    "CoreOperation",
    "CorePrincipalRole",
    "CoreProtectedResource",
    "CoreSecurityBoundary",
    "PrincipalVerifier",
    "ProtectedCoreState",
    "ProtectedCoreStateError",
    "ProtectedIdentityView",
    "assert_protected_core_path",
]
