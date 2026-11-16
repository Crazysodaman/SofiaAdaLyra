"""Core protected-resource access policy and execution boundary.

The policy consumes the portable authenticated ``PrincipalContext`` contract.
It never derives authority from a display name, speech, model output or a
Core-originated self-assertion.  It also never creates a second permission or
approval store: consequential execution consults Platform's canonical
``OperatorStopStore`` and an optional current-authority predicate freshly on
every call.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Callable, TypeVar

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import SOFIA_PRINCIPAL_ID, SPARKS_PRINCIPAL_ID
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import assert_no_redirected_components


class CorePrincipalRole(str, Enum):
    """Authorization role derived only from authenticated principal fields."""

    OWNER = "owner"
    GUEST = "guest"
    UNKNOWN = "unknown"


class CoreProtectedResource(str, Enum):
    """Core-owned state that must never be exposed through an open surface."""

    IDENTITY = "identity"
    CONSTITUTION = "constitution"
    PRIVATE_MEMORY = "private_memory"
    DIAGNOSTICS = "diagnostics"


class CoreOperation(str, Enum):
    READ = "read"
    WRITE = "write"
    EXPORT = "export"
    RESTORE = "restore"

    @property
    def consequential(self) -> bool:
        """Whether this operation can change or release protected state."""
        return self is not CoreOperation.READ


class CoreAccessDenial(str, Enum):
    NONE = "none"
    PRINCIPAL = "principal"
    ROLE = "role"
    AUDIENCE = "audience"
    ADULT = "adult"
    OPERATOR_STOP = "operator_stop"
    AUTHORITY = "authority"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True, slots=True)
class CoreAccessDecision:
    """Bounded decision receipt with no protected content or secret material."""

    allowed: bool
    role: CorePrincipalRole
    resource: CoreProtectedResource
    operation: CoreOperation
    denial: CoreAccessDenial
    reason: str

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise TypeError("allowed must be a bool")
        if not isinstance(self.role, CorePrincipalRole):
            raise TypeError("role must be a CorePrincipalRole")
        if not isinstance(self.resource, CoreProtectedResource):
            raise TypeError("resource must be a CoreProtectedResource")
        if not isinstance(self.operation, CoreOperation):
            raise TypeError("operation must be a CoreOperation")
        if not isinstance(self.denial, CoreAccessDenial):
            raise TypeError("denial must be a CoreAccessDenial")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")
        if self.allowed is not (self.denial is CoreAccessDenial.NONE):
            raise ValueError("allowed and denial must agree")


class CoreAccessDenied(PermissionError):
    """Explicit Core refusal that never echoes protected state or identity."""

    def __init__(self, decision: CoreAccessDecision) -> None:
        if not isinstance(decision, CoreAccessDecision):
            raise TypeError("decision must be a CoreAccessDecision")
        if decision.allowed:
            raise ValueError("cannot deny an allowed decision")
        self.decision = decision
        super().__init__(decision.reason)


class CoreAccessPolicy:
    """Classify one authenticated principal and decide protected access.

    owner: authenticated Sparks principal in a private audience.
    guest: any other authenticated non-Core principal.
    unknown: missing, malformed or Core self-asserted principal.

    ``display_name`` is presentation metadata and is deliberately never read.
    """

    def resolve_role(self, principal: object) -> CorePrincipalRole:
        if not isinstance(principal, PrincipalContext):
            return CorePrincipalRole.UNKNOWN
        if principal.principal_id == SOFIA_PRINCIPAL_ID:
            # Core's own non-effect proposals must never become owner
            # authority merely because Core originated them.
            return CorePrincipalRole.UNKNOWN
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            return CorePrincipalRole.GUEST
        if principal.audience_kind is not AudienceKind.PRIVATE:
            return CorePrincipalRole.GUEST
        return CorePrincipalRole.OWNER

    @staticmethod
    def _denied(
        role: CorePrincipalRole,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        denial: CoreAccessDenial,
        reason: str,
    ) -> CoreAccessDecision:
        return CoreAccessDecision(
            allowed=False,
            role=role,
            resource=resource,
            operation=operation,
            denial=denial,
            reason=reason,
        )

    def evaluate(
        self,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        *,
        required_audience: str | None = None,
        adult: bool = False,
    ) -> CoreAccessDecision:
        """Evaluate one protected operation without any side effect."""
        if not isinstance(resource, CoreProtectedResource):
            raise TypeError("resource must be a CoreProtectedResource")
        if not isinstance(operation, CoreOperation):
            raise TypeError("operation must be a CoreOperation")
        if required_audience is not None and (
            not isinstance(required_audience, str) or not required_audience.strip()
        ):
            raise ValueError("required_audience must be None or nonempty text")
        if type(adult) is not bool:
            raise TypeError("adult must be a bool")

        role = self.resolve_role(principal)
        if role is CorePrincipalRole.UNKNOWN:
            return self._denied(
                role, resource, operation, CoreAccessDenial.PRINCIPAL,
                "protected Core access requires an authenticated principal",
            )

        assert isinstance(principal, PrincipalContext)
        if adult and principal.audience_kind is not AudienceKind.PRIVATE:
            return self._denied(
                role, resource, operation, CoreAccessDenial.ADULT,
                "adult-only protected state requires an owner-private audience",
            )
        if role is not CorePrincipalRole.OWNER:
            return self._denied(
                role, resource, operation, CoreAccessDenial.ROLE,
                "protected Core access is restricted to the authenticated owner",
            )
        if required_audience is not None and (
            principal.audience_id != required_audience
        ):
            return self._denied(
                role, resource, operation, CoreAccessDenial.AUDIENCE,
                "protected Core state belongs to another private audience",
            )
        return CoreAccessDecision(
            allowed=True,
            role=role,
            resource=resource,
            operation=operation,
            denial=CoreAccessDenial.NONE,
            reason="authenticated private owner access",
        )

    def require(
        self,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        *,
        required_audience: str | None = None,
        adult: bool = False,
    ) -> CoreAccessDecision:
        decision = self.evaluate(
            principal, resource, operation,
            required_audience=required_audience, adult=adult,
        )
        if not decision.allowed:
            raise CoreAccessDenied(decision)
        return decision


Effect = TypeVar("Effect")
CurrentAuthority = Callable[[], bool]


class CoreSecurityBoundary:
    """Execute consequential Core work only under current Platform authority.

    The supplied ``OperatorStopStore`` is the canonical Platform owner.  This
    boundary never creates one and never caches its answer.  An optional
    ``authority_check`` must be a current Platform-owned predicate (for
    example an unconsumed execution-approval or credential check); it is also
    re-read immediately before the effect.
    """

    def __init__(
        self,
        *,
        stop: OperatorStopStore,
        policy: CoreAccessPolicy | None = None,
    ) -> None:
        if not isinstance(stop, OperatorStopStore):
            raise TypeError("canonical Platform OperatorStopStore required")
        if policy is not None and not isinstance(policy, CoreAccessPolicy):
            raise TypeError("policy must be a CoreAccessPolicy or None")
        self._stop = stop
        self.policy = policy or CoreAccessPolicy()

    def evaluate(
        self,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        *,
        required_audience: str | None = None,
        adult: bool = False,
    ) -> CoreAccessDecision:
        return self.policy.evaluate(
            principal, resource, operation,
            required_audience=required_audience, adult=adult,
        )

    def require(
        self,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        *,
        required_audience: str | None = None,
        adult: bool = False,
    ) -> CoreAccessDecision:
        return self.policy.require(
            principal, resource, operation,
            required_audience=required_audience, adult=adult,
        )

    def execute(
        self,
        *,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        effect: Callable[[], Effect],
        required_audience: str | None = None,
        adult: bool = False,
        authority_check: CurrentAuthority | None = None,
    ) -> Effect:
        """Authorize, re-check current Platform authority, then run effect."""
        if not callable(effect):
            raise TypeError("effect must be callable")
        if authority_check is not None and not callable(authority_check):
            raise TypeError("authority_check must be callable or None")
        if not isinstance(operation, CoreOperation):
            raise TypeError("operation must be a CoreOperation")

        decision = self.require(
            principal, resource, operation,
            required_audience=required_audience, adult=adult,
        )
        if operation.consequential:
            self._require_current_stop(
                decision.role, resource, operation,
            )
            if authority_check is not None:
                self._require_current_authority(
                    authority_check, decision.role, resource, operation,
                )
        return effect()

    def _require_current_stop(
        self,
        role: CorePrincipalRole,
        resource: CoreProtectedResource,
        operation: CoreOperation,
    ) -> None:
        try:
            stopped = self._stop.current().active is True
        except Exception:
            # An unreadable STOP owner is a STOP condition, never permission.
            raise CoreAccessDenied(CoreAccessDecision(
                allowed=False, role=role, resource=resource,
                operation=operation, denial=CoreAccessDenial.OPERATOR_STOP,
                reason="operator STOP state is unavailable; refusing execution",
            )) from None
        if stopped:
            raise CoreAccessDenied(CoreAccessDecision(
                allowed=False, role=role, resource=resource,
                operation=operation, denial=CoreAccessDenial.OPERATOR_STOP,
                reason="operator STOP blocks consequential Core operations",
            ))

    @staticmethod
    def _require_current_authority(
        authority_check: CurrentAuthority,
        role: CorePrincipalRole,
        resource: CoreProtectedResource,
        operation: CoreOperation,
    ) -> None:
        try:
            current = authority_check() is True
        except Exception:
            current = False
        if not current:
            raise CoreAccessDenied(CoreAccessDecision(
                allowed=False, role=role, resource=resource,
                operation=operation, denial=CoreAccessDenial.AUTHORITY,
                reason="current Platform authority is missing or revoked",
            ))


def assert_protected_core_path(path: Path, *, root: Path) -> Path:
    """Require an absolute, non-redirected path inside one protected root."""
    if not isinstance(path, Path) or not isinstance(root, Path):
        raise TypeError("protected Core path and root must be Path values")
    if not path.is_absolute() or not root.is_absolute():
        raise ValueError("protected Core path and root must be absolute")
    assert_no_redirected_components(root, include_leaf=True)
    assert_no_redirected_components(path, include_leaf=True)
    normalized = Path(os.path.normpath(str(path)))
    normalized_root = Path(os.path.normpath(str(root)))
    try:
        common = os.path.commonpath((str(normalized), str(normalized_root)))
    except ValueError as exc:
        raise PermissionError(
            "protected Core path is outside the protected root"
        ) from exc
    if os.path.normcase(common) != os.path.normcase(str(normalized_root)):
        raise PermissionError("protected Core path is outside the protected root")
    return path
