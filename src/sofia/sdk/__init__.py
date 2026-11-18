"""Portable component contracts, lazily loaded across package boundaries."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "CognitiveToolBinding": ("tool_binding", "CognitiveToolBinding"),
    **{
        name: ("identity", name) for name in (
            "AegisIdentity", "IdentityKind", "IDENTITY_SCHEMA",
        )
    },
    **{
        name: ("contracts", name) for name in (
            "AuthorityProjection", "ComponentEndpoint", "ComponentKind",
            "ComponentOutcome", "ComponentRequestEnvelope",
            "ComponentResponseEnvelope", "ProtocolVersion",
            "ProtocolVersionRange", "SDK_PROTOCOL_VERSION",
            "negotiate_protocol",
        )
    },
    **{
        name: ("state", name) for name in (
            "StateProjection", "StateReadFacade", "StateWriteFacade",
        )
    },
    **{
        name: ("cognition", name) for name in (
            "decode_request", "decode_response", "encode_request",
            "encode_response",
        )
    },
    **{
        name: ("voice_expression", name) for name in (
            "VoiceExpressionCue", "VOICE_EXPRESSION_SCHEMA",
            "VOICE_SYNTHESIZE_SCOPE",
        )
    },
    **{
        name: ("core_link", name) for name in (
            "CoreLinkRequest", "CoreLinkResponse", "CoreLinkResponseStatus",
        )
    },
    **{
        name: ("module_settings", name) for name in (
            "ModuleSettingApplyClass", "ModuleSettingField",
            "ModuleSettingType", "ModuleSettingsContract",
            "module_settings_contract_from_document",
            "module_settings_contract_to_document",
        )
    },
    **{
        name: ("core_capabilities", name) for name in (
            "CAPABILITY_RECEIPT_SCHEMA", "CORE_CAPABILITIES_SCHEMA",
            "MAX_CAPABILITY_FAMILIES", "BodyCapability",
            "BodyCapabilityProfile", "CapabilityError", "CapabilityFamily",
            "CapabilityOutcome", "CapabilityReceipt", "CapabilityState",
            "CoreCapabilityContract", "RendererCapability",
            "UNIVERSAL_CAPABILITY_FAMILIES", "definition_digest_for",
            "derive_core_capability_contract", "unavailable_receipt",
        )
    },
    **{
        name: ("gesture_contract", name) for name in (
            "ADULT_REVIEWED_POLICY", "ADULT_SCENE_SCHEMA",
            "GESTURE_CONTRACT_SCHEMA", "GESTURE_RECEIPT_SCHEMA",
            "AdultEligibility", "AdultSceneDecision", "AdultSceneReceipt",
            "AdultSceneRequest", "GestureClass", "GestureCompatibility",
            "GestureCompatibilityStatus", "GestureDefinition", "GestureError",
            "GestureEvidence", "GestureExecution", "GestureParty",
            "GesturePartyKind", "GesturePlaybackReceipt", "GesturePrivacy",
            "GestureStateError", "IntimacyDimensions", "SceneAudience",
            "evaluate_adult_scene", "resolve_gesture_compatibility",
        )
    },
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
