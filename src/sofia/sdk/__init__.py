"""Portable component contracts, lazily loaded across package boundaries."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
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
        name: ("core_link", name) for name in (
            "CoreLinkRequest", "CoreLinkResponse", "CoreLinkResponseStatus",
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
