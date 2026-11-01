"""Evidence-limited answers for narrow operational status questions.

A configured model is not proof of GPU residency or actual per-turn routing.
A network interface inventory is not a latency/packet-loss measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.platform.authority.model import Authority
from sofia.platform.config.cognitive_models import CognitiveModelSelection
from sofia.platform.operational.model import OperationalState, RuntimeContinuity


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

_DEV_SELF_CAPABILITY_FORM = re.compile(
    r"^(?:are\s+(?:you|u)\s+able\s+to|can\s+(?:you|u))\s+"
    r"(?:make|create|write|change|modify|edit)\s+(?:new\s+)?"
    r"(?:code|your\s+(?:own\s+)?code|code\s+for\s+(?:yourself|your\s+self))"
    r"(?:\s+for\s+(?:yourself|your\s+self))?$",
    re.IGNORECASE,
)

_MODEL_FORM = re.compile(
    r"^(?:what|which)\s+(?:llm|model)(?:\s+is|\s+am|\s+are)?\s+"
    r"(?:(?:i|you|sofia)\s+)?running(?:\s+(?:right\s+now|rn|currently))?$|"
    r"^what\s+(?:llm|model)\s+(?:am\s+i|are\s+you|is\s+sofia)"
    r"\s+(?:using|running)(?:\s+(?:right\s+now|rn|currently))?$",
    re.IGNORECASE,
)


_PREVIOUS_RUNTIME_QUESTION = re.compile(
    r"\b(?:last|previous|prior)\b.*\b(?:runtime|run|session)\b|"
    r"\b(?:runtime|session)\b.*\b(?:last|previous|prior)\b",
    re.IGNORECASE,
)


# These are strictly read-only self-state requests. "PID" means the OS
# process executing the local conversation, not an invented remote worker.
_CURRENT_RUNTIME_READ = re.compile(
    r"\b(?:current|this|active|running|present)\s+(?:sofia\s+)?runtime\b"
    r"|\b(?:runtime|process)\s+(?:start(?:ed)?\s+)?(?:time|date|pid|id)\b"
    r"|\b(?:your|sofia(?:'s)?)\s+(?:own\s+)?(?:process\s+id|pid)\b"
    r"|\bprocess\s+id\b"
    r"|\b(?:when\s+(?:did|was)\s+you\s+(?:start|started|run))\b",
    re.IGNORECASE,
)
_RUNTIME_HISTORY_FOLLOWUP = re.compile(
    r"\bwhen\s+(?:were|did)\s+you\s+(?:running|run)\s+before\b"
    r"|\bwhen\s+did\s+you\s+last\s+(?:run|start)\b",
    re.IGNORECASE,
)
_RUNTIME_MUTATION = re.compile(
    r"^\s*(?:please\s+)?(?:start|stop|restart|kill|terminate|"
    r"change|remove|delete|shutdown)\b",
    re.IGNORECASE,
)
_RUNTIME_UNRELATED = re.compile(
    r"\b(?:error|fault|crash|logs?|malware|virus|suspicious|security|"
    r"all\s+processes|process\s+list|service\s+status|"
    r"configuration|settings|meaning|mean|definition|format)\b",
    re.IGNORECASE,
)


def _is_current_runtime_read(query: str) -> bool:
    normalized = _normalize(query)
    if _RUNTIME_MUTATION.match(normalized) or _RUNTIME_UNRELATED.search(normalized):
        return False
    return _CURRENT_RUNTIME_READ.search(normalized) is not None


def _current_runtime_answer(
    state: OperationalState | None, *,
    process_id: int | None,
    continuity: RuntimeContinuity | None,
    include_previous: bool,
) -> str:
    if state is None:
        content = (
            "I don't have a verified current Core runtime state in this "
            "conversation. I won't invent its start time."
        )
    else:
        content = (
            "This Sofía runtime started at "
            f"{state.started_at.isoformat()} (UTC offset included), "
            f"runtime ID {state.runtime_id}, "
            f"lifecycle state {state.lifecycle_state}."
        )
    if process_id is not None:
        content += (
            f" The local Python process handling this conversation has "
            f"PID {process_id}. This is a host OS process identifier, not a "
            "remote Core worker PID; it does not by itself establish the "
            "operating system process creation time."
        )
    elif state is not None:
        content += " This interface has no verified local process PID."
    if include_previous:
        content += " " + _runtime_history_answer(continuity)
    return content


def _is_previous_runtime_read(query: str) -> bool:
    normalized = _normalize(query)
    words = set(re.findall(r"[a-z]+", normalized))
    compact_runtime_history = re.fullmatch(
        r"(?:(?:current|this)\s+runtime\s*\?\s*)?"
        r"(?:last|previous|prior)\s+(?:runtime|session)\s*\??",
        normalized,
    ) is not None
    return (
        (
            (
                _PREVIOUS_RUNTIME_QUESTION.search(normalized) is not None
                and bool(words & {"what", "when", "tell", "show", "how"})
            )
            or compact_runtime_history
            or _RUNTIME_HISTORY_FOLLOWUP.search(normalized) is not None
        )
        and _RUNTIME_MUTATION.match(normalized) is None
        and _RUNTIME_UNRELATED.search(normalized) is None
    )


def _runtime_history_answer(continuity: RuntimeContinuity | None) -> str:
    if continuity is None:
        return (
            "I don't have a current runtime history record available. "
            "I won't invent a previous startup or shutdown time."
        )
    current = continuity.current_started_at.isoformat()
    if continuity.previous_started_at is None:
        return (
            f"This runtime started at {current}. I have no verified "
            "previous runtime timestamp in this state, which does not "
            "prove no previous runtime existed."
        )
    previous = continuity.previous_started_at.isoformat()
    if continuity.previous_stopped_at is None:
        stop = "No verified shutdown timestamp was recorded for that runtime."
    else:
        stop = (
            "Its recorded shutdown was at "
            f"{continuity.previous_stopped_at.isoformat()}."
        )
    return (
        f"My previous recorded runtime started at {previous}. "
        f"{stop} This runtime started at {current}."
    )


class OperationalStatusQueryResolver:
    @classmethod
    def is_current_runtime_query(cls, query: str) -> bool:
        return isinstance(query, str) and _is_current_runtime_read(query)

    @classmethod
    def is_previous_runtime_query(cls, query: str) -> bool:
        return isinstance(query, str) and _is_previous_runtime_read(query)

    def resolve(
        self,
        query: str,
        *,
        selection: CognitiveModelSelection,
        capability_names: tuple[str, ...] = (),
        authority: Authority | None = None,
        continuity: RuntimeContinuity | None = None,
        current_runtime: OperationalState | None = None,
        process_id: int | None = None,
    ) -> OperationalStatusAnswer:
        if not isinstance(query, str):
            raise TypeError("query must be str")
        if not isinstance(selection, CognitiveModelSelection):
            raise TypeError("selection must be CognitiveModelSelection")
        if not isinstance(capability_names, tuple) or any(
            not isinstance(item, str) or not item.strip()
            for item in capability_names
        ):
            raise TypeError(
                "capability_names must be a tuple of nonempty strings"
            )
        if authority is not None and not isinstance(authority, Authority):
            raise TypeError("authority must be Authority or None")
        if continuity is not None and not isinstance(continuity, RuntimeContinuity):
            raise TypeError("continuity must be RuntimeContinuity or None")
        if current_runtime is not None and not isinstance(current_runtime, OperationalState):
            raise TypeError("current_runtime must be OperationalState or None")
        if process_id is not None and (type(process_id) is not int or process_id <= 0):
            raise ValueError("process_id must be a positive integer or None")
        current_query = self.is_current_runtime_query(query)
        previous_query = self.is_previous_runtime_query(query)
        if current_query:
            return OperationalStatusAnswer(
                True,
                _current_runtime_answer(
                    current_runtime, process_id=process_id,
                    continuity=continuity, include_previous=previous_query,
                ),
            )
        if previous_query:
            return OperationalStatusAnswer(
                True,
                _runtime_history_answer(continuity),
            )
        normalized = _normalize(query)
        if normalized.startswith("so "):
            normalized = normalized[3:].lstrip()

        if _DEV_SELF_CAPABILITY_FORM.fullmatch(normalized):
            registered = set(capability_names)
            dev_capabilities = tuple(
                name
                for name in (
                    "codebase.inspect",
                    "dev.status",
                    "dev.build",
                    "dev.apply",
                    "dev.commit",
                    "dev.push",
                    "dev.rollback",
                )
                if name in registered
            )
            if not dev_capabilities:
                return OperationalStatusAnswer(
                    True,
                    (
                        "I don't have registered DEV capabilities proving I can "
                        "modify my code in this runtime."
                    ),
                )
            return OperationalStatusAnswer(
                True,
                (
                    "Yes. This runtime has registered DEV capabilities for "
                    "inspecting and changing the Sofía codebase"
                    + (
                        ": " + ", ".join(dev_capabilities) + "."
                        if dev_capabilities
                        else "."
                    )
                    + " A specific edit still has to pass the current Matrix, "
                    "authority, and Capability Gateway checks; having the "
                    "capability does not grant itself permission."
                ),
            )

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
