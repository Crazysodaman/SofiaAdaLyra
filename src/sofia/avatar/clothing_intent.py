"""Natural-language clothing intent parsing for AVATAR wardrobe actions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re


def _normalize(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _clean_target(value: str) -> str:
    text = _normalize(value)
    text = re.sub(r"^(?:the|a|an|my|your|ur)\s+", "", text)
    text = re.sub(r"\s+(?:please)$", "", text)
    return text.strip()


class ClothingActionKind(str, Enum):
    WEAR = "wear"
    ADD = "add"
    REMOVE = "remove"
    SWAP = "swap"
    UNDRESS = "undress"


@dataclass(frozen=True, slots=True)
class ClothingActionIntent:
    kind: ClothingActionKind
    target: str | None = None
    hypothetical: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ClothingActionKind):
            raise TypeError("kind must be ClothingActionKind")
        if self.target is not None and (
            not isinstance(self.target, str) or not self.target.strip()
        ):
            raise ValueError("target must be None or nonempty")
        if type(self.hypothetical) is not bool:
            raise TypeError("hypothetical must be bool")


class ClothingActionParser:
    _FOLLOW = re.compile(
        r"^\s*(?:do\s+it|go\s+ahead|yes[, ]+do\s+it|"
        r"please\s+do\s+it|ok(?:ay)?[, ]+do\s+it)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _IF_ASKED = re.compile(
        r"^\s*if\s+i\s+ask(?:ed)?\s+you\s+to\s+(.+?)"
        r"\s*,?\s*(?:would|will)\s+you\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _QUESTION = re.compile(
        r"^\s*(?:would|will|can|could)\s+you\s+(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _UNDRESS = re.compile(
        r"^\s*(?:please\s+)?(?:undress|get\s+undressed|"
        r"take\s+off\s+(?:all|everything|all\s+your\s+clothes|"
        r"your\s+clothes))\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _REMOVE_A = re.compile(
        r"^\s*(?:please\s+)?(?:take\s+off|remove)\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _REMOVE_B = re.compile(
        r"^\s*(?:please\s+)?take\s+(?:your|ur|the)?\s*(.+?)\s+off"
        r"\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _SWAP = re.compile(
        r"^\s*(?:please\s+)?(?:swap|switch|change)\s+"
        r"(?:your|ur|the)?\s*(?!outfit\b)(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _CHANGE_OUTFIT = re.compile(
        r"^\s*(?:please\s+)?change\s+(?:your\s+)?outfit\s+"
        r"(?:to|into)\s+(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _WEAR = re.compile(
        r"^\s*(?:please\s+)?(?:change\s+into|wear)\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _ADD = re.compile(
        r"^\s*(?:please\s+)?put\s+on\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )

    def parse(self, content: str) -> ClothingActionIntent | None:
        if not isinstance(content, str):
            raise TypeError("clothing action content must be a string")
        text = content.strip()
        if not text:
            return None

        hypothetical = self._IF_ASKED.fullmatch(text)
        if hypothetical is not None:
            inner = self._parse_direct(hypothetical.group(1))
            return (
                None
                if inner is None
                else replace(inner, hypothetical=True)
            )

        question = self._QUESTION.fullmatch(text)
        if question is not None:
            inner = self._parse_direct(question.group(1))
            return (
                None
                if inner is None
                else replace(inner, hypothetical=True)
            )

        return self._parse_direct(text)

    def is_followup(self, content: str) -> bool:
        if not isinstance(content, str):
            return False
        return self._FOLLOW.fullmatch(content.strip()) is not None

    def _parse_direct(self, text: str) -> ClothingActionIntent | None:
        if self._UNDRESS.fullmatch(text) is not None:
            return ClothingActionIntent(ClothingActionKind.UNDRESS)

        for pattern in (self._REMOVE_A, self._REMOVE_B):
            match = pattern.fullmatch(text)
            if match is not None:
                return ClothingActionIntent(
                    ClothingActionKind.REMOVE,
                    _clean_target(match.group(1)),
                )

        match = self._CHANGE_OUTFIT.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.WEAR,
                _clean_target(match.group(1)),
            )

        match = self._WEAR.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.WEAR,
                _clean_target(match.group(1)),
            )

        match = self._ADD.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.ADD,
                _clean_target(match.group(1)),
            )

        match = self._SWAP.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.SWAP,
                _clean_target(match.group(1)),
            )

        return None


