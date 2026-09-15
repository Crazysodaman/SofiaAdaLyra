from dataclasses import dataclass

from sofia.capability.model import (
    CapabilityRequest,
)
from sofia.capability.system import (
    CapabilitySystem,
)
from sofia.codebase.codebase import (
    CODEBASE_INSPECT_CAPABILITY,
)


class CapabilityRoutingError(Exception):
    """
    Raised when a user request cannot be mapped to a capability.
    """


@dataclass(frozen=True)
class CapabilityRoute:
    """
    Structured description of a capability request derived from
    an explicit supported request form.

    This is routing, not cognitive reasoning.
    """

    request: CapabilityRequest


class CapabilityRouter:
    """
    Maps explicitly supported application requests to capabilities.

    This router does not grant authority and does not execute
    capabilities directly.
    """

    _CODEBASE_PHRASES = (
        "inspect your codebase",
        "inspect the codebase",
        "inspect your own codebase",
        "check your codebase",
        "check the codebase",
        "check your own codebase",
        "analyze your codebase",
        "analyze the codebase",
        "understand your codebase",
        "understand the codebase",
        "inspect your source code",
        "inspect your source",
        "check your source code",
    )

    def __init__(
        self,
        capability_system: CapabilitySystem,
    ) -> None:
        if not isinstance(
            capability_system,
            CapabilitySystem,
        ):
            raise TypeError(
                "CapabilityRouter requires a CapabilitySystem."
            )

        self._capability_system = capability_system

    def route(
        self,
        content: str,
        requested_scope=None,
    ) -> CapabilityRoute | None:
        if not isinstance(
            content,
            str,
        ):
            raise TypeError(
                "CapabilityRouter content must be a string."
            )

        normalized = " ".join(
            content.lower().split()
        )

        if not normalized:
            return None

        if not any(
            phrase in normalized
            for phrase in self._CODEBASE_PHRASES
        ):
            return None

        capability = self._capability_system.resolve(
            CODEBASE_INSPECT_CAPABILITY.name
        )

        request = CapabilityRequest(
            capability=capability,
            parameters={},
            requested_scope=requested_scope,
            rationale=content.strip(),
        )

        return CapabilityRoute(
            request=request,
        )