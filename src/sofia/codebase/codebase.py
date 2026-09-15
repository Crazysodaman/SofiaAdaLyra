from sofia.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.codebase.inspector import (
    CodebaseInspector,
)


CODEBASE_INSPECT_CAPABILITY = Capability(
    name="codebase.inspect",
    description=(
        "Perform bounded, read-only structural inspection "
        "of the authorized Sofía codebase."
    ),
)


class CodebaseCapability:
    """
    Adapter between the generic capability system and
    the codebase inspection subsystem.
    """

    def __init__(
        self,
        inspector: CodebaseInspector,
    ) -> None:
        self._inspector = inspector

    @property
    def capability(self) -> Capability:
        return CODEBASE_INSPECT_CAPABILITY

    def execute(
        self,
        request: CapabilityRequest,
    ):
        if request.capability.name != (
            CODEBASE_INSPECT_CAPABILITY.name
        ):
            raise ValueError(
                "CodebaseCapability received an unsupported "
                "capability request."
            )

        return self._inspector.inspect()