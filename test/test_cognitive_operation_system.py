import pytest

from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.system import CognitiveSystem


class RecordingEngine(CognitiveEngine):
    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.requests.append(request)

        return CognitiveResponse(
            content="Recorded response.",
        )


class FailingEngine(CognitiveEngine):
    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        raise CognitiveEngineError(
            "Primary engine failed."
        )


class FallbackEngine(CognitiveEngine):
    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.requests.append(request)

        return CognitiveResponse(
            content="Fallback response.",
        )


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Test operation.",
            ),
        )
    )


def make_operation(
    authority: Authority | None = None,
) -> CognitiveOperation:
    return CognitiveOperation(
        context=CognitiveContext(
            request=make_request(),
        ),
        authority=authority or Authority(),
    )


def test_respond_to_operation_uses_assembled_context_request() -> None:
    engine = RecordingEngine()
    system = CognitiveSystem(
        engine=engine,
    )

    operation = make_operation()

    response = system.respond_to_operation(operation)

    assert response.content == "Recorded response."

    assert engine.requests == [
        system.context_assembler.assemble(
            operation.context,
        ),
    ]


def test_respond_to_operation_preserves_supplied_authority() -> None:
    engine = RecordingEngine()
    system = CognitiveSystem(
        engine=engine,
    )

    authority = Authority(
        can_respond=True,
        can_propose_actions=False,
        can_execute_actions=True,
    )

    operation = make_operation(
        authority=authority,
    )

    system.respond_to_operation(operation)

    assert operation.authority is authority
    assert operation.authority.can_respond is True
    assert operation.authority.can_propose_actions is False
    assert operation.authority.can_execute_actions is True


def test_respond_to_operation_does_not_put_authority_in_request() -> None:
    engine = RecordingEngine()
    system = CognitiveSystem(
        engine=engine,
    )

    operation = make_operation(
        authority=Authority(
            can_execute_actions=True,
        ),
    )

    system.respond_to_operation(operation)

    request = engine.requests[0]

    assert not hasattr(request, "authority")


def test_respond_to_operation_rejects_invalid_operation() -> None:
    engine = RecordingEngine()
    system = CognitiveSystem(
        engine=engine,
    )

    with pytest.raises(TypeError):
        system.respond_to_operation(
            "not an operation",
        )


def test_respond_to_operation_uses_fallback_engine() -> None:
    primary = FailingEngine()
    fallback = FallbackEngine()

    system = CognitiveSystem(
        engine=primary,
        fallback_engine=fallback,
    )

    operation = make_operation()

    response = system.respond_to_operation(operation)

    assert response.content == "Fallback response."

    assert fallback.requests == [
        system.context_assembler.assemble(
            operation.context,
        ),
    ]


def test_respond_to_operation_preserves_primary_error_when_no_fallback() -> None:
    system = CognitiveSystem(
        engine=FailingEngine(),
    )

    with pytest.raises(
        CognitiveEngineError,
        match="Primary engine failed.",
    ):
        system.respond_to_operation(
            make_operation(),
        )


def test_respond_requires_explicit_operation() -> None:
    engine = RecordingEngine()
    system = CognitiveSystem(
        engine=engine,
    )

    with pytest.raises(TypeError):
        system.respond(
            make_request(),
        )