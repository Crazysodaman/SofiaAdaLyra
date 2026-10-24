from pathlib import Path

from datetime import datetime, timezone

from sofia.platform.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.core.codebase.inspector import (
    CodebaseInspector,
)
from sofia.core.codebase.model import (
    CodebaseInspectionEvidence,
)
from sofia.core.codebase.store import CodebaseInspectionStore


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
        evidence_store: CodebaseInspectionStore | None = None,
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
        if evidence_store is not None and not isinstance(
            evidence_store, CodebaseInspectionStore,
        ):
            raise TypeError(
                "evidence_store must be CodebaseInspectionStore or None."
            )
        self._evidence_store = evidence_store

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

        evidence = self._inspector.inspect()
        if self._evidence_store is not None:
            self._evidence_store.record(
                evidence, observed_at=datetime.now(timezone.utc),
            )
        return evidence
