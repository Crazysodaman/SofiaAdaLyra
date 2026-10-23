"""Conservative read-only intent recognition for named Fleet machines.

This recognizes a question's subject; it never proves Fleet enrollment,
remote reachability, permission, or a successful inspection.
"""
from __future__ import annotations

import re


_NAMED_MACHINE_VISIBILITY = re.compile(
    r"^\s*(?:(?:can|could|do)\s+(?:you|u)\s+"
    r"(?:see|find|reach|access|connect(?:\s+to)?)"
    r"|are\s+(?:you|u)\s+connected\s+to)\s+"
    r"(?:(?:the|a|an)\s+)?"
    r"(?:(?:computer|host|server|machine|node)\s+)?"
    r"(?P<target>[a-z][a-z0-9_.-]{1,63})\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_NON_MACHINE_SUBJECTS = frozenset({
    "me", "you", "us", "it", "this", "that", "them", "myself",
    "anything", "everything", "something", "nothing", "anyone",
    "everyone", "somebody", "nobody", "screen", "image", "photo",
    "picture", "message", "text", "camera", "clearly",
})
_NAMED_MACHINE_HARDWARE = (
    re.compile(
        r"\bwhat\s+(?:hardware|cpu|gpu|ram|memory)\s+(?:does|is\s+on)\s+"
        r"(?P<target>[a-z][a-z0-9_.-]{1,63})(?:\s+have)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<target>[a-z][a-z0-9_.-]{1,63})(?:'|’)?s\s+"
        r"(?:hardware|cpu|gpu|ram|memory)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:hardware|cpu|gpu|ram|memory)\s+(?:on|for|of)\s+"
        r"(?P<target>[a-z][a-z0-9_.-]{1,63})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:inspect|check|query|show\s+me|get)\s+"
        r"(?P<target>[a-z][a-z0-9_.-]{1,63})(?:'|’)?s?\s+"
        r"(?:hardware|cpu|gpu|ram|memory)\b",
        re.IGNORECASE,
    ),
)


def asks_about_machine_visibility(content: str) -> bool:
    """Recognize a named-machine question without assuming its identity.

    A successful match only selects read-only Fleet *checking*, not an
    assertion that the named item is a registered or reachable machine.
    """
    if not isinstance(content, str):
        raise TypeError("content must be str")
    match = _NAMED_MACHINE_VISIBILITY.fullmatch(content)
    return (
        match is not None
        and match.group("target").casefold() not in _NON_MACHINE_SUBJECTS
    )


def asks_about_named_machine_hardware(content: str) -> bool:
    """Recognize an explicitly named remote hardware subject.

    Recognition selects read-only Fleet/remote tools only; it does not prove
    that the target exists, is enrolled, or is reachable.
    """
    if not isinstance(content, str):
        raise TypeError("content must be str")
    for pattern in _NAMED_MACHINE_HARDWARE:
        match = pattern.search(content)
        if (
            match is not None
            and match.group("target").casefold() not in _NON_MACHINE_SUBJECTS
            and match.group("target").casefold() not in {
                "local", "localhost", "this", "current", "my",
            }
        ):
            return True
    return False
