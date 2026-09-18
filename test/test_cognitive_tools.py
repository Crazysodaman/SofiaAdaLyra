from pathlib import Path

import pytest

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import (
    Capability,
    CapabilityResultKind,
)
from sofia.capability.system import CapabilitySystem
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
)
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.tools import (
    CognitiveToolBinding,
    CognitiveToolDispatcher,
    CognitiveToolError,
)
from sofia.cognition.model import (
    CognitiveToolDefinition,
)
from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext


TEST_CAPABILITY = Capability(
    name="test.inspect",
    description="Test inspection capability.",
)


def create_dispatcher():
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    capability_system.register(
        capability=TEST_CAPABILITY,
        handler=lambda request: {
            "received": request.parameters,
        },
    )

    gateway = CapabilityGateway(
        capability_system=capability_system,
    )

    dispatcher = CognitiveToolDispatcher(
        gateway=gateway,
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="inspect_test",
                    description="Inspect test data.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "value": {
                                "type": "string",
                            },
                        },
                        "required": ["value"],
                    },
                ),
                capability_name="test.inspect",
            ),
        ),
    )

    return dispatcher


def test_tool_call_is_data_only():
    call = CognitiveToolCall(
        name="inspect_test",
        arguments={"value": "hello"},
        call_id="call-1",
    )

    assert call.name == "inspect_test"
    assert call.arguments == {"value": "hello"}
    assert call.call_id == "call-1"


def test_dispatcher_exposes_host_owned_tool_definitions():
    dispatcher = create_dispatcher()

    definitions = dispatcher.definitions

    assert len(definitions) == 1
    assert definitions[0].name == "inspect_test"


def test_dispatcher_converts_tool_call_to_capability_execution():
    dispatcher = create_dispatcher()

    result = dispatcher.dispatch(
        CognitiveToolCall(
            name="inspect_test",
            arguments={"value": "hello"},
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == {
        "received": {
            "value": "hello",
        },
    }


def test_dispatcher_rejects_unknown_tool():
    dispatcher = create_dispatcher()

    with pytest.raises(
        CognitiveToolError,
        match="Unknown cognitive tool",
    ):
        dispatcher.dispatch(
            CognitiveToolCall(
                name="unknown_tool",
                arguments={},
            )
        )


def test_cognitive_system_executes_tool_and_continues():
    dispatcher = create_dispatcher()

    class ToolCallingEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            self.requests.append(request)

            if len(self.requests) == 1:
                return CognitiveResponse(
                    content="",
                    tool_calls=(
                        CognitiveToolCall(
                            name="inspect_test",
                            arguments={
                                "value": "hello",
                            },
                            call_id="call-1",
                        ),
                    ),
                )

            assert request.messages[-1].role is CognitiveRole.TOOL
            assert "hello" in request.messages[-1].content

            return CognitiveResponse(
                content="Tool evidence received.",
            )

    engine = ToolCallingEngine()

    system = CognitiveSystem(
        engine=engine,
        tool_dispatcher=dispatcher,
    )

    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Inspect the test value.",
                        ),
                    ),
                ),
            ),
            authority=Authority(),
        )
    )

    assert response.content == "Tool evidence received."
    assert len(engine.requests) == 2


def test_cognitive_system_rejects_tool_loop_without_dispatcher():
    class ToolCallingEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="",
                tool_calls=(
                    CognitiveToolCall(
                        name="inspect_test",
                        arguments={},
                    ),
                ),
            )

    system = CognitiveSystem(
        engine=ToolCallingEngine(),
    )

    with pytest.raises(
        Exception,
        match="no CognitiveToolDispatcher",
    ):
        system.respond(
            CognitiveOperation(
                context=CognitiveContext(
                    request=CognitiveRequest(messages=()),
                ),
                authority=Authority(),
            )
        )


def test_cognitive_system_enforces_tool_round_limit():
    dispatcher = create_dispatcher()

    class InfiniteToolEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="",
                tool_calls=(
                    CognitiveToolCall(
                        name="inspect_test",
                        arguments={
                            "value": "loop",
                        },
                    ),
                ),
            )

    system = CognitiveSystem(
        engine=InfiniteToolEngine(),
        tool_dispatcher=dispatcher,
        max_tool_rounds=2,
    )

    with pytest.raises(
        Exception,
        match="maximum number of tool rounds",
    ):
        system.respond(
            CognitiveOperation(
                context=CognitiveContext(
                    request=CognitiveRequest(messages=()),
                ),
                authority=Authority(),
            )
        )


def test_tool_call_message_is_preserved_for_followup_provider_request():
    dispatcher = create_dispatcher()

    class RecordingEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            self.requests.append(request)

            if len(self.requests) == 1:
                return CognitiveResponse(
                    content="",
                    tool_calls=(
                        CognitiveToolCall(
                            name="inspect_test",
                            arguments={
                                "value": "hello",
                            },
                            call_id="call-42",
                        ),
                    ),
                )

            assistant_message = self.requests[-1].messages[-2]
            tool_message = self.requests[-1].messages[-1]

            assert assistant_message.role is CognitiveRole.ASSISTANT
            assert assistant_message.tool_calls[0].call_id == "call-42"
            assert tool_message.role is CognitiveRole.TOOL
            assert tool_message.tool_call_id == "call-42"

            return CognitiveResponse(
                content="done",
            )

    engine = RecordingEngine()

    system = CognitiveSystem(
        engine=engine,
        tool_dispatcher=dispatcher,
    )

    result = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(messages=()),
            ),
            authority=Authority(),
        )
    )

    assert result.content == "done"