"""Owner-private read-only inspection of Sofía's unified permission state."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.capability.model import Capability, CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.social.principals import SPARKS_PRINCIPAL_ID

from .permissions import (
    PermissionLevel,
    PermissionStore,
    capability_permission_policy,
    explicitly_classified_capabilities,
    grantable_capabilities,
)


PERMISSION_INSPECT_CAPABILITY = Capability(
    "permissions.inspect",
    "Inspect Sofía's current permission levels, standing grants, and private/adult authority. Owner-private and read-only.",
)


class PermissionInspectionCapability:
    def __init__(self, store: PermissionStore) -> None:
        if not isinstance(store, PermissionStore):
            raise TypeError("store must be PermissionStore")
        self.store = store
        self.capability = PERMISSION_INSPECT_CAPABILITY

    def execute(self, request: CapabilityRequest):
        if request.capability.name != self.capability.name:
            raise ValueError("capability mismatch")
        parameters = dict(request.parameters)
        if parameters.get("__principal_id") != SPARKS_PRINCIPAL_ID:
            raise PermissionError("permission inspection is owner-only")
        if parameters.get("__audience_kind") != "private":
            raise PermissionError(
                "permission inspection requires an authenticated private audience"
            )

        now = datetime.now(timezone.utc)
        grants = []
        for grant in self.store.grants(active_only=False):
            state = (
                "revoked"
                if grant.revoked_at is not None
                else ("active" if grant.is_active_at(now) else "expired")
            )
            grants.append(
                {
                    "grant_id": grant.grant_id,
                    "capability": grant.capability,
                    "scope": grant.scope,
                    "level": int(
                        capability_permission_policy(grant.capability).level
                    ),
                    "granted_by": grant.granted_by,
                    "granted_at": grant.granted_at.isoformat(),
                    "expires_at": (
                        None
                        if grant.expires_at is None
                        else grant.expires_at.isoformat()
                    ),
                    "state": state,
                }
            )

        private = self.store.private_adult_authority()
        capabilities_by_level = {
            str(int(level)): tuple(
                sorted(
                    capability
                    for capability in explicitly_classified_capabilities()
                    if capability_permission_policy(capability).level is level
                )
            )
            for level in PermissionLevel
        }
        return {
            "levels": {
                "1": "observe_read",
                "2": "safe_autonomous",
                "3": "reversible_scoped",
                "4": "protected",
                "5": "never_self_authorized",
            },
            "automatic_levels": (
                int(PermissionLevel.OBSERVE_READ),
                int(PermissionLevel.SAFE_AUTONOMOUS),
            ),
            "capabilities_by_level": capabilities_by_level,
            "grantable_capabilities": grantable_capabilities(),
            "standing_grants": tuple(grants),
            "private_adult": {
                "private_chat": private.private_chat,
                "adult_chat": private.adult_chat,
                "adult_avatar": private.adult_avatar,
                "adult_external_delivery": private.adult_external_delivery,
                "updated_by": private.updated_by,
                "updated_at": (
                    None
                    if private.updated_at is None
                    else private.updated_at.isoformat()
                ),
            },
        }


def create_permission_tool_binding() -> CognitiveToolBinding:
    return CognitiveToolBinding(
        definition=CognitiveToolDefinition(
            name="inspect_permissions",
            description=(
                "Inspect Sofía's live permission levels, standing grants, and "
                "private/adult authority for the authenticated private owner."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        ),
        capability_name=PERMISSION_INSPECT_CAPABILITY.name,
        include_principal_metadata=True,
    )
