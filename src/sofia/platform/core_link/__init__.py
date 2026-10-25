"""Core Link exports resolved lazily for physically Core-free clients."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "CORE_LINK_BINDING_STORE_ENV": ("binding", "CORE_LINK_BINDING_STORE_ENV"),
    "CoreLinkBinding": ("binding", "CoreLinkBinding"),
    "CoreLinkBindingState": ("binding", "CoreLinkBindingState"),
    "CoreLinkBindingStore": ("binding", "CoreLinkBindingStore"),
    "CoreLinkStoreSnapshot": ("binding", "CoreLinkStoreSnapshot"),
    "CoreLinkClientAccess": ("access", "CoreLinkClientAccess"),
    "CoreLinkClientAccessStore": ("access", "CoreLinkClientAccessStore"),
    "CoreLinkConversationGateway": ("conversation", "CoreLinkConversationGateway"),
    "CoreLinkEndpoint": ("transport", "CoreLinkEndpoint"),
    "CoreLinkServer": ("transport", "CoreLinkServer"),
    "CoreLinkServerConfiguration": ("transport", "CoreLinkServerConfiguration"),
    "CoreLinkTLSCredentials": ("transport", "CoreLinkTLSCredentials"),
    "CoreLinkTransportError": ("transport", "CoreLinkTransportError"),
    "PinnedCoreLinkClient": ("transport", "PinnedCoreLinkClient"),
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

