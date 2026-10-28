"""Compatibility exports for SDK-owned principal and audience contracts.

The principal contracts moved to ``sofia.sdk.principals`` so Platform Core
Link authorization does not import ``sofia.core``.
"""
from sofia.sdk.principals import (
    AudienceKind,
    PrincipalContext,
    ScopeKind,
    SocialScope,
)

__all__ = [
    "AudienceKind",
    "PrincipalContext",
    "ScopeKind",
    "SocialScope",
]
