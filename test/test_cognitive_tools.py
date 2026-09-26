from pathlib import Path

import pytest

from sofia.authority.model import Authority
from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import (
    Capability,
    CapabilityResultKind,
)
from sofia.capability.system import CapabilitySystem
from sofia.cognition.context import CognitiveContext
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.tools import (
    CognitiveToolBinding,
    CognitiveToolDispatcher,
    CognitiveToolError,
)


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


def create_default_dispatcher(tmp_path: Path):
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    gateway = CapabilityGateway(
        capability_system=capability_system,
    )

    from sofia.cognition.tools import create_default_tool_bindings

    return CognitiveToolDispatcher(
        gateway=gateway,
        bindings=create_default_tool_bindings(tmp_path),
    )


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


def test_dispatcher_filters_unauthorized_capabilities():
    dispatcher = create_dispatcher()

    definitions = dispatcher.definitions_for_authority(
        Authority()
    )

    assert definitions == ()


def test_dispatcher_exposes_explicitly_authorized_capability():
    dispatcher = create_dispatcher()

    definitions = dispatcher.definitions_for_authority(
        Authority(
            allowed_capabilities=("test.inspect",),
        )
    )

    assert len(definitions) == 1
    assert definitions[0].name == "inspect_test"


def test_default_filesystem_tools_are_hidden_without_authority(
    tmp_path: Path,
):
    dispatcher = create_default_dispatcher(tmp_path)

    definitions = dispatcher.definitions_for_authority(
        Authority()
    )

    assert definitions == ()


def test_default_filesystem_tools_are_exposed_with_filesystem_authority(
    tmp_path: Path,
):
    dispatcher = create_default_dispatcher(tmp_path)

    definitions = dispatcher.definitions_for_authority(
        Authority(
            can_inspect_filesystem=True,
        )
    )

    assert {
        definition.name
        for definition in definitions
    } == {
        "inspect_file",
        "inspect_directory",
        "search_code",
    }


def test_codebase_tool_is_not_exposed_by_filesystem_authority(
    tmp_path: Path,
):
    dispatcher = create_default_dispatcher(tmp_path)

    definitions = dispatcher.definitions_for_authority(
        Authority(
            can_inspect_filesystem=True,
        )
    )

    assert "inspect_codebase" not in {
        definition.name
        for definition in definitions
    }


def test_codebase_tool_requires_explicit_capability_authority(
    tmp_path: Path,
):
    dispatcher = create_default_dispatcher(tmp_path)

    definitions = dispatcher.definitions_for_authority(
        Authority(
            allowed_capabilities=("codebase.inspect",),
        )
    )

    assert {
        definition.name
        for definition in definitions
    } == {
        "inspect_codebase",
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


def test_cognitive_system_executes_authorized_tool_and_continues():
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
                assert [
                    tool.name
                    for tool in request.tools
                ] == ["inspect_test"]

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
            context=__import__(
                "sofia.cognition.context",
                fromlist=["CognitiveContext"],
            ).CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Inspect the test value.",
                        ),
                    ),
                ),
            ),
            authority=Authority(
                allowed_capabilities=("test.inspect",),
            ),
        )
    )

    assert response.content == "Tool evidence received."
    assert len(engine.requests) == 2


def test_cognitive_system_does_not_expose_unauthorized_tool():
    dispatcher = create_dispatcher()

    class RecordingEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            self.requests.append(request)

            return CognitiveResponse(
                content="No tool exposed.",
            )

    engine = RecordingEngine()

    system = CognitiveSystem(
        engine=engine,
        tool_dispatcher=dispatcher,
    )

    response = system.respond(
        CognitiveOperation(
            context=__import__(
                "sofia.cognition.context",
                fromlist=["CognitiveContext"],
            ).CognitiveContext(
                request=CognitiveRequest(messages=()),
            ),
            authority=Authority(),
        )
    )

    assert response.content == "No tool exposed."
    assert engine.requests[0].tools == ()


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
                context=__import__(
                    "sofia.cognition.context",
                    fromlist=["CognitiveContext"],
                ).CognitiveContext(
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
                context=__import__(
                    "sofia.cognition.context",
                    fromlist=["CognitiveContext"],
                ).CognitiveContext(
                    request=CognitiveRequest(messages=()),
                ),
                authority=Authority(
                    allowed_capabilities=("test.inspect",),
                ),
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
            context=__import__(
                "sofia.cognition.context",
                fromlist=["CognitiveContext"],
            ).CognitiveContext(
                request=CognitiveRequest(messages=()),
            ),
            authority=Authority(
                allowed_capabilities=("test.inspect",),
            ),
        )
    )

    assert result.content == "done"

def test_cognitive_system_respects_explicit_tool_suppression():
    dispatcher = create_dispatcher()

    class RecordingEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            self.requests.append(request)
            return CognitiveResponse(
                content="Tool-free response.",
            )

    engine = RecordingEngine()
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
                            content="Respond without tools.",
                        ),
                    ),
                    allow_tools=False,
                ),
            ),
            authority=Authority(
                allowed_capabilities=("test.inspect",),
            ),
        )
    )

    assert response.content == "Tool-free response."
    assert engine.requests[0].tools == ()
    assert engine.requests[0].allow_tools is False
