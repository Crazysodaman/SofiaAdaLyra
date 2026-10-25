"""Portable Sofía component contracts with no runtime authority."""

from .contracts import (
    AuthorityProjection,
    ComponentEndpoint,
    ComponentKind,
    ComponentOutcome,
    ComponentRequestEnvelope,
    ComponentResponseEnvelope,
    ProtocolVersion,
    ProtocolVersionRange,
    SDK_PROTOCOL_VERSION,
    negotiate_protocol,
)
from .state import StateProjection, StateReadFacade, StateWriteFacade
from .cognition import decode_request, decode_response, encode_request, encode_response
from .core_link import CoreLinkRequest, CoreLinkResponse, CoreLinkResponseStatus

__all__ = [
    "AuthorityProjection",
    "ComponentEndpoint",
    "ComponentKind",
    "ComponentOutcome",
    "ComponentRequestEnvelope",
    "ComponentResponseEnvelope",
    "ProtocolVersion",
    "ProtocolVersionRange",
    "SDK_PROTOCOL_VERSION",
    "StateProjection",
    "StateReadFacade",
    "StateWriteFacade",
    "negotiate_protocol",
    "decode_request",
    "decode_response",
    "encode_request",
    "encode_response",
    "CoreLinkRequest",
    "CoreLinkResponse",
    "CoreLinkResponseStatus",
]
