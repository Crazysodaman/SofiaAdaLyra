from abc import ABC, abstractmethod

from sofia.system.model import (
    SystemCapability,
    SystemCapabilityRequest,
    SystemCapabilityResult,
)


class SystemCapabilityBackend(ABC):
    """
    OS-specific implementation boundary for system capabilities.

    Backends provide execution mechanisms and structured evidence.
    They do not decide whether Sofía is authorized to perform
    an operation.

    Authorization belongs to the existing CapabilitySystem.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the canonical backend identifier."""

    @property
    @abstractmethod
    def supported_capabilities(
        self,
    ) -> tuple[SystemCapability, ...]:
        """Return the capabilities supported by this backend."""

    @abstractmethod
    def execute(
        self,
        request: SystemCapabilityRequest,
    ) -> SystemCapabilityResult:
        """
        Execute a supported inspection request.

        Implementations must return structured evidence and must
        never interpret a request as permission to execute arbitrary
        commands or scripts.
        """
        raise NotImplementedError