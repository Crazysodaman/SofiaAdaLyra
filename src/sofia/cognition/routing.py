from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter

from sofia.cognition.activity import CognitiveModelActivityStore
from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.performance import emit_performance


class CognitiveRoute(Enum):
    """Logical cognitive modes, independent of concrete model names."""

    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    OPEN = "open"
    VERIFY = "verify"


@dataclass(frozen=True)
class RoutingDecision:
    route: CognitiveRoute
    score: int
    reason: str


@dataclass(frozen=True)
class RoutingExecutionStep:
    role: str
    model: str | None
    host: str | None
    succeeded: bool


@dataclass(frozen=True)
class RoutingExecution:
    serial: int
    route: CognitiveRoute
    steps: tuple[RoutingExecutionStep, ...]
    fallback_count: int
    verification_passes: int

    @property
    def successful_steps(self) -> tuple[RoutingExecutionStep, ...]:
        return tuple(step for step in self.steps if step.succeeded)

    @property
    def last_successful_step(self) -> RoutingExecutionStep | None:
        values = self.successful_steps
        return values[-1] if values else None


class CognitiveEngineRegistry:
    """Small role registry for interchangeable cognitive engines."""

    def __init__(
        self,
        *,
        primary: CognitiveEngine,
        secondary: CognitiveEngine,
    ) -> None:
        if not isinstance(primary, CognitiveEngine):
            raise TypeError("primary must be a CognitiveEngine")
        if not isinstance(secondary, CognitiveEngine):
            raise TypeError("secondary must be a CognitiveEngine")
        self._engines = {
            "primary": primary,
            "secondary": secondary,
        }

    @property
    def primary(self) -> CognitiveEngine:
        return self._engines["primary"]

    @property
    def secondary(self) -> CognitiveEngine:
        return self._engines["secondary"]

    def get(self, role: str) -> CognitiveEngine:
        try:
            return self._engines[role]
        except KeyError as exc:
            raise KeyError(f"Unknown cognitive engine role: {role}") from exc


class CognitiveRoutingPolicy:
    """Deterministic first-pass routing policy.

    The router chooses an inference engine only. Identity, authority,
    capabilities, memory, and action permission remain outside this layer.
    """

    _VERIFY_MARKERS = (
        "verify",
        "double check",
        "double-check",
        "confirm this",
        "are you sure",
        "check your answer",
    )
    _OPEN_MARKERS = (
        "open mode",
        "use open model",
        "use the open model",
        "uncensored model",
        "secondary model",
    )
    _INTERACTION_CONTEXT_MARKERS = (
        "TRUSTED INTERACTION INTERPRETATION",
        "TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION",
        "TRUSTED INTERACTION FOLLOW-UP",
        "TRUSTED BODY INTERACTION CONTROL",
        "TRUSTED REPRESENTATIONAL EXPERIENCE FOLLOW-UP",
        "TRUSTED REPRESENTATIONAL PRESENTATION REQUEST",
    )
    _HIGH_IMPACT_MARKERS = (
        "delete",
        "remove",
        "restart",
        "reboot",
        "shutdown",
        "migrate",
        "deploy",
        "update",
        "upgrade",
        "install",
        "uninstall",
        "execute",
        "run this",
        "write to",
        "modify",
    )
    _TECHNICAL_MARKERS = (
        "python",
        "powershell",
        "linux",
        "windows",
        "docker",
        "github",
        "pytest",
        "traceback",
        "exception",
        "error",
        "function",
        "class ",
        "database",
        "sqlite",
        "network",
        "service",
        "process",
        "hardware",
        "fleet",
        "home assistant",
        "api",
        "json",
        "yaml",
        "code",
        "debug",
        "architecture",
    )

    def decide(self, request: CognitiveRequest) -> RoutingDecision:
        if not isinstance(request, CognitiveRequest):
            raise TypeError("request must be a CognitiveRequest")

        if request.route_hint is not None:
            route = CognitiveRoute(request.route_hint)
            return RoutingDecision(
                route=route,
                score=10,
                reason=f"matrix route hint: {request.route_hint}",
            )

        text = self._latest_user_text(request)
        normalized = text.casefold()
        word_count = len(text.split())

        if any(marker in normalized for marker in self._VERIFY_MARKERS):
            return RoutingDecision(
                route=CognitiveRoute.VERIFY,
                score=10,
                reason="explicit verification request",
            )

        if any(
            message.role is CognitiveRole.SYSTEM
            and any(
                marker in message.content
                for marker in self._INTERACTION_CONTEXT_MARKERS
            )
            for message in request.messages
        ):
            return RoutingDecision(
                route=CognitiveRoute.STANDARD,
                score=4,
                reason="reviewed represented-interaction context",
            )

        if (
            request.tools
            and any(
                marker in normalized
                for marker in self._HIGH_IMPACT_MARKERS
            )
        ):
            return RoutingDecision(
                route=CognitiveRoute.VERIFY,
                score=9,
                reason="high-impact tool-oriented request",
            )

        if (
            not request.tools
            and any(marker in normalized for marker in self._OPEN_MARKERS)
        ):
            return RoutingDecision(
                route=CognitiveRoute.OPEN,
                score=0,
                reason="explicit open-model request",
            )

        score = 0
        if request.tools:
            score += 5
        if chr(96) * 3 in text:
            score += 3
        if len(text) >= 600:
            score += 3
        elif len(text) >= 280:
            score += 1

        technical_hits = sum(
            1
            for marker in self._TECHNICAL_MARKERS
            if marker in normalized
        )
        score += min(technical_hits, 4)

        if score >= 5:
            return RoutingDecision(
                route=CognitiveRoute.DEEP,
                score=score,
                reason="technical or tool-heavy request",
            )

        if not request.tools and word_count <= 30 and score == 0:
            return RoutingDecision(
                route=CognitiveRoute.FAST,
                score=score,
                reason="short low-complexity conversation",
            )

        return RoutingDecision(
            route=CognitiveRoute.STANDARD,
            score=score,
            reason="normal conversation",
        )

    @staticmethod
    def _latest_user_text(request: CognitiveRequest) -> str:
        for message in reversed(request.messages):
            if message.role is CognitiveRole.USER:
                return message.content
        return ""


class RoutingCognitiveEngine(CognitiveEngine):
    """Route one canonical cognitive request across interchangeable engines."""

    _ROUTE_CODES = {
        CognitiveRoute.FAST: 1,
        CognitiveRoute.STANDARD: 2,
        CognitiveRoute.DEEP: 3,
        CognitiveRoute.OPEN: 4,
        CognitiveRoute.VERIFY: 5,
    }
    _REPLAY_SAFE_TOOL_VERBS = frozenset({
        "catalog", "check", "find", "get", "inspect", "list", "query",
        "read", "search", "show", "status",
    })

    def __init__(
        self,
        registry: CognitiveEngineRegistry,
        *,
        policy: CognitiveRoutingPolicy | None = None,
        verify_enabled: bool = True,
        activity_store: CognitiveModelActivityStore | None = None,
    ) -> None:
        if not isinstance(registry, CognitiveEngineRegistry):
            raise TypeError("registry must be a CognitiveEngineRegistry")
        if policy is not None and not isinstance(
            policy,
            CognitiveRoutingPolicy,
        ):
            raise TypeError("policy must be a CognitiveRoutingPolicy or None")
        if type(verify_enabled) is not bool:
            raise TypeError("verify_enabled must be a bool")
        if (
            activity_store is not None
            and not isinstance(activity_store, CognitiveModelActivityStore)
        ):
            raise TypeError(
                "activity_store must be CognitiveModelActivityStore or None"
            )

        self.registry = registry
        self.policy = policy or CognitiveRoutingPolicy()
        self.verify_enabled = verify_enabled
        self.activity_store = activity_store
        self.last_decision: RoutingDecision | None = None
        self.last_execution: RoutingExecution | None = None
        self._execution_serial = 0

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        decision = self.policy.decide(request)
        self.last_decision = decision
        started = perf_counter()
        fallback_count = 0
        verification_passes = 0
        steps: list[RoutingExecutionStep] = []
        tool_fallback_used = False
        try:
            # Only a conservatively recognized read-only tool surface may be
            # replayed on the secondary. Mutating/unknown tools stay on one
            # engine because a failure can occur after an action was requested
            # or executed, making whole-turn retry unsafe.
            if request.tools:
                try:
                    primary_response = self._invoke(
                        "primary",
                        request,
                        steps,
                    )
                except CognitiveEngineError:
                    if not self._tool_request_is_replay_safe(request):
                        raise
                    fallback_count += 1
                    tool_fallback_used = True
                    primary_response = self._invoke(
                        "secondary",
                        request,
                        steps,
                    )
                if (
                    decision.route is CognitiveRoute.VERIFY
                    and self.verify_enabled
                    and not primary_response.tool_calls
                    and not tool_fallback_used
                ):
                    response, fallback_count, verification_passes = (
                        self._review_existing_response(
                            request,
                            primary_response,
                            steps=steps,
                        )
                    )
                    return response
                return primary_response

            if decision.route is CognitiveRoute.VERIFY and self.verify_enabled:
                response, fallback_count, verification_passes = (
                    self._verified_response(
                        request,
                        steps=steps,
                    )
                )
            elif decision.route in {
                CognitiveRoute.FAST,
                CognitiveRoute.OPEN,
            }:
                response, fallback_count = self._respond_with_fallback(
                    preferred_role="secondary",
                    fallback_role="primary",
                    request=request,
                    steps=steps,
                )
            else:
                response, fallback_count = self._respond_with_fallback(
                    preferred_role="primary",
                    fallback_role="secondary",
                    request=request,
                    steps=steps,
                )
            return response
        finally:
            self._execution_serial += 1
            self.last_execution = RoutingExecution(
                serial=self._execution_serial,
                route=decision.route,
                steps=tuple(steps),
                fallback_count=fallback_count,
                verification_passes=verification_passes,
            )

            emit_performance(
                "router",
                elapsed_ms=(perf_counter() - started) * 1000,
                route_code=self._ROUTE_CODES[decision.route],
                routing_score=max(decision.score, 0),
                fallback_count=fallback_count,
                verification_passes=verification_passes,
            )

    @classmethod
    def _tool_request_is_replay_safe(cls, request: CognitiveRequest) -> bool:
        """Allow engine fallback only for visibly read-only tool definitions."""
        if not request.tools:
            return False
        for tool in request.tools:
            name = tool.name.casefold().replace(".", "_")
            verb = name.split("_", 1)[0]
            if verb not in cls._REPLAY_SAFE_TOOL_VERBS:
                return False
        return True

    @staticmethod
    def _engine_model(engine: CognitiveEngine) -> str | None:
        configuration = getattr(engine, "configuration", None)
        model = getattr(configuration, "model", None)
        if isinstance(model, str) and model.strip():
            return model
        provider = getattr(engine, "provider", None)
        model = getattr(provider, "model", None)
        if isinstance(model, str) and model.strip():
            return model
        local = getattr(engine, "local", None)
        if isinstance(local, CognitiveEngine):
            return RoutingCognitiveEngine._engine_model(local)
        return None

    @staticmethod
    def _engine_host(engine: CognitiveEngine) -> str | None:
        host = getattr(engine, "last_host_id", None)
        if isinstance(host, str) and host.strip():
            return host
        local = getattr(engine, "local", None)
        if isinstance(local, CognitiveEngine):
            return RoutingCognitiveEngine._engine_host(local)
        return None

    def _invoke(
        self,
        role: str,
        request: CognitiveRequest,
        steps: list[RoutingExecutionStep],
    ) -> CognitiveResponse:
        engine = self.registry.get(role)
        model = self._engine_model(engine)
        if self.activity_store is not None and model is not None:
            self.activity_store.mark_busy(
                role=role,
                model=model,
            )
        try:
            response = engine.respond(request)
        except CognitiveEngineError:
            host = self._engine_host(engine)
            if self.activity_store is not None and model is not None:
                self.activity_store.mark_finished(
                    role=role,
                    model=model,
                    host=host,
                    succeeded=False,
                )
            steps.append(
                RoutingExecutionStep(
                    role=role,
                    model=model,
                    host=host,
                    succeeded=False,
                )
            )
            raise
        host = self._engine_host(engine)
        if self.activity_store is not None and model is not None:
            self.activity_store.mark_finished(
                role=role,
                model=model,
                host=host,
                succeeded=True,
            )
        steps.append(
            RoutingExecutionStep(
                role=role,
                model=model,
                host=host,
                succeeded=True,
            )
        )
        return response

    def _respond_with_fallback(
        self,
        *,
        preferred_role: str,
        fallback_role: str,
        request: CognitiveRequest,
        steps: list[RoutingExecutionStep],
    ) -> tuple[CognitiveResponse, int]:
        try:
            response = self._invoke(preferred_role, request, steps)
            if not response.tool_calls and len(response.content.strip()) <= 1:
                raise CognitiveEngineError(
                    "preferred cognitive engine returned an incomplete response"
                )
            return response, 0
        except CognitiveEngineError as preferred_error:
            try:
                return self._invoke(fallback_role, request, steps), 1
            except CognitiveEngineError as fallback_error:
                raise fallback_error from preferred_error

    def _verified_response(
        self,
        request: CognitiveRequest,
        *,
        steps: list[RoutingExecutionStep],
    ) -> tuple[CognitiveResponse, int, int]:
        fallback_count = 0

        try:
            primary_response = self._invoke("primary", request, steps)
        except CognitiveEngineError as primary_error:
            try:
                secondary_response = self._invoke(
                    "secondary",
                    request,
                    steps,
                )
            except CognitiveEngineError as secondary_error:
                raise secondary_error from primary_error
            return secondary_response, 1, 0

        # Tool requests must return to the host authority/capability layer.
        # A second model must never independently approve or duplicate them.
        if primary_response.tool_calls:
            return primary_response, fallback_count, 0

        return self._review_existing_response(
            request,
            primary_response,
            fallback_count=fallback_count,
            steps=steps,
        )

    def _review_existing_response(
        self,
        request: CognitiveRequest,
        primary_response: CognitiveResponse,
        *,
        fallback_count: int = 0,
        steps: list[RoutingExecutionStep],
    ) -> tuple[CognitiveResponse, int, int]:
        critique_request = self._build_critique_request(
            request,
            primary_response,
        )
        try:
            critique = self._invoke(
                "secondary",
                critique_request,
                steps,
            )
        except CognitiveEngineError:
            return primary_response, fallback_count + 1, 0

        synthesis_request = self._build_synthesis_request(
            request,
            primary_response,
            critique,
        )
        try:
            final_response = self._invoke(
                "primary",
                synthesis_request,
                steps,
            )
        except CognitiveEngineError:
            return primary_response, fallback_count + 1, 1

        return final_response, fallback_count, 2

    @staticmethod
    def _build_critique_request(
        request: CognitiveRequest,
        response: CognitiveResponse,
    ) -> CognitiveRequest:
        messages = (
            *request.messages,
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content=response.content,
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "Review the immediately preceding assistant answer. "
                    "Check factual consistency, logic, unsupported claims, "
                    "missed constraints, and contradictions with the supplied "
                    "system context. Do not execute or request tools. Return "
                    "a concise critique for another model to use."
                ),
            ),
        )
        return CognitiveRequest(
            messages=messages,
            tools=(),
            allow_tools=False,
        )

    @staticmethod
    def _build_synthesis_request(
        request: CognitiveRequest,
        response: CognitiveResponse,
        critique: CognitiveResponse,
    ) -> CognitiveRequest:
        messages = (
            *request.messages,
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content=response.content,
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "A secondary cognitive engine reviewed the previous "
                    "answer. Use the critique only as review evidence, not "
                    "as authority. Produce the final answer using the "
                    "original system context and user request.\n\n"
                    f"Reviewer critique:\n{critique.content}"
                ),
            ),
        )
        return CognitiveRequest(
            messages=messages,
            tools=(),
            allow_tools=False,
        )
