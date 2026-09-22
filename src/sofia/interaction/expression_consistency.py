"""Conservative veto for explicit contradictions in one reviewed avatar offer.

This is deliberately NOT a semantic oracle. Ambiguous text must not become a
silent rewrite or an automatic yes; the supervised candidate fails closed.
The model's diagnostic reason is not authoritative evidence.
"""
from __future__ import annotations

import re

from sofia.interaction.decision_expression import CandidateChoice

# Only overt language that contradicts acceptance. A refusal after an apparent
# affirmative still vetoes the reply. Curly and straight apostrophes match.
_REFUSAL = re.compile(
    r"\b(?:not\s+(?:sure\s+(?:i(?:['’]m|\s+am)\s+)?ready|ready|comfortable|inclined)|"
    r"(?:i\s+)?(?:do\s+not|don['’]t|cannot|can['’]t|would\s+not|won['’]t)\s+"
    r"(?:want|accept|feel\s+ready|feel\s+comfortable)|"
    r"(?:i(?:['’]d|\s+would)\s+)?rather\s+not|"
    r"(?:i\s+)?prefer\s+(?:not\s+to|to\s+keep\s+(?:things|our\s+interaction))|"
    r"let(?:['’]s|\s+us)\s+keep\s+(?:things|our\s+interaction))\b",
    re.IGNORECASE,
)
_AFFIRMATIVE = re.compile(
    r"\b(?:yes|sure|of\s+course|go\s+ahead|please\s+do|"
    r"you\s+can\s+hug\s+me|i\s+accept\s+(?:your|the)\s+hug|"
    r"(?:i(?:['’]d|\s+would)\s+)?(?:love|welcome)\s+(?:a|your|the)\s+hug|"
    r"happy\s+to\s+accept|glad\s+to\s+accept)\b",
    re.IGNORECASE,
)
_EXPLICIT_ACCEPTANCE = re.compile(
    r"\b(?:yes\s*[,!.]?\s*(?:you\s+can\s+)?hug\s+me|"
    r"go\s+ahead\s+and\s+hug\s+me|"
    r"i\s+accept\s+(?:your|the)\s+hug|"
    r"you\s+can\s+hug\s+me)\b",
    re.IGNORECASE,
)


def validate_offer_expression(choice: CandidateChoice, response: str) -> None:
    """Reject obvious reversals; never invent a replacement response.

    Positive language alone does not establish genuine consent, and absence
    of these patterns does not prove consistency or grounding. The reviewed
    decision remains a candidate conversational choice only.
    """
    if not isinstance(choice, CandidateChoice) or choice.choice not in (
        'accept', 'decline', 'clarify', 'boundary',
    ) or not isinstance(response, str) or not response.strip():
        raise ValueError('A checked choice and nonempty expression are required.')
    if choice.choice == 'accept':
        if _REFUSAL.search(response) or not _AFFIRMATIVE.search(response):
            raise ValueError('Expression contradicts or fails to express checked acceptance.')
    elif _EXPLICIT_ACCEPTANCE.search(response):
        raise ValueError('Expression contradicts the checked non-acceptance choice.')
