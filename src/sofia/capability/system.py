from collections.abc import Callable
from typing import Any

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultKind,
)


CapabilityHandler = Callable[[CapabilityRequest], Any]
AuthorizationChecker = Callable[[CapabilityRequest], bool]


class CapabilityResolutionError(Exception):
    """Raised when a requested capability cannot be resolved."""


class CapabilityExecutionError(Exception):
    """Raised when capability execution infrastructure fails."""


class CapabilitySystem:
    """
    Resolves and executes registered capabilities.

    Capability availability does not imply authorization.
    Authorization is supplied by the caller and is evaluated before
    capability execution.

    This system does not:
    - interpret natural language,
    - grant authority,
    - approve Actions,
    - execute arbitrary code,
    - modify persistent state by itself.
    """

    def __init__(
        self,
        authorization_checker: AuthorizationChecker | None = None,
    ) -> None:
        self._capabilities: dict[str, tuple[Capability, CapabilityHandler]] = {}
        self._authorization_checker = authorization_checker

    def register(
        self,
        capability: Capability,
        handler: CapabilityHandler,
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable.")

        if capability.name in self._capabilities:
            raise ValueError(
                f"Capability already registered: {capability.name}"
            )

        self._capabilities[capability.name] = (capability, handler)

    def resolve(self, name: str) -> Capability:
        try:
            capability, _ = self._capabilities[name]
        except KeyError as exc:
            raise CapabilityResolutionError(
                f"Unknown capability: {name}"
            ) from exc

        return capability

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        capability_name = request.capability.name

        try:
            _, handler = self._capabilities[capability_name]
        except KeyError:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.UNAVAILABLE,
                evidence=None,
                error=f"Unknown capability: {capability_name}",
            )

        if self._authorization_checker is None:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.UNAUTHORIZED,
                evidence=None,
                error="No authorization checker is configured.",
            )

        try:
            authorized = self._authorization_checker(request)
        except Exception as exc:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.FAILED,
                evidence=None,
                error=f"Authorization evaluation failed: {exc}",
            )

        if not authorized:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.UNAUTHORIZED,
                evidence=None,
                error="Capability request was not authorized.",
            )

        try:
            evidence = handler(request)
        except Exception as exc:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.FAILED,
                evidence=None,
                error=f"Capability execution failed: {exc}",
            )

        return CapabilityResult(
            capability=capability_name,
            kind=CapabilityResultKind.SUCCESS,
            evidence=evidence,
            error=None,
        )