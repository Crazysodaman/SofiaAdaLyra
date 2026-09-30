"""Evidence-limited answers for narrow operational status questions.

A configured model is not proof of GPU residency or actual per-turn routing.
A network interface inventory is not a latency/packet-loss measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.config.cognitive_models import CognitiveModelSelection


@dataclass(frozen=True, slots=True)
class OperationalStatusAnswer:
    recognized: bool
    content: str = ""


def _normalize(query: str) -> str:
    return " ".join(
        query.strip().casefold().replace("’", "'").split()
    ).rstrip("?.! ")


_NETWORK_FORMS = frozenset({
    "hows the network",
    "how's the network",
    "how is the network",
    "how's your network",
    "hows your network",
    "how is your network",
    "network status",
    "what's the network status",
    "whats the network status",
    "how's network",
    "hows network",
})

_MODEL_FORM = re.compile(
    r"^(?:what|which)\s+(?:llm|model)(?:\s+is|\s+am|\s+are)?\s+"
    r"(?:(?:i|you|sofia)\s+)?running(?:\s+(?:right\s+now|rn|currently))?$|"
    r"^what\s+(?:llm|model)\s+(?:am\s+i|are\s+you|is\s+sofia)"
    r"\s+(?:using|running)(?:\s+(?:right\s+now|rn|currently))?$",
    re.IGNORECASE,
)


class OperationalStatusQueryResolver:
    def resolve(
        self,
        query: str,
        *,
        selection: CognitiveModelSelection,
    ) -> OperationalStatusAnswer:
        if not isinstance(query, str):
            raise TypeError("query must be str")
        if not isinstance(selection, CognitiveModelSelection):
            raise TypeError("selection must be CognitiveModelSelection")
        normalized = _normalize(query)
        if normalized.startswith("so "):
            normalized = normalized[3:].lstrip()

        if normalized in _NETWORK_FORMS:
            return OperationalStatusAnswer(
                True,
                "I don't have a fresh, verified network-health measurement "
                "for this question. I can't claim zero packet loss, low "
                "latency, or that every machine is online without checks. "
                "A network inspection can report interfaces; a connectivity "
                "test is needed to measure latency and loss.",
            )

        if _MODEL_FORM.fullmatch(normalized):
            primary = selection.primary
            content = (
                f"My configured primary model is {primary.model} "
                f"through {primary.provider}."
            )
            if selection.routing_enabled and selection.secondary is not None:
                secondary = selection.secondary
                content += (
                    f" The configured secondary is {secondary.model} "
                    f"through {secondary.provider}."
                )
            content += (
                " This configuration alone doesn't prove which model "
                "handled this turn or what is currently loaded."
            )
            return OperationalStatusAnswer(True, content)
        return OperationalStatusAnswer(False)
