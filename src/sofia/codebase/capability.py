from pathlib import Path

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.codebase.inspector import (
    CodebaseInspector,
)
from sofia.codebase.model import (
    CodebaseInspectionEvidence,
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

    This capability performs observation only.

    It does not modify source files, execute Python, execute shell
    commands, invoke Git, or grant authorization.
    """

    def __init__(
        self,
        inspector: CodebaseInspector,
    ) -> None:
        if not isinstance(
            inspector,
            CodebaseInspector,
        ):
            raise TypeError(
                "CodebaseCapability inspector must be a "
                "CodebaseInspector."
            )

        self._inspector = inspector

    @property
    def capability(self) -> Capability:
        return CODEBASE_INSPECT_CAPABILITY

    @property
    def inspector(self) -> CodebaseInspector:
        return self._inspector

    def execute(
        self,
        request: CapabilityRequest,
    ) -> CodebaseInspectionEvidence:
        if not isinstance(
            request,
            CapabilityRequest,
        ):
            raise TypeError(
                "CodebaseCapability request must be a "
                "CapabilityRequest."
            )

        if request.capability.name != (
            CODEBASE_INSPECT_CAPABILITY.name
        ):
            raise ValueError(
                "CodebaseCapability received an unsupported "
                "capability request."
            )

        requested_scope = request.requested_scope

        if requested_scope is not None:
            if not isinstance(
                requested_scope,
                Path,
            ):
                raise TypeError(
                    "CodebaseCapability requested_scope must "
                    "be a Path or None."
                )

            if requested_scope.resolve() != self._inspector.root:
                raise ValueError(
                    "CodebaseCapability request scope does not "
                    "match the configured codebase root."
                )

        return self._inspector.inspect()