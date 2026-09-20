"""Batch G5-G8: full-context, bounded, raw personality observations.

A passing offline test means prompts were assembled and observations retained,
NOT that an LLM consistently behaves as Sofía. Human review is separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import CognitiveResponse, CognitiveRole


@dataclass(frozen=True)
class PersonalityScenario:
    label: str
    context: CognitiveContext

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Scenario label must be nonempty.")
        if not isinstance(self.context, CognitiveContext):
            raise TypeError("Scenario context must be a CognitiveContext.")
        if self.context.personality is None:
            raise ValueError("Scenario must include an actual personality profile.")
        if not self.context.request.messages or (
            self.context.request.messages[-1].role is not CognitiveRole.USER
        ):
            raise ValueError("Scenario must end with a user message.")


@dataclass(frozen=True)
class PersonalityObservation:
    label: str
    request_sha256: str
    response: str | None
    elapsed_seconds: float
    error_type: str | None
    error_message: str | None


def observe_full_context(
    engine: CognitiveEngine,
    scenarios: tuple[PersonalityScenario, ...],
    *, max_cases: int,
) -> tuple[PersonalityObservation, ...]:
    """Run explicitly supplied scenarios; no model, memory, or network is created.

    The caller supplies full canonical context. A count limit is NOT a timeout.
    Errors and response text can be sensitive; never auto-persist or upload.
    """
    if not isinstance(engine, CognitiveEngine):
        raise TypeError("engine must be a CognitiveEngine.")
    if not isinstance(scenarios, tuple) or not scenarios:
        raise ValueError("scenarios must be a nonempty tuple.")
    if type(max_cases) is not int or max_cases <= 0 or len(scenarios) > max_cases:
        raise ValueError("Invalid max_cases or too many scenarios; no calls made.")
    if any(not isinstance(item, PersonalityScenario) for item in scenarios):
        raise TypeError("scenarios must contain PersonalityScenario instances.")
    if len({item.label for item in scenarios}) != len(scenarios):
        raise ValueError("Scenario labels must be unique.")
    assembler = CognitiveContextAssembler()
    observations: list[PersonalityObservation] = []
    for scenario in scenarios:
        request = assembler.assemble(scenario.context)
        serialized = "".join(
            f"{len(msg.role.value)}:{msg.role.value}{len(msg.content)}:{msg.content}"
            for msg in request.messages
        )
        digest = sha256(serialized.encode("utf-8")).hexdigest()
        start = perf_counter()
        response = None
        error_type = None
        error_message = None
        try:
            result = engine.respond(request)
            if not isinstance(result, CognitiveResponse):
                raise TypeError("Cognitive engine returned the wrong response type.")
            response = result.content
        except Exception as exc:
            error_type, error_message = type(exc).__name__, str(exc)
        observations.append(PersonalityObservation(
            scenario.label, digest, response, perf_counter() - start,
            error_type, error_message,
        ))
    return tuple(observations)
