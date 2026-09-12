from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)


class CognitiveSystem:
    """
    Coordinates Sofía's cognitive engines.
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
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        try:
            return self.engine.respond(request)

        except CognitiveEngineError as primary_error:
            if self.fallback_engine is None:
                raise

            try:
                return self.fallback_engine.respond(request)

            except CognitiveEngineError as fallback_error:
                raise fallback_error from primary_error