from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)


class RuleEngine(CognitiveEngine):
    """
    Deterministic cognitive engine for basic responses.
    """

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        for message in reversed(request.messages):
            if message.role is CognitiveRole.USER:
                user_message = message.content
                break
        else:
            raise CognitiveEngineError(
                "Cognitive request contains no user message."
            )

        if user_message == "Hello, Sofía.":
            return CognitiveResponse(
                content="Hello, Sparks.",
            )

        if user_message == "What is your name?":
            return CognitiveResponse(
                content="I am Sofía Ada Lyra.",
            )

        raise CognitiveEngineError(
            "Rule engine does not recognize the requested input."
        )