"""Matrix v2 semantic planning over structured concepts and focus."""
from __future__ import annotations

import re

from .contracts import (
    ActionRequirement,
    ConversationFocus,
    EvidenceNeed,
    ReasoningRequirement,
    TurnKernelInput,
    TurnPlan,
)
from .scheduler import ValidatedCognitiveScheduler


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*")
_QUESTION_OPENERS = frozenset({
    "are", "can", "could", "did", "do", "does", "give", "how", "is",
    "show", "tell", "what", "when", "where", "which", "who", "why",
})
_READ_ACTIONS = frozenset({
    "browse", "check", "find", "inspect", "list", "look", "open", "read",
    "scan", "search", "show", "summarize",
})
_MUTATION_ACTIONS = frozenset({
    "apply", "change", "delete", "deploy", "edit", "execute", "install",
    "migrate", "move", "reboot", "remove", "restart", "shutdown", "start",
    "stop", "uninstall", "update", "upgrade", "write",
})
_VERIFY_CONCEPTS = frozenset({
    "confirm", "double-check", "recheck", "sure", "verify",
})
_DOMAIN_CONCEPTS = {
    "environment": frozenset({
        "date", "daylight", "forecast", "humidity", "location", "outside",
        "rain", "season", "snow", "sunrise", "sunset", "temperature",
        "time", "timezone", "weather", "wind",
    }),
    "avatar": frozenset({
        "appearance", "body", "clothes", "clothing", "ears", "hair",
        "outfit", "tail", "wear", "wearing", "wardrobe",
    }),
    "interaction": frozenset({
        "affection", "gesture", "hug", "interaction", "kiss", "pat",
        "pose", "touch",
    }),
    "emotion": frozenset({
        "angry", "arousal", "desire", "emotion", "feel", "feeling",
        "happy", "lonely", "mood", "sad", "upset",
    }),
    "memory": frozenset({
        "earlier", "memory", "recall", "remember", "remembered",
    }),
    "rel": frozenset({
        "bond", "companion", "relationship", "sparks", "together",
    }),
    "habit": frozenset({"habit", "pattern", "routine", "usually"}),
    "dev": frozenset({
        "code", "codebase", "commit", "git", "github", "pytest", "repo",
        "repository", "software",
    }),
    "know": frozenset({
        "document", "documentation", "knowledge", "manual", "pdf",
        "research",
    }),
    "integrate": frozenset({
        "cloudflare", "discord", "home-assistant", "integration", "jmri",
        "tunnel",
    }),
    "body": frozenset({
        "battery", "collision", "gait", "gaia", "motor", "orientation",
        "proximity", "sensor", "servo", "stability",
    }),
    "voice": frozenset({
        "audio", "listen", "microphone", "speech", "stt", "talk", "tts",
        "voice",
    }),
    "machine": frozenset({
        "computer", "cpu", "device", "disk", "docker", "gpu", "hardware",
        "host", "machine", "memory", "network", "node", "ram", "server",
        "storage", "telemetry",
    }),
    "ops": frozenset({
        "container", "docker", "failure", "fault", "fleet", "health",
        "latency", "offline", "process", "service", "telemetry",
    }),
    "cognition": frozenset({
        "cognition", "llm", "matrix", "model", "neuro", "ollama",
        "primary", "routing", "secondary",
    }),
    "goals": frozenset({"goal", "goals"}),
    "authority": frozenset({
        "approval", "authority", "permission", "private", "public",
    }),
    "continuity": frozenset({
        "background", "continue", "pending", "previous", "unfinished",
    }),
}
_EVIDENCE_PREDICATES = {
    "environment": "environment.current",
    "avatar": "avatar.canonical",
    "interaction": "interaction.interpretation",
    "emotion": "emotion.current",
    "memory": "memory.retrieval",
    "rel": "relationship.current",
    "habit": "habit.patterns",
    "voice": "voice.runtime.current",
    "body": "body.sensor.current",
    "machine": "machine.measurement.current",
    "ops": "ops.measurement.current",
    "cognition": "cognition.configuration",
    "continuity": "continuity.current",
    "goals": "goals.current",
}


def _machine_predicate(tokens: frozenset[str]) -> str:
    if "cpu" in tokens and tokens & {"load", "usage", "utilization", "percent"}:
        return "ops.cpu_percent"
    if "cpu" in tokens:
        return "machine.cpu"
    if "gpu" in tokens:
        return "machine.gpu"
    if tokens & {"ram", "memory"}:
        return "machine.memory_bytes"
    if tokens & {"disk", "storage"}:
        return "machine.storage"
    return "machine.hardware"


def _tokens(content: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN.finditer(content))


class MatrixV2Planner:
    """Create one validated plan without creating truth or authority.

    Domain selection uses concept membership plus structured focus, rather than
    an expanding sequence of phrase-shaped regular expressions. Exact command
    and mutation verbs stay deterministic because they are safety boundaries.
    """

    def __init__(self, scheduler: ValidatedCognitiveScheduler | None = None):
        self.scheduler = scheduler or ValidatedCognitiveScheduler()

    def plan(
        self,
        turn: TurnKernelInput,
        focus: ConversationFocus,
        *,
        neuro_snapshot=None,
    ) -> TurnPlan:
        if not isinstance(turn, TurnKernelInput):
            raise TypeError("turn must be TurnKernelInput")
        if not isinstance(focus, ConversationFocus):
            raise TypeError("focus must be ConversationFocus")
        tokens = _tokens(turn.content)
        token_set = frozenset(tokens)
        domains = [
            domain
            for domain, concepts in _DOMAIN_CONCEPTS.items()
            if token_set & concepts
        ]
        if any(
            tokens[index:index + 2] == ("memory", "usage")
            for index in range(max(0, len(tokens) - 1))
        ):
            if "machine" not in domains:
                domains.append("machine")
            if not token_set & {"recall", "remember", "remembered"}:
                domains = [domain for domain in domains if domain != "memory"]
        if any(
            tokens[index:index + 2] == ("home", "assistant")
            for index in range(max(0, len(tokens) - 1))
        ) and "integrate" not in domains:
            domains.append("integrate")
        reference = focus.primary_reference
        if reference is not None and reference.kind == "fleet-node":
            for domain in ("machine", "ops"):
                if domain not in domains:
                    domains.append(domain)
        elif (
            reference is not None
            and reference.kind != "local-host"
            and "machine" in domains
            and "ops" not in domains
        ):
            domains.append("ops")
        if not domains:
            domains.append("social")

        command_tokens = tokens[1:] if tokens[:1] == ("please",) else tokens
        first = None if not command_tokens else command_tokens[0]
        elliptical_action = command_tokens[:2] == ("do", "it")
        if first in _MUTATION_ACTIONS:
            action = ActionRequirement.MUTATION
        elif first in _READ_ACTIONS:
            action = ActionRequirement.READ_ONLY
        elif elliptical_action and focus.pending_actions:
            action = ActionRequirement.CLARIFY
        else:
            action = ActionRequirement.NONE

        question = "?" in turn.content or (
            bool(tokens) and tokens[0] in _QUESTION_OPENERS
        )
        intent = self._intent(domains, token_set, action, question)
        reasoning = self._reasoning(intent, domains, token_set, action)
        reasoning, budget = self.scheduler.budget(
            reasoning,
            neuro_snapshot=neuro_snapshot,
        )
        subject_id = (
            reference.subject_id
            if reference is not None
            else (
                "runtime:local-host"
                if {"machine", "ops"} & set(domains)
                else (
                    "runtime:environment"
                    if "environment" in domains
                    else "runtime:sofia"
                )
            )
        )
        scope_id = turn.audience_id or "audience:unbound"
        needs = tuple(
            EvidenceNeed(
                need_id=f"need:{domain}:{index}",
                subject_id=subject_id,
                predicate=(
                    _machine_predicate(token_set)
                    if domain == "machine"
                    else _EVIDENCE_PREDICATES[domain]
                ),
                scope_id=scope_id,
                max_age_seconds=(60.0 if domain in {"environment", "machine", "ops"}
                                 else 300.0),
                minimum_trust=(0.8 if domain in {"machine", "ops", "body"}
                               else 0.6),
            )
            for index, domain in enumerate(domains, start=1)
            if domain in _EVIDENCE_PREDICATES
        )
        strategy = self._strategy(intent, action, bool(needs))
        schedule = self.scheduler.schedule(
            turn_id=turn.turn_id,
            evidence_needs=needs,
            reasoning_requirement=reasoning,
            response_strategy=strategy,
            budget=budget,
        )
        return TurnPlan(
            turn_id=turn.turn_id,
            focus_revision=focus.revision,
            domains=tuple(domains),
            evidence_needs=needs,
            schedule=schedule,
            response_strategy=strategy,
            action_requires_authority=(
                action is ActionRequirement.MUTATION
            ),
            intent=intent,
            action_requirement=action,
            reasoning_requirement=reasoning,
            budget=budget,
        )

    @staticmethod
    def _intent(domains, tokens, action, question) -> str:
        if "goals" in domains:
            return "goal_management"
        if tokens & _VERIFY_CONCEPTS:
            return "verification"
        if action is not ActionRequirement.NONE:
            return "action_request"
        if "memory" in domains:
            return "memory_query"
        if {"machine", "ops", "cognition"} & set(domains):
            return "operational_query" if question else "operational_context"
        if "environment" in domains and question:
            return "environment_query"
        if "avatar" in domains and question:
            return "avatar_query"
        if {"social", "emotion", "rel"} & set(domains):
            return "social_checkin" if question else "social"
        return "general_query" if question else "general"

    @staticmethod
    def _reasoning(intent, domains, tokens, action):
        if intent == "verification" or action is ActionRequirement.MUTATION:
            return ReasoningRequirement.VERIFY
        if intent == "goal_management":
            return ReasoningRequirement.DETERMINISTIC
        if {"ops", "machine", "dev", "body"} & set(domains):
            return ReasoningRequirement.DEEP
        if {"social", "emotion", "interaction", "rel", "memory"} & set(domains):
            return ReasoningRequirement.STANDARD
        if "environment" in domains:
            return ReasoningRequirement.DETERMINISTIC
        return ReasoningRequirement.FAST

    @staticmethod
    def _strategy(intent, action, has_evidence):
        if intent == "goal_management":
            return "deterministic"
        if action is ActionRequirement.CLARIFY:
            return "clarify"
        if action is not ActionRequirement.NONE or has_evidence:
            return "tool-assisted"
        return "generative"
