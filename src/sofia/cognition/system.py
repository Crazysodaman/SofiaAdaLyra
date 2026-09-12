from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.operation import CognitiveOperation


class CognitiveSystem:
    """
    Coordinates Sofía's cognitive engines.

    A cognitive operation supplies both the context for cognition and the
    authority governing that operation. The cognitive engine itself does
    not determine authority.
    """

    def __init__(
        self,
        engine: CognitiveEngine,
        fallback_engine: CognitiveEngine | None = None,
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

        self.engine = engine
        self.fallback_engine = fallback_engine

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

        request = operation.context.request

        try:
            return self.engine.respond(request)

        except CognitiveEngineError as primary_error:
            if self.fallback_engine is None:
                raise

            try:
                return self.fallback_engine.respond(request)

            except CognitiveEngineError as fallback_error:
                raise fallback_error from primary_error