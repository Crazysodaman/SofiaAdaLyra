"""Platform preflight facade over canonical SAFE authorities.

This service projects current authority. It never records, consumes, or grants
an approval. Effect handlers retain responsibility for atomic approval
consumption immediately before their protected operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import (
    PermissionLevel, PermissionStore, PrivacyClass,
    capability_permission_policy,
)
from sofia.core.social.model import AudienceKind, PrincipalContext


class PolicyDenial(str, Enum):
    NONE = "none"
    IDENTITY = "identity"
    AUDIENCE = "audience"
    OPERATOR_STOP = "operator_stop"
    MODULE_CEILING = "module_ceiling"
    NEVER_SELF_AUTHORIZED = "never_self_authorized"
    APPROVAL_REQUIRED = "approval_required"
    GRANT_REQUIRED = "grant_required"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    capability: str
    allowed: bool
    level: PermissionLevel
    privacy: PrivacyClass
    denial: PolicyDenial
    reason: str
    approval_must_be_consumed: bool
    standing_grant_id: str | None = None


PrincipalVerifier = Callable[[PrincipalContext, str, datetime], bool]


class PlatformSafeFacade:
    """Evaluate effective permission intersection without creating authority."""

    def __init__(self, state_path: Path, *, principal_verifier: PrincipalVerifier) -> None:
        if not isinstance(state_path, Path) or not callable(principal_verifier):
            raise TypeError("state_path and principal_verifier are required")
        self.permissions = PermissionStore(state_path)
        self.approvals = ExecutionApprovalVerifier(state_path)
        self.operator_stop = OperatorStopStore(state_path)
        self.principal_verifier = principal_verifier

    @staticmethod
    def _denied(capability: str, level: PermissionLevel, privacy: PrivacyClass,
                denial: PolicyDenial, reason: str) -> PolicyDecision:
        return PolicyDecision(
            capability, False, level, privacy, denial, reason, False, None,
        )

    def evaluate(
        self, *, principal: PrincipalContext, principal_attestation_ref: str,
        capability: str, parameters: dict[str, object], module_permission_ceiling: int,
        now: datetime, approval_id: str | None = None,
    ) -> PolicyDecision:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if not isinstance(principal_attestation_ref, str) or not principal_attestation_ref:
            raise ValueError("principal_attestation_ref required")
        if not isinstance(parameters, dict):
            raise TypeError("parameters must be a dict")
        if type(module_permission_ceiling) is not int or not 1 <= module_permission_ceiling <= 5:
            raise ValueError("module_permission_ceiling must be in 1..5")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        policy = capability_permission_policy(capability)
        try:
            authenticated = self.principal_verifier(
                principal, principal_attestation_ref, moment,
            ) is True
        except Exception:
            authenticated = False
        if not authenticated:
            return self._denied(
                capability, policy.level, policy.privacy, PolicyDenial.IDENTITY,
                "principal authentication is missing, stale, or invalid",
            )
        if principal.audience_kind is not AudienceKind.PRIVATE:
            return self._denied(
                capability, policy.level, policy.privacy, PolicyDenial.AUDIENCE,
                "Platform capability execution requires its authenticated private audience",
            )
        if self.operator_stop.current().active:
            return self._denied(
                capability, policy.level, policy.privacy,
                PolicyDenial.OPERATOR_STOP, "operator STOP is active",
            )
        if int(policy.level) > module_permission_ceiling:
            return self._denied(
                capability, policy.level, policy.privacy,
                PolicyDenial.MODULE_CEILING,
                "module operation profile authority ceiling is lower than capability policy",
            )
        if policy.level is PermissionLevel.NEVER_SELF_AUTHORIZED:
            return self._denied(
                capability, policy.level, policy.privacy,
                PolicyDenial.NEVER_SELF_AUTHORIZED,
                "authority-changing capability cannot be authorized by a module profile",
            )
        if policy.level <= PermissionLevel.SAFE_AUTONOMOUS:
            return PolicyDecision(
                capability, True, policy.level, policy.privacy,
                PolicyDenial.NONE, "authenticated automatic capability", False,
            )
        matching = next((
            grant for grant in self.permissions.grants(active_only=False)
            if grant.capability == capability and grant.matches(parameters, now=moment)
        ), None)
        if policy.level is PermissionLevel.REVERSIBLE_SCOPED and matching is not None:
            return PolicyDecision(
                capability, True, policy.level, policy.privacy,
                PolicyDenial.NONE, "active exact-scope standing grant", False,
                matching.grant_id,
            )
        if self.approvals.matches_unconsumed(
            approval_id=approval_id, capability=capability,
            parameters=parameters, now=moment,
        ):
            return PolicyDecision(
                capability, True, policy.level, policy.privacy,
                PolicyDenial.NONE,
                "exact unconsumed owner approval; effect handler must consume it",
                True,
            )
        denial = (
            PolicyDenial.GRANT_REQUIRED
            if policy.level is PermissionLevel.REVERSIBLE_SCOPED
            else PolicyDenial.APPROVAL_REQUIRED
        )
        return self._denied(
            capability, policy.level, policy.privacy, denial,
            "current exact authorization is unavailable",
        )
