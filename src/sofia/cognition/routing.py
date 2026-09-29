from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import perf_counter

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

        text = self._latest_user_text(request)
        normalized = text.casefold()
        word_count = len(text.split())

        if any(marker in normalized for marker in self._VERIFY_MARKERS):
            return RoutingDecision(
                route=CognitiveRoute.VERIFY,
                score=10,
                reason="explicit verification request",
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

    def __init__(
        self,
        registry: CognitiveEngineRegistry,
        *,
        policy: CognitiveRoutingPolicy | None = None,
        verify_enabled: bool = True,
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

        self.registry = registry
        self.policy = policy or CognitiveRoutingPolicy()
        self.verify_enabled = verify_enabled
        self.last_decision: RoutingDecision | None = None

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        decision = self.policy.decide(request)
        self.last_decision = decision
        started = perf_counter()
        fallback_count = 0
        verification_passes = 0

        try:
            if decision.route is CognitiveRoute.VERIFY and self.verify_enabled:
                response, fallback_count, verification_passes = (
                    self._verified_response(request)
                )
            elif decision.route in {
                CognitiveRoute.FAST,
                CognitiveRoute.OPEN,
            }:
                response, fallback_count = self._respond_with_fallback(
                    preferred=self.registry.secondary,
                    fallback=self.registry.primary,
                    request=request,
                )
            else:
                response, fallback_count = self._respond_with_fallback(
                    preferred=self.registry.primary,
                    fallback=self.registry.secondary,
                    request=request,
                )
            return response
        finally:
            emit_performance(
                "router",
                elapsed_ms=(perf_counter() - started) * 1000,
                route_code=self._ROUTE_CODES[decision.route],
                routing_score=max(decision.score, 0),
                fallback_count=fallback_count,
                verification_passes=verification_passes,
            )

    @staticmethod
    def _respond_with_fallback(
        *,
        preferred: CognitiveEngine,
        fallback: CognitiveEngine,
        request: CognitiveRequest,
    ) -> tuple[CognitiveResponse, int]:
        try:
            return preferred.respond(request), 0
        except CognitiveEngineError as preferred_error:
            try:
                return fallback.respond(request), 1
            except CognitiveEngineError as fallback_error:
                raise fallback_error from preferred_error

    def _verified_response(
        self,
        request: CognitiveRequest,
    ) -> tuple[CognitiveResponse, int, int]:
        fallback_count = 0

        try:
            primary_response = self.registry.primary.respond(request)
        except CognitiveEngineError as primary_error:
            try:
                secondary_response = self.registry.secondary.respond(request)
            except CognitiveEngineError as secondary_error:
                raise secondary_error from primary_error
            return secondary_response, 1, 0

        # Tool requests must return to the host authority/capability layer.
        # A second model must never independently approve or duplicate them.
        if primary_response.tool_calls:
            return primary_response, fallback_count, 0

        critique_request = self._build_critique_request(
            request,
            primary_response,
        )
        try:
            critique = self.registry.secondary.respond(critique_request)
        except CognitiveEngineError:
            return primary_response, fallback_count + 1, 0

        synthesis_request = self._build_synthesis_request(
            request,
            primary_response,
            critique,
        )
        try:
            final_response = self.registry.primary.respond(synthesis_request)
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
