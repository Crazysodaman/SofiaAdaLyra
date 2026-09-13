from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.operation import CognitiveOperation


class CognitiveSystemError(Exception):
    """
    Raised when the cognitive system cannot execute an operation.
    """


class CognitiveSystem:
    """
    Coordinates Sofía's cognitive engines.

    A cognitive operation supplies both the context for cognition and the
    authority governing that operation.

    Context assembly and authority enforcement occur outside the cognitive
    engine itself.
    """

    def __init__(
        self,
        engine: CognitiveEngine,
        fallback_engine: CognitiveEngine | None = None,
        context_assembler: CognitiveContextAssembler | None = None,
    ):
        if not isinstance(engine, CognitiveEngine):
            raise TypeError(
                "CognitiveSystem requires a CognitiveEngine."
            )

        if (
            fallback_engine is not None
            and not isinstance(fallback_engine, CognitiveEngine)
        ):
            raise TypeError(
                "CognitiveSystem fallback_engine must be a CognitiveEngine."
            )

        if (
            context_assembler is not None
            and not isinstance(
                context_assembler,
                CognitiveContextAssembler,
            )
        ):
            raise TypeError(
                "CognitiveSystem context_assembler must be a "
                "CognitiveContextAssembler."
            )

        self.engine = engine
        self.fallback_engine = fallback_engine
        self.context_assembler = (
            context_assembler
            if context_assembler is not None
            else CognitiveContextAssembler()
        )

    def respond(
        self,
        operation: CognitiveOperation,
    ) -> CognitiveResponse:
        return self.respond_to_operation(operation)

    def respond_to_operation(
        self,
        operation: CognitiveOperation,
    ) -> CognitiveResponse:
        if not isinstance(operation, CognitiveOperation):
            raise TypeError(
                "CognitiveSystem operation must be a CognitiveOperation."
            )

        if not operation.authority.can_respond:
            raise CognitiveSystemError(
                "Cognitive operation is not authorized to produce a response."
            )

        request = self.context_assembler.assemble(
            operation.context
        )

        try:
            return self.engine.respond(request)

        except CognitiveEngineError as primary_error:
            if self.fallback_engine is None:
                raise

            try:
                return self.fallback_engine.respond(request)

            except CognitiveEngineError as fallback_error:
                raise fallback_error from primary_error