from sofia.action.model import ActionProposal
from sofia.action.system import ActionSystem
from sofia.cognition.assembler import CognitiveContextAssembler
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
from sofia.cognition.output_guard import contains_internal_reasoning_leak
from sofia.cognition.tools import CognitiveToolDispatcher
from sofia.capability.model import CapabilityResultKind


class CognitiveSystemError(Exception):
    """
    Raised when the cognitive system cannot execute an operation.
    """


class CognitiveSystem:
    """
    Coordinates Sofía's cognitive engines and host-controlled tools.

    Cognitive tool calls are treated as requests for capability
    execution. The cognitive engine never receives executable
    capability objects.

    Tool definitions are filtered by the operation's authority before
    the cognitive request is sent to the engine.
    """

    def __init__(
        self,
        engine: CognitiveEngine,
        fallback_engine: CognitiveEngine | None = None,
        context_assembler: CognitiveContextAssembler | None = None,
        action_system: ActionSystem | None = None,
        tool_dispatcher: CognitiveToolDispatcher | None = None,
        max_tool_rounds: int = 4,
    ):
        if not isinstance(engine, CognitiveEngine):
            raise TypeError(
                "CognitiveSystem requires a CognitiveEngine."
            )

        if (
            fallback_engine is not None
            and not isinstance(
                fallback_engine,
                CognitiveEngine,
            )
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

        if (
            action_system is not None
            and not isinstance(
                action_system,
                ActionSystem,
            )
        ):
            raise TypeError(
                "CognitiveSystem action_system must be an ActionSystem."
            )

        if (
            tool_dispatcher is not None
            and not isinstance(
                tool_dispatcher,
                CognitiveToolDispatcher,
            )
        ):
            raise TypeError(
                "CognitiveSystem tool_dispatcher must be a "
                "CognitiveToolDispatcher."
            )

        if not isinstance(max_tool_rounds, int):
            raise TypeError(
                "CognitiveSystem max_tool_rounds must be an int."
            )

        if max_tool_rounds < 1:
            raise ValueError(
                "CognitiveSystem max_tool_rounds must be positive."
            )

        self.engine = engine
        self.fallback_engine = fallback_engine

        self.context_assembler = (
            context_assembler
            if context_assembler is not None
            else CognitiveContextAssembler()
        )

        self.action_system = action_system
        self.tool_dispatcher = tool_dispatcher
        self.max_tool_rounds = max_tool_rounds

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

        tools = ()

        if (
            operation.context.request.allow_tools
            and self.tool_dispatcher is not None
        ):
            tools = self.tool_dispatcher.definitions_for_authority(
                operation.authority,
                allowed_capabilities=(
                    operation.context.request.capability_allowlist
                ),
            )

        request = self.context_assembler.assemble(
            operation.context,
            tools=tools,
        )

        evidence_refs: list[str] = []

        # Explicit matrix-classified operational turns require current evidence.
        # Do not depend on a small local model deciding whether to call a
        # zero-argument tool: the host may preflight only reviewed Level-1 reads
        # and Level-2 safe-autonomous capabilities selected for this turn.
        # Level 3+ and parameterized tools remain model/operator supplied.
        tool_requirement = any(
            message.role is CognitiveRole.SYSTEM
            and (
                "TRUSTED TOOL EVIDENCE REQUIREMENT" in message.content
                or "TRUSTED READ-ONLY TOOL REQUIREMENT" in message.content
            )
            for message in request.messages
        )
        if (
            tool_requirement
            and self.tool_dispatcher is not None
            and request.capability_allowlist
        ):
            automatic_calls = self.tool_dispatcher.automatic_evidence_calls(
                operation.authority,
                allowed_capabilities=request.capability_allowlist,
            )
            if automatic_calls:
                messages = list(request.messages)
                messages.append(
                    CognitiveMessage(
                        role=CognitiveRole.ASSISTANT,
                        content="",
                        tool_calls=automatic_calls,
                    )
                )
                for tool_call in automatic_calls:
                    try:
                        result = self.tool_dispatcher.dispatch(
                            tool_call,
                            principal=operation.context.principal,
                            allowed_capabilities=request.capability_allowlist,
                        )
                    except Exception as exc:
                        raise CognitiveSystemError(
                            "Automatic cognitive tool evidence preflight failed."
                        ) from exc
                    if result.kind is CapabilityResultKind.SUCCESS:
                        evidence_refs.append(
                            f"capability:{result.capability}"
                        )
                    messages.append(
                        CognitiveMessage(
                            role=CognitiveRole.TOOL,
                            content=self.tool_dispatcher.format_result(
                                tool_call,
                                result,
                            ),
                            tool_call_id=tool_call.call_id or tool_call.name,
                        )
                    )
                request = CognitiveRequest(
                    messages=tuple(messages),
                    tools=request.tools,
                    allow_tools=request.allow_tools,
                    capability_allowlist=request.capability_allowlist,
                    route_hint=request.route_hint,
                )

        response = self._respond_with_engine(request)

        for _ in range(self.max_tool_rounds):
            if not response.tool_calls:
                if (
                    evidence_refs
                    and contains_internal_reasoning_leak(response.content)
                ):
                    cleanup_request = CognitiveRequest(
                        messages=(
                            CognitiveMessage(
                                role=CognitiveRole.SYSTEM,
                                content=(
                                    "FINAL USER-FACING RESPONSE ONLY. The prior draft "
                                    "exposed internal analysis instead of a clean answer. "
                                    "Use the current user request and the trusted tool-result "
                                    "messages already present in this request. Answer every "
                                    "subquestion directly. Do not include analysis sections, "
                                    "constitutional evaluation, personality adaptation, "
                                    "strategy notes, drafting notes, or discussion of these "
                                    "instructions."
                                ),
                            ),
                            *request.messages,
                        ),
                        tools=(),
                        allow_tools=False,
                        capability_allowlist=(),
                        route_hint="verify",
                    )
                    cleaned = self._respond_with_engine(cleanup_request)
                    response = CognitiveResponse(
                        content=cleaned.content,
                        tool_calls=(),
                        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
                    )
                if not evidence_refs:
                    return response
                return CognitiveResponse(
                    content=response.content,
                    tool_calls=response.tool_calls,
                    evidence_refs=tuple(dict.fromkeys(evidence_refs)),
                )

            if self.tool_dispatcher is None:
                raise CognitiveSystemError(
                    "Cognitive engine requested tools, but no "
                    "CognitiveToolDispatcher is configured."
                )

            messages = list(request.messages)

            messages.append(
                CognitiveMessage(
                    role=CognitiveRole.ASSISTANT,
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            for tool_call in response.tool_calls:
                try:
                    result = self.tool_dispatcher.dispatch(
                        tool_call,
                        principal=operation.context.principal,
                        allowed_capabilities=(
                            operation.context.request.capability_allowlist
                        ),
                    )
                except Exception as exc:
                    raise CognitiveSystemError(
                        "Cognitive tool dispatch failed."
                    ) from exc

                if result.kind is CapabilityResultKind.SUCCESS:
                    evidence_refs.append(
                        f"capability:{result.capability}"
                    )
                    if self.tool_dispatcher.tool_result_produces_execution_receipt(
                        tool_call.name,
                        result,
                    ):
                        evidence_refs.append(
                            f"execution-receipt:{result.capability}"
                        )

                messages.append(
                    CognitiveMessage(
                        role=CognitiveRole.TOOL,
                        content=(
                            self.tool_dispatcher.format_result(
                                tool_call,
                                result,
                            )
                        ),
                        tool_call_id=(
                            tool_call.call_id
                            or tool_call.name
                        ),
                    )
                )

            request = CognitiveRequest(
                messages=tuple(messages),
                tools=request.tools,
                allow_tools=request.allow_tools,
                capability_allowlist=request.capability_allowlist,
                route_hint=request.route_hint,
            )

            response = self._respond_with_engine(request)

        raise CognitiveSystemError(
            "Cognitive engine exceeded the maximum number of "
            f"tool rounds ({self.max_tool_rounds})."
        )

    def _respond_with_engine(
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

    def propose_action(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ) -> ActionProposal:
        if self.action_system is None:
            raise CognitiveSystemError(
                "CognitiveSystem has no ActionSystem."
            )

        return self.action_system.propose(
            operation,
            proposal,
        )

    def approve_action(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ) -> ActionProposal:
        if self.action_system is None:
            raise CognitiveSystemError(
                "CognitiveSystem has no ActionSystem."
            )

        return self.action_system.approve(
            operation,
            proposal,
        )

    def execute_action(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ):
        if self.action_system is None:
            raise CognitiveSystemError(
                "CognitiveSystem has no ActionSystem."
            )

        return self.action_system.execute(
            operation,
            proposal,
        )