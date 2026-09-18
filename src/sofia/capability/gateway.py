from sofia.capability.model import (
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultKind,
)
from sofia.capability.proposal import CapabilityProposal
from sofia.capability.system import (
    CapabilityResolutionError,
    CapabilitySystem,
)


class CapabilityGateway:
    """
    Bridges structured capability proposals to the capability system.

    The gateway resolves the canonical registered capability and
    constructs the corresponding CapabilityRequest. It does not
    authorize or execute capabilities itself.

    All authorization and execution remain owned by CapabilitySystem.
    """

    def __init__(
        self,
        capability_system: CapabilitySystem,
    ) -> None:
        if not isinstance(
            capability_system,
            CapabilitySystem,
        ):
            raise TypeError(
                "CapabilityGateway requires a CapabilitySystem."
            )

        self._capability_system = capability_system

    @property
    def capability_system(self) -> CapabilitySystem:
        return self._capability_system

    def execute(
        self,
        proposal: CapabilityProposal,
    ) -> CapabilityResult:
        """
        Resolve and execute a structured capability proposal.

        Resolution uses the canonical capability registered in the
        CapabilitySystem. Authorization and execution are delegated
        entirely to CapabilitySystem.execute().
        """

        if not isinstance(
            proposal,
            CapabilityProposal,
        ):
            raise TypeError(
                "CapabilityGateway proposal must be a "
                "CapabilityProposal."
            )

        try:
            capability = self._capability_system.resolve(
                proposal.capability_name
            )
        except CapabilityResolutionError as exc:
            return CapabilityResult(
                capability=proposal.capability_name,
                kind=CapabilityResultKind.UNAVAILABLE,
                evidence=None,
                error=str(exc),
            )

        request = CapabilityRequest(
            capability=capability,
            parameters=proposal.parameters,
            requested_scope=proposal.requested_scope,
            rationale=proposal.rationale,
        )

        return self._capability_system.execute(
            request
        )