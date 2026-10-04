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


def create_dispatcher(
    *,
    produces_execution_receipt: bool = False,
    execution_receipt_evidence_match=None,
):
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
                produces_execution_receipt=produces_execution_receipt,
                execution_receipt_evidence_match=(
                    execution_receipt_evidence_match
                ),
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


def test_dispatcher_filters_authorized_tools_by_matrix_relevance(tmp_path: Path):
    dispatcher = create_default_dispatcher(tmp_path)
    authority = Authority(
        can_inspect_filesystem=True,
        allowed_capabilities=("codebase.inspect",),
    )

    definitions = dispatcher.definitions_for_authority(
        authority,
        allowed_capabilities=("codebase.inspect",),
    )

    assert {item.name for item in definitions} == {"inspect_codebase"}


def test_dispatcher_rejects_authorized_but_unexposed_tool(tmp_path: Path):
    dispatcher = create_default_dispatcher(tmp_path)
    call = CognitiveToolCall(
        name="inspect_codebase",
        arguments={},
    )

    with pytest.raises(CognitiveToolError, match="not exposed"):
        dispatcher.dispatch(
            call,
            allowed_capabilities=("filesystem.inspect",),
        )


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
    assert response.evidence_refs == ("capability:test.inspect",)
    assert len(engine.requests) == 2


def test_cognitive_system_emits_execution_receipt_only_for_marked_tool():
    dispatcher = create_dispatcher(produces_execution_receipt=True)

    class ToolCallingEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            self.requests.append(request)
            if len(self.requests) == 1:
                return CognitiveResponse(
                    content="",
                    tool_calls=(
                        CognitiveToolCall(
                            name="inspect_test",
                            arguments={"value": "changed"},
                            call_id="execute-1",
                        ),
                    ),
                )
            return CognitiveResponse(content="Execution completed.")

    system = CognitiveSystem(
        engine=ToolCallingEngine(),
        tool_dispatcher=dispatcher,
    )
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Execute the approved test action.",
                        ),
                    ),
                ),
            ),
            authority=Authority(
                allowed_capabilities=("test.inspect",),
            ),
        )
    )

    assert response.evidence_refs == (
        "capability:test.inspect",
        "execution-receipt:test.inspect",
    )


def test_execution_receipt_evidence_match_blocks_unconfirmed_result():
    dispatcher = create_dispatcher(
        produces_execution_receipt=True,
        execution_receipt_evidence_match=(
            "received",
            {"value": "confirmed"},
        ),
    )

    unconfirmed = dispatcher.dispatch(
        CognitiveToolCall(
            name="inspect_test",
            arguments={"value": "unknown"},
        )
    )
    confirmed = dispatcher.dispatch(
        CognitiveToolCall(
            name="inspect_test",
            arguments={"value": "confirmed"},
        )
    )

    assert dispatcher.tool_result_produces_execution_receipt(
        "inspect_test",
        unconfirmed,
    ) is False
    assert dispatcher.tool_result_produces_execution_receipt(
        "inspect_test",
        confirmed,
    ) is True


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



def test_required_read_only_inspection_is_host_preflighted_before_model_answer():
    capability = Capability(
        name="process.inspect",
        description="Inspect local running processes. Read-only.",
    )
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )
    capability_system.register(
        capability=capability,
        handler=lambda request: {"processes": [{"name": "python.exe", "pid": 42}]},
    )
    dispatcher = CognitiveToolDispatcher(
        gateway=CapabilityGateway(capability_system=capability_system),
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="inspect_processes",
                    description="Inspect local running processes. Read-only.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
                capability_name="process.inspect",
            ),
        ),
    )

    class EvidenceFirstEngine(CognitiveEngine):
        def __init__(self):
            self.requests = []

        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            self.requests.append(request)
            assert any(
                message.role is CognitiveRole.TOOL
                and "python.exe" in message.content
                for message in request.messages
            )
            return CognitiveResponse(content="python.exe is running as PID 42.")

    engine = EvidenceFirstEngine()
    system = CognitiveSystem(engine=engine, tool_dispatcher=dispatcher)
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="TRUSTED READ-ONLY TOOL REQUIREMENT",
                        ),
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Inspect the local running processes.",
                        ),
                    ),
                    allow_tools=True,
                    capability_allowlist=("process.inspect",),
                    route_hint="deep",
                )
            ),
            authority=Authority(
                allowed_capabilities=("process.inspect",),
            ),
        )
    )

    assert response.content == "python.exe is running as PID 42."
    assert response.evidence_refs == ("capability:process.inspect",)
    assert len(engine.requests) == 1


def test_required_read_only_preflight_never_autocalls_parameterized_tool():
    capability = Capability(
        name="machine.get",
        description="Inspect one known machine.",
    )
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )
    called = []
    capability_system.register(
        capability=capability,
        handler=lambda request: called.append(request) or {},
    )
    dispatcher = CognitiveToolDispatcher(
        gateway=CapabilityGateway(capability_system=capability_system),
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="inspect_known_machine",
                    description="Inspect one known machine.",
                    parameters={
                        "type": "object",
                        "properties": {"machine_id": {"type": "string"}},
                        "required": ["machine_id"],
                        "additionalProperties": False,
                    },
                ),
                capability_name="machine.get",
            ),
        ),
    )

    class NoToolEngine(CognitiveEngine):
        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            return CognitiveResponse(content="No automatic call was possible.")

    system = CognitiveSystem(engine=NoToolEngine(), tool_dispatcher=dispatcher)
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="TRUSTED READ-ONLY TOOL REQUIREMENT",
                        ),
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Inspect a known machine.",
                        ),
                    ),
                    allow_tools=True,
                    capability_allowlist=("machine.get",),
                    route_hint="deep",
                )
            ),
            authority=Authority(
                allowed_capabilities=("machine.get",),
            ),
        )
    )

    assert response.content == "No automatic call was possible."
    assert called == []


def test_required_tool_preflight_executes_zero_argument_safe_autonomous_capability():
    capability = Capability(
        name="ops.fleet.discover",
        description="Discover Fleet candidates.",
    )
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )
    called = []
    capability_system.register(
        capability=capability,
        handler=lambda request: called.append(request) or {
            "candidates": [{"host_id": "candidate-a"}],
        },
    )
    dispatcher = CognitiveToolDispatcher(
        gateway=CapabilityGateway(capability_system=capability_system),
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="discover_fleet_candidates",
                    description="Discover Fleet candidates.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
                capability_name="ops.fleet.discover",
            ),
        ),
    )

    class EvidenceFirstEngine(CognitiveEngine):
        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            assert any(
                message.role is CognitiveRole.TOOL
                and "candidate-a" in message.content
                for message in request.messages
            )
            return CognitiveResponse(content="Found candidate-a.")

    system = CognitiveSystem(
        engine=EvidenceFirstEngine(),
        tool_dispatcher=dispatcher,
    )
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="TRUSTED TOOL EVIDENCE REQUIREMENT",
                        ),
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Discover Fleet candidates.",
                        ),
                    ),
                    allow_tools=True,
                    capability_allowlist=("ops.fleet.discover",),
                    route_hint="deep",
                )
            ),
            authority=Authority(
                allowed_capabilities=("ops.fleet.discover",),
            ),
        )
    )

    assert response.content == "Found candidate-a."
    assert response.evidence_refs == ("capability:ops.fleet.discover",)
    assert len(called) == 1


def test_required_tool_preflight_never_autocalls_protected_zero_argument_capability():
    capability = Capability(
        name="local.host.reboot",
        description="Reboot the local host.",
    )
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )
    called = []
    capability_system.register(
        capability=capability,
        handler=lambda request: called.append(request) or {"rebooted": True},
    )
    dispatcher = CognitiveToolDispatcher(
        gateway=CapabilityGateway(capability_system=capability_system),
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="reboot_local_host",
                    description="Reboot the local host.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
                capability_name="local.host.reboot",
            ),
        ),
    )

    class NoToolEngine(CognitiveEngine):
        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            assert not any(
                message.role is CognitiveRole.TOOL
                for message in request.messages
            )
            return CognitiveResponse(content="No automatic reboot.")

    system = CognitiveSystem(
        engine=NoToolEngine(),
        tool_dispatcher=dispatcher,
    )
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="TRUSTED TOOL EVIDENCE REQUIREMENT",
                        ),
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Reboot this host.",
                        ),
                    ),
                    allow_tools=True,
                    capability_allowlist=("local.host.reboot",),
                    route_hint="deep",
                )
            ),
            authority=Authority(
                allowed_capabilities=("local.host.reboot",),
            ),
        )
    )

    assert response.content == "No automatic reboot."
    assert called == []


def test_required_read_only_preflight_dispatches_all_zero_argument_reads():
    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )
    for capability, payload in (
        (
            Capability(
                name="system.inspect",
                description="Inspect the local system.",
            ),
            {"host": "Venus"},
        ),
        (
            Capability(
                name="machine.list",
                description="List known machines.",
            ),
            {"machines": ["Venus", "Artemis"]},
        ),
    ):
        capability_system.register(
            capability=capability,
            handler=lambda request, value=payload: value,
        )

    dispatcher = CognitiveToolDispatcher(
        gateway=CapabilityGateway(
            capability_system=capability_system
        ),
        bindings=(
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="inspect_system",
                    description="Inspect the local system.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
                capability_name="system.inspect",
            ),
            CognitiveToolBinding(
                definition=CognitiveToolDefinition(
                    name="list_known_machines",
                    description="List known machines.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
                capability_name="machine.list",
            ),
        ),
    )

    class MultiEvidenceEngine(CognitiveEngine):
        def respond(self, request: CognitiveRequest) -> CognitiveResponse:
            tool_messages = tuple(
                message
                for message in request.messages
                if message.role is CognitiveRole.TOOL
            )
            assert len(tool_messages) == 2
            combined = "\n".join(
                message.content for message in tool_messages
            )
            assert "Venus" in combined
            assert "Artemis" in combined
            return CognitiveResponse(
                content="I have both local-system and known-machine evidence."
            )

    system = CognitiveSystem(
        engine=MultiEvidenceEngine(),
        tool_dispatcher=dispatcher,
    )
    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="TRUSTED READ-ONLY TOOL REQUIREMENT",
                        ),
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content=(
                                "What computer are you on, and what other "
                                "computers can you already see?"
                            ),
                        ),
                    ),
                    allow_tools=True,
                    capability_allowlist=(
                        "system.inspect",
                        "machine.list",
                    ),
                    route_hint="deep",
                )
            ),
            authority=Authority(
                allowed_capabilities=(
                    "system.inspect",
                    "machine.list",
                ),
            ),
        )
    )

    assert response.evidence_refs == (
        "capability:system.inspect",
        "capability:machine.list",
    )
