"""User-facing output guards for cognitive responses."""
from __future__ import annotations

import re


_INTERNAL_REASONING_LEAK = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?"
    r"(?:analysis\s+of\s+the\s+tool\s+result|constitutional\s+evaluation|"
    r"personality\s+adaptation|strategic\s+intent|drafting\s+the\s+response)\b"
    r"|^\s*okay,?\s+i\s+see\s+the\s+tool\s+output\b"
    r"|^\s*let(?:'|’)s\s+analy[sz]e\b",
    re.IGNORECASE | re.MULTILINE,
)


def contains_internal_reasoning_leak(content: str) -> bool:
    """Return whether model output exposes scratch-work instead of a final answer."""
    if not isinstance(content, str):
        raise TypeError("content must be str")
    return _INTERNAL_REASONING_LEAK.search(content) is not None
