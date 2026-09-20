"""Batch G4: explicit, bounded-case personality observation harness.

This harness preserves raw responses and errors. It does not grade, alter,
post-process, approve, or guarantee a language model's personality fidelity.
Calling it with a live engine may block for the provider's configured duration;
max_cases limits count, NOT wall-clock time. No live engine is created here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.personality.model import PersonalityProfile


@dataclass(frozen=True)
class PersonalityProbeCase:
    label: str
    user_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Probe case label must be a nonempty string.")
        if not isinstance(self.user_text, str) or not self.user_text.strip():
            raise ValueError("Probe case user_text must be a nonempty string.")


@dataclass(frozen=True)
class PersonalityProbeObservation:
    """A raw observation, never a pass/fail personality assessment."""

    label: str
    request_sha256: str
    raw_response: str | None
    elapsed_seconds: float
    error_type: str | None
    error_message: str | None

    @property
    def succeeded(self) -> bool:
        return self.error_type is None


def observe_personality_cases(
    profile: PersonalityProfile,
    engine: CognitiveEngine,
    cases: tuple[PersonalityProbeCase, ...],
    *,
    max_cases: int,
) -> tuple[PersonalityProbeObservation, ...]:
    """Observe explicit cases sequentially, retaining failures and raw text.

    Refuses excess cases instead of truncating them without disclosure.
    Exception details can contain provider data: review before sharing logs.
    """
    if not isinstance(profile, PersonalityProfile):
        raise TypeError("profile must be a PersonalityProfile.")
    if not isinstance(engine, CognitiveEngine):
        raise TypeError("engine must be a CognitiveEngine.")
    if not isinstance(cases, tuple) or not cases:
        raise ValueError("cases must be a nonempty tuple.")
    if type(max_cases) is not int or max_cases <= 0:
        raise ValueError("max_cases must be a positive integer.")
    if len(cases) > max_cases:
        raise ValueError("Case count exceeds max_cases; no generation performed.")
    if any(not isinstance(case, PersonalityProbeCase) for case in cases):
        raise TypeError("cases must contain PersonalityProbeCase instances.")
    labels = [case.label for case in cases]
    if len(set(labels)) != len(labels):
        raise ValueError("Probe case labels must be unique.")

    assembler = CognitiveContextAssembler()
    observations: list[PersonalityProbeObservation] = []
    for case in cases:
        source = CognitiveRequest(messages=(
            CognitiveMessage(role=CognitiveRole.USER, content=case.user_text),
        ))
        assembled = assembler.assemble(
            CognitiveContext(request=source, personality=profile)
        )
        # Hash is a comparison aid, not proof of truth or an authenticity signature.
        payload = "".join(
            f"{len(message.role.value)}:{message.role.value}"
            f"{len(message.content)}:{message.content}"
            for message in assembled.messages
        )
        request_sha256 = sha256(payload.encode("utf-8")).hexdigest()
        began = perf_counter()
        raw_response: str | None = None
        error_type: str | None = None
        error_message: str | None = None
        try:
            result = engine.respond(assembled)
            if not isinstance(result, CognitiveResponse):
                raise TypeError("Engine returned a non-CognitiveResponse value.")
            raw_response = result.content
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
        observations.append(PersonalityProbeObservation(
            label=case.label,
            request_sha256=request_sha256,
            raw_response=raw_response,
            elapsed_seconds=perf_counter() - began,
            error_type=error_type,
            error_message=error_message,
        ))
    return tuple(observations)
