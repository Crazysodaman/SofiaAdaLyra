from collections.abc import Callable
from typing import Any

from sofia.platform.capability.model import (
    Capability,
    CapabilityExecutionError,
    CapabilityRequest,
    CapabilityResolutionError,
    CapabilityResult,
    CapabilityResultKind,
)


CapabilityHandler = Callable[[CapabilityRequest], Any]
AuthorizationChecker = Callable[[CapabilityRequest], bool]


class CapabilitySystem:
    """
    Resolves and executes registered capabilities.

    Capability availability does not imply authorization.
    Authorization is supplied by the caller and is evaluated before
    capability execution.

    Registered capabilities are authoritative. A request may not replace
    a registered capability with a look-alike capability that happens to
    use the same name.

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
        self._capabilities: dict[
            str,
            tuple[Capability, CapabilityHandler],
        ] = {}
        self._authorization_checker = authorization_checker

    def register(
        self,
        capability: Capability,
        handler: CapabilityHandler,
    ) -> None:
        if not isinstance(capability, Capability):
            raise TypeError("capability must be a Capability.")

        if not callable(handler):
            raise TypeError("handler must be callable.")

        if capability.name in self._capabilities:
            raise ValueError(
                f"Capability already registered: {capability.name}"
            )

        self._capabilities[capability.name] = (
            capability,
            handler,
        )

    def register_batch(
        self,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
    ) -> None:
        """Register one module's capabilities atomically in memory."""
        self.validate_batch(registrations)
        self._capabilities.update(
            (capability.name, (capability, handler))
            for capability, handler in registrations
        )

    def validate_batch(
        self,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
    ) -> None:
        """Perform non-effectful registration validation before authority use."""
        if type(registrations) is not tuple or not registrations:
            raise ValueError("registrations must be a nonempty tuple")
        names: list[str] = []
        for capability, handler in registrations:
            if not isinstance(capability, Capability):
                raise TypeError("capability must be a Capability")
            if not callable(handler):
                raise TypeError("handler must be callable")
            names.append(capability.name)
        if len(names) != len(set(names)):
            raise ValueError("batch contains duplicate capability names")
        conflicts = sorted(set(names) & set(self._capabilities))
        if conflicts:
            raise ValueError(
                f"Capabilities already registered: {', '.join(conflicts)}"
            )

    def unregister_batch(
        self,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
    ) -> None:
        """Remove exactly a previously registered batch, never look-alikes."""
        if type(registrations) is not tuple or not registrations:
            raise ValueError("registrations must be a nonempty tuple")
        for capability, handler in registrations:
            current = self._capabilities.get(capability.name)
            if current is None or current[0] != capability or current[1] is not handler:
                raise RuntimeError(
                    "capability batch changed; refusing partial unregister"
                )
        for capability, _ in registrations:
            del self._capabilities[capability.name]

    def capabilities(self) -> tuple[Capability, ...]:
        """Return the registered canonical capability descriptors."""
        return tuple(
            self._capabilities[name][0]
            for name in sorted(self._capabilities)
        )

    def capability_names(self) -> tuple[str, ...]:
        """Return registered capability names in stable order."""
        return tuple(capability.name for capability in self.capabilities())

    def resolve(self, name: str) -> Capability:
        try:
            capability, _ = self._capabilities[name]
        except KeyError as exc:
            raise CapabilityResolutionError(
                f"Unknown capability: {name}"
            ) from exc

        return capability

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        if not isinstance(request, CapabilityRequest):
            raise TypeError(
                "CapabilitySystem.execute requires a CapabilityRequest."
            )

        capability_name = request.capability.name

        try:
            registered_capability, handler = self._capabilities[
                capability_name
            ]
        except KeyError:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.UNAVAILABLE,
                evidence=None,
                error=f"Unknown capability: {capability_name}",
            )

        if request.capability != registered_capability:
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.DENIED,
                evidence=None,
                error=(
                    "Capability request does not match the "
                    "registered capability."
                ),
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
        except PermissionError as exc:
            # The executing handler has not been called, so this is a
            # definitive authority refusal rather than an uncertain effect.
            return CapabilityResult(
                capability=capability_name,
                kind=CapabilityResultKind.UNAUTHORIZED,
                evidence=None,
                error=f"Authorization denied: {exc}",
            )
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
