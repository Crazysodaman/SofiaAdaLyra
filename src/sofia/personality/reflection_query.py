"""Deterministic reporting of recorded reflection state.

Questions about what Sofía has been thinking about must report stored reflection
records or say none are available. They must never trigger a fresh invented
retrospective narrative.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.personality.reflection import RecordedThought


@dataclass(frozen=True, slots=True)
class ReflectionQueryAnswer:
    recognized: bool
    content: str = ""

    def __post_init__(self) -> None:
        if type(self.recognized) is not bool:
            raise TypeError("recognized must be bool")
        if not isinstance(self.content, str):
            raise TypeError("content must be str")
        if not self.recognized and self.content:
            raise ValueError("unrecognized reflection answer cannot contain content")


def _normalize(query: str) -> str:
    return " ".join(
        query.strip().casefold().replace("’", "'").split()
    ).rstrip(" ?!.")


def _conversational_reflection(content: str) -> str:
    """Render a stored reflection naturally without inventing new thought content."""
    text = " ".join(content.strip().split())
    workspace = re.fullmatch(
        r"Workspace comparison observed (\d+) added, (\d+) modified, and "
        r"(\d+) removed paths\. Cause, authorship, and significance are not established\.",
        text,
        re.IGNORECASE,
    )
    if workspace is not None:
        added, modified, removed = workspace.groups()
        return (
            "the recent workspace changes. I recorded "
            f"{added} added, {modified} modified, and {removed} removed paths, "
            "but I don't have grounded evidence yet for who caused them or how "
            "significant they are"
        )
    return text.rstrip(".")


class ReflectionQueryResolver:
    _QUERY_RE = re.compile(
        r"\b(?:"
        r"what(?:'s|\s+is)\s+on\s+your\s+mind"
        r"|what\s+have\s+you\s+been\s+thinking(?:\s+about)?"
        r"|what\s+are\s+you\s+thinking(?:\s+about)?"
        r"|what\s+were\s+you\s+thinking(?:\s+about)?"
        r"|anything\s+on\s+your\s+mind"
        r"|(?:list|show)\s+(?:me\s+)?(?:your\s+)?recorded\s+reflections"
        r"|(?:show|give\s+me)\s+(?:your\s+)?reflection\s+history"
        r")\b",
        re.IGNORECASE,
    )

    @classmethod
    def might_match(cls, query: str) -> bool:
        return (
            isinstance(query, str)
            and cls._QUERY_RE.search(_normalize(query)) is not None
        )

    def resolve(
        self,
        query: str,
        *,
        thoughts: tuple[RecordedThought, ...],
    ) -> ReflectionQueryAnswer:
        if not isinstance(query, str):
            raise TypeError("query must be str")
        if not isinstance(thoughts, tuple) or any(
            not isinstance(item, RecordedThought) for item in thoughts
        ):
            raise TypeError("thoughts must be a tuple of RecordedThought")
        if not self.might_match(query):
            return ReflectionQueryAnswer(False)

        if not thoughts:
            return ReflectionQueryAnswer(
                True,
                (
                    "I don't have a recorded reflection to report right now. "
                    "I won't invent thoughts, logs, experiments, or background "
                    "activity that were never recorded."
                ),
            )

        recent = tuple(
            sorted(
                thoughts,
                key=lambda item: (item.created_at, item.thought_id),
                reverse=True,
            )[:3]
        )
        latest = recent[0]
        latest_text = _conversational_reflection(latest.content)

        # Ordinary "what are you thinking about?" is conversational. Report
        # the newest actually recorded reflection without dumping audit rows or
        # timestamps unless the user explicitly asked for records/history.
        normalized = _normalize(query)
        detail_requested = any(
            token in normalized
            for token in (
                "list",
                "records",
                "recorded reflections",
                "reflection history",
                "timestamps",
                "when did",
            )
        )
        if not detail_requested:
            return ReflectionQueryAnswer(
                True,
                f"Mostly {latest_text}.",
            )

        if len(recent) == 1:
            return ReflectionQueryAnswer(
                True,
                (
                    "My latest recorded reflection is "
                    f"{latest.content} "
                    f"(recorded {latest.created_at.isoformat()})."
                ),
            )

        lines = ["My recent recorded reflections are:"]
        for item in recent:
            lines.append(
                f"- {item.content} "
                f"(recorded {item.created_at.isoformat()})"
            )
        return ReflectionQueryAnswer(True, "\n".join(lines))
