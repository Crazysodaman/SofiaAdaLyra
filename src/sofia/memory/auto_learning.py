"""Conservative automatic proposal of explicit user memory from saved chat.

This layer never promotes memory. It recognizes a narrow set of first-person
statements and routes them through the existing reviewed-memory workflow using
the exact saved USER message as provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from uuid import UUID, uuid5

from sofia.application.memory_review import MemoryReviewService
from sofia.memory.provenance import CandidateStatus, MemoryCandidate


_NAMESPACE = UUID("8f20ca70-9148-4cf3-bdf0-b12c2b9868e6")

_REMEMBER = re.compile(r"^remember(?: that)?\s+(?P<value>.+?)[.!]?$", re.I)
_PREFERENCE = re.compile(
    r"^i\s+(?P<verb>prefer|like|love|dislike|hate)\s+(?P<value>.+?)[.!]?$",
    re.I,
)
_MY_FACT = re.compile(
    r"^my\s+(?P<field>[a-z][a-z0-9 _-]{1,48})\s+is\s+(?P<value>.+?)[.!]?$",
    re.I,
)
_I_AM = re.compile(
    r"^i(?:'m| am)\s+(?:an?\s+)?(?P<value>.+?)[.!]?$",
    re.I,
)
_I_WORK = re.compile(
    r"^i\s+work\s+(?P<prep>as|in)\s+(?P<value>.+?)[.!]?$",
    re.I,
)

_BLOCK_ALWAYS = re.compile(
    r"\b(?:password|passphrase|api\s*key|access\s*token|refresh\s*token|"
    r"private\s*key|secret\s*key|social\s*security|ssn|credit\s*card|"
    r"bank\s*account|routing\s*number)\b",
    re.I,
)
_SENSITIVE = re.compile(
    r"\b(?:sex|sexual|intimate|arousal|aroused|fetish|kink|breasts?|"
    r"genitals?|groin|buttocks?|nude|naked|diagnos(?:is|ed)|medication|"
    r"religion|political\s+party|union\s+member|orientation)\b",
    re.I,
)
_TRANSIENT = re.compile(
    r"\b(?:right now|today only|for now|currently downloading|"
    r"temporary|just this once)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class LearnedMemoryProposal:
    candidate: MemoryCandidate
    kind: str


def _single_line(value: str, *, limit: int = 360) -> str:
    clean = " ".join(value.strip().split())
    if not clean or len(clean) > limit or any(ch in clean for ch in "\x00\r\n"):
        raise ValueError("memory content must be bounded text")
    return clean


def _possessive(label: str) -> str:
    return label + ("'" if label.casefold().endswith("s") else "'s")


class ExplicitChatMemoryLearner:
    """Recognize explicit, stable statements and propose reviewable memory."""

    def __init__(
        self,
        review: MemoryReviewService,
        *,
        allow_sensitive: bool = False,
    ) -> None:
        if not isinstance(review, MemoryReviewService):
            raise TypeError("review must be MemoryReviewService")
        if type(allow_sensitive) is not bool:
            raise TypeError("allow_sensitive must be boolean")
        self.review = review
        self.allow_sensitive = allow_sensitive

    def derive(
        self,
        content: str,
        *,
        principal_label: str,
    ) -> tuple[str, str] | None:
        if not isinstance(content, str):
            raise TypeError("content must be text")
        if not isinstance(principal_label, str) or not principal_label.strip():
            raise ValueError("principal_label required")
        clean = content.strip()
        if (
            not clean
            or len(clean) > 500
            or "\n" in clean
            or chr(96) * 3 in clean
            or "?" in clean
            or _BLOCK_ALWAYS.search(clean)
            or _TRANSIENT.search(clean)
        ):
            return None
        if _SENSITIVE.search(clean) and not self.allow_sensitive:
            return None

        label = _single_line(principal_label, limit=80)

        match = _REMEMBER.fullmatch(clean)
        if match is not None:
            value = _single_line(match.group("value"))
            return (
                "explicit_remember",
                f"{label} explicitly asked Sofía to remember: {value}",
            )

        match = _PREFERENCE.fullmatch(clean)
        if match is not None:
            value = _single_line(match.group("value"))
            canonical = {
                "prefer": "prefers",
                "like": "likes",
                "love": "loves",
                "dislike": "dislikes",
                "hate": "hates",
            }[match.group("verb").casefold()]
            return "explicit_preference", f"{label} {canonical} {value}."

        match = _MY_FACT.fullmatch(clean)
        if match is not None:
            field = _single_line(match.group("field"), limit=50).casefold()
            value = _single_line(match.group("value"))
            if _BLOCK_ALWAYS.search(field):
                return None
            return "explicit_fact", f"{_possessive(label)} {field} is {value}."

        match = _I_WORK.fullmatch(clean)
        if match is not None:
            prep = match.group("prep").casefold()
            value = _single_line(match.group("value"))
            return "explicit_fact", f"{label} works {prep} {value}."

        match = _I_AM.fullmatch(clean)
        if match is not None:
            value = _single_line(match.group("value"))
            if re.search(
                r"\b(?:happy|sad|angry|tired|bored|hungry|excited|"
                r"frustrated|upset|horny|aroused|busy|sick)\b",
                value,
                re.I,
            ):
                return None
            return (
                "explicit_self_description",
                f"{label} describes themself as {value}.",
            )

        return None

    def propose(
        self,
        *,
        session_id: str,
        message_id: str,
        content: str,
        created_at: datetime,
        principal_label: str,
    ) -> LearnedMemoryProposal | None:
        derived = self.derive(content, principal_label=principal_label)
        if derived is None:
            return None
        kind, claim = derived
        candidate_id = uuid5(
            _NAMESPACE,
            f"{session_id}\x1f{message_id}\x1f{kind}\x1f{claim}",
        )
        status = self.review.status(candidate_id)
        if status is not None:
            candidate = self.review.get(candidate_id)
            if candidate is None:
                raise RuntimeError(
                    "memory candidate status exists without candidate"
                )
            return LearnedMemoryProposal(candidate, kind)

        candidate = self.review.propose(
            session_id=session_id,
            message_ids=(message_id,),
            content=claim,
            created_at=created_at,
            candidate_id=candidate_id,
        )
        if self.review.status(candidate_id) is not CandidateStatus.PROPOSED:
            raise RuntimeError("automatic memory candidate was not proposed")
        return LearnedMemoryProposal(candidate, kind)
