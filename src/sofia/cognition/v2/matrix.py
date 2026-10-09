"""Matrix v2 semantic planning over structured concepts and focus."""
from __future__ import annotations

import re
import unicodedata

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
    "browse", "check", "discover", "find", "inspect", "list", "look", "open", "read",
    "scan", "search", "show", "summarize",
})
_MUTATION_ACTIONS = frozenset({
    "apply", "change", "create", "delete", "deploy", "design", "edit",
    "execute", "generate", "install", "make", "migrate", "move", "reboot",
    "remove", "restart", "send", "set", "shutdown", "start", "stop", "swap",
    "switch", "wear",
    "take", "turn", "undress", "uninstall", "update", "upgrade", "write",
})
_VERIFY_CONCEPTS = frozenset({
    "confirm", "double-check", "recheck", "sure", "verify",
})
_DOMAIN_CONCEPTS = {
    "environment": frozenset({
        "date", "day", "daylight", "forecast", "humidity", "location", "outside",
        "rain", "season", "snow", "sunrise", "sunset", "temperature",
        "time", "timezone", "weather", "wind",
    }),
    "avatar": frozenset({
        "appearance", "body", "clothes", "clothing", "ears", "hair",
        "outfit", "tail", "wear", "wearing", "wardrobe", "underwear",
        "panties", "bra", "bralette", "bikini", "boots", "footwear",
        "foot", "garment", "hoodie", "jacket", "shoes", "socks", "undress",
    }),
    "interaction": frozenset({
        "affection", "gesture", "gestures", "hug", "interaction",
        "interactions", "kiss", "kisses", "pat", "pats", "pose", "touch",
        "touches",
    }),
    "emotion": frozenset({
        "affect", "angry", "arousal", "desire", "emotion", "feel", "feeling",
        "happy", "lonely", "mood", "quiet", "sad", "upset",
    }),
    "memory": frozenset({
        "earlier", "memory", "mind", "recall", "reflection", "reflections",
        "remember", "remembered", "thinking",
    }),
    "rel": frozenset({
        "bond", "companion", "gone", "relationship", "reunion", "return",
        "sparks", "together",
    }),
    "habit": frozenset({
        "habit", "normally", "pattern", "routine", "usually",
    }),
    "dev": frozenset({
        "code", "codebase", "commit", "git", "github", "pytest", "repo",
        "repository", "software", "jython", "python", "programming",
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
        "latency", "offline", "process", "processes", "service",
        "telemetry", "uptime",
    }),
    "cognition": frozenset({
        "cognition", "llm", "matrix", "matrixs", "matrixes", "matrices",
        "model", "neuro", "ollama",
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
    "know": "knowledge.retrieval",
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
    normalized = unicodedata.normalize("NFKD", content).encode(
        "ascii", "ignore"
    ).decode("ascii")
    return tuple(
        match.group(0).casefold() for match in _TOKEN.finditer(normalized)
    )


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

        if "emotion" in domains and "it" in token_set and "interaction" not in domains:
            domains.append("interaction")
        if token_set & {"want", "wanna"} and token_set & {"change", "changing"}:
            if "avatar" not in domains:
                domains.append("avatar")
        if {"feel", "changing"} <= token_set and "avatar" not in domains:
            domains.append("avatar")
        if token_set >= {"where", "i"} and "environment" not in domains:
            domains.append("environment")
        if (
            token_set & {"am", "pm"}
            and any(token.isdigit() for token in tokens)
            and "environment" not in domains
        ):
            domains.append("environment")
        if {"changed", "restart"} <= token_set and "continuity" not in domains:
            domains.append("continuity")

        command_tokens = tokens
        if command_tokens[:1] in {("please",), ("sofia",)}:
            command_tokens = command_tokens[1:]
        first = None if not command_tokens else command_tokens[0]
        elliptical_action = command_tokens[:2] == ("do", "it")
        conditional_change = bool(
            token_set & {"want", "wanna", "feel"}
            and token_set & {"change", "changing"}
        )
        later_mutation = bool(
            ("," in turn.content or "?" in turn.content)
            and token_set & {"restart", "design", "generate", "create"}
        )
        if first in _MUTATION_ACTIONS and not conditional_change:
            action = ActionRequirement.MUTATION
        elif later_mutation:
            action = ActionRequirement.MUTATION
        elif first in _READ_ACTIONS:
            action = ActionRequirement.READ_ONLY
        elif elliptical_action:
            action = ActionRequirement.CLARIFY
        else:
            action = ActionRequirement.NONE

        if "machine" in domains and token_set & {
            "cpu", "gpu", "hardware", "ram", "storage",
        } and not token_set & {"recall", "remember", "remembered"}:
            domains = [domain for domain in domains if domain != "memory"]
        if (
            action is ActionRequirement.READ_ONLY
            and "machine" in domains
            and "ops" not in domains
        ):
            domains.append("ops")
        if (
            "machine" in domains
            and token_set & {"fleet", "other", "see"}
            and "ops" not in domains
        ):
            domains.append("ops")

        question = (
            "?" in turn.content
            or (bool(tokens) and tokens[0] in _QUESTION_OPENERS)
            or (len(tokens) == 1 and token_set & {"date", "time", "weather"})
            or bool(token_set & {"am", "pm"})
            or token_set & {"hru"}
            or tokens[:3] in {("how", "are", "you"), ("how", "r", "u")}
        )
        intent = self._intent(domains, token_set, action, question)
        if (
            {"interaction", "emotion"} <= set(domains)
            and "it" in token_set
            and question
        ):
            intent = "interaction_followup"
        if conditional_change:
            intent = "general"
            if "social" not in domains:
                domains.append("social")
        if (
            len(tokens) <= 5
            and token_set & {"why", "all", "more"}
            and action is ActionRequirement.NONE
        ):
            intent = "general"
        if "emotion" in domains and token_set & {"quiet", "seem"}:
            intent = "social_checkin"
            if "social" not in domains:
                domains.append("social")
        if {"environment", "emotion"} <= set(domains):
            intent = "general"
        if intent == "social_checkin" and token_set & {"mean", "relationship"}:
            if "rel" not in domains:
                domains.append("rel")
        if intent == "social_checkin" and "emotion" not in domains:
            domains.append("emotion")
        if "body" in domains and not token_set & {
            "battery", "collision", "gaia", "orientation", "proximity",
            "sensor", "servo", "stability",
        }:
            domains.remove("body")
            if not domains:
                domains.append("social")
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
        strategy = self._strategy(intent, action, bool(needs), domains)
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
        if action in {ActionRequirement.MUTATION, ActionRequirement.CLARIFY}:
            return "action_request"
        if "memory" in domains:
            return (
                "reflection_query"
                if tokens & {"mind", "reflection", "reflections", "thinking"}
                else "memory_query"
            )
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
        if "environment" in domains and "emotion" in domains:
            # The host environment coordinator can answer the grounded
            # influence question—or explicit lack of evidence—without a model.
            return ReasoningRequirement.DETERMINISTIC
        if {"ops", "machine", "dev", "body"} & set(domains):
            return ReasoningRequirement.DEEP
        if {"social", "emotion", "interaction", "rel", "memory"} & set(domains):
            return ReasoningRequirement.STANDARD
        if "environment" in domains:
            return ReasoningRequirement.DETERMINISTIC
        return ReasoningRequirement.FAST

    @staticmethod
    def _strategy(intent, action, has_evidence, domains):
        if intent == "goal_management":
            return "deterministic"
        if action is ActionRequirement.CLARIFY:
            return "clarify"
        if action is not ActionRequirement.NONE:
            return "tool-assisted"
        if intent == "environment_query":
            return "deterministic"
        if intent == "operational_query":
            if set(domains) <= {"cognition"}:
                return "deterministic"
            return "tool-assisted"
        if intent in {"avatar_query", "memory_query", "reflection_query"}:
            return "hybrid"
        return "generative"
