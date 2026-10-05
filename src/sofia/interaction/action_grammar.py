"""Reviewed, non-executing whole-body/social action language classifier.

Only a complete, explicitly reviewed user-described action from a saved turn
qualifies. Supported forms include first-person sentences and a small reviewed
set of telegraphic forms such as "kisses you"; there is no open-ended catchall.
The resulting intent describes what the USER wrote, not a performed action,
Sofía's consent, physical presence or a user-authorized tool operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.interaction.registry import ACTION_DEFINITIONS, CATALOG_VERSION

_ACTIONS = frozenset(item.id for item in ACTION_DEFINITIONS)
_DISCUSSION = re.compile(r"\b(?:not|never|don't|would|could|should|if|imagine|pretend|hypothetically)\b", re.I)
_COMPOSITE = re.compile(r"\b(?:and|then|while|before|after|plus)\b|[;&]", re.I)
_ADDRESS = re.compile(r"^sof[ií]a,\s+", re.I)
# Each phrase is reviewed independently. No catchall `I <verb> you` fallback.
_PHRASES: dict[str, tuple[str, str]] = {
    'hug you': ('hug', 'described'),
    'embrace you': ('hug', 'described'),
    'cuddle you': ('cuddle', 'described'),
    'snuggle with you': ('cuddle', 'described'),
    'lean against you': ('lean-on', 'described'),
    'sit beside you': ('sit-beside', 'described'),
    'sit next to you': ('sit-beside', 'described'),
    'sit in your lap': ('sit-in-lap', 'described'),
    'move closer': ('move-closer', 'described'),
    'step closer': ('move-closer', 'described'),
    'move away': ('move-away', 'described'),
    'step away': ('move-away', 'described'),
    'give you space': ('give-space', 'described'),
    'offer you my hand': ('offer-hand', 'offered'),
    'offer my hand': ('offer-hand', 'offered'),
    'hold hands with you': ('hold-hands', 'described'),
    'pull you closer': ('pull-closer', 'described'),
    'draw you closer': ('pull-closer', 'described'),
    'rest my head on you': ('rest-head-on', 'described'),
    'kiss you': ('kiss', 'described'),
    'hold you close': ('hold-close', 'described'),
    'kiss your neck': ('kiss-neck', 'described'),
    'kiss your cheek': ('kiss-cheek', 'described'),
    'kiss your forehead': ('kiss-forehead', 'described'),
    # Explicit adult/private represented actions. Every phrase is exact and
    # reviewed; there is no sexual catchall or unknown-verb fallback.
    'strike a sensual pose for you': ('sensual-pose', 'described'),
    'flash my chest at you': ('flash-chest', 'described'),
    'press my breasts together for you': ('breast-press-pose', 'described'),
    'have sex with you': ('sexual-intercourse', 'described'),
    'ask to have sex with you': ('sexual-intercourse', 'offered'),
    'perform oral sex on you': ('oral-sex', 'described'),
    'ask to perform oral sex on you': ('oral-sex', 'offered'),
    'give you a blowjob': ('fellatio', 'described'),
    'ask to give you a blowjob': ('fellatio', 'offered'),
    'perform cunnilingus on you': ('cunnilingus', 'described'),
    'ask to perform cunnilingus on you': ('cunnilingus', 'offered'),
    'perform analingus on you': ('analingus', 'described'),
    'ask to perform analingus on you': ('analingus', 'offered'),
    'have anal sex with you': ('anal-sex', 'described'),
    'ask to have anal sex with you': ('anal-sex', 'offered'),
    'have vaginal sex with you': ('vaginal-sex', 'described'),
    'ask to have vaginal sex with you': ('vaginal-sex', 'offered'),
    'manually stimulate your genitals': (
        'manual-genital-stimulation', 'described',
    ),
    'ask to manually stimulate your genitals': (
        'manual-genital-stimulation', 'offered',
    ),
    'mutually masturbate with you': ('mutual-masturbation', 'described'),
    'ask to mutually masturbate with you': (
        'mutual-masturbation', 'offered',
    ),
    'rub my genitals against yours': ('genital-rubbing', 'described'),
    'ask to rub my genitals against yours': ('genital-rubbing', 'offered'),
    'offer you a tool': ('offer-tool', 'offered'),
    'help you in the lab': ('help-in-lab', 'offered'),
    'ask to hug you': ('hug', 'offered'),
    'ask to cuddle you': ('cuddle', 'offered'),
}
_TELEGRAPHIC_PHRASES: dict[str, tuple[str, str]] = {
    'hugs you': ('hug', 'described'),
    'embraces you': ('hug', 'described'),
    'cuddles you': ('cuddle', 'described'),
    'snuggles with you': ('cuddle', 'described'),
    'kisses you': ('kiss', 'described'),
    'holds you close': ('hold-close', 'described'),
}
if any(
    action_id not in _ACTIONS
    for action_id, _ in (*_PHRASES.values(), *_TELEGRAPHIC_PHRASES.values())
):
    raise RuntimeError('Action grammar refers to a missing catalog definition.')


@dataclass(frozen=True)
class ActionIntent:
    message_id: str
    actor: str
    target: str
    action_id: str
    modality: str  # described or offered; neither means executed
    registry_version: str = CATALOG_VERSION


def parse_user_action(content: str, *, message_id: str) -> ActionIntent | None:
    """Return None when language is not an exactly reviewed user action."""
    if not isinstance(content, str):
        raise TypeError('Action message must be text.')
    if not isinstance(message_id, str) or not message_id.strip() or len(message_id) > 120:
        raise ValueError('A bounded saved-message ID is required.')
    text = content.strip()
    if (not text or len(text) > 160 or any(c in text for c in ('\n', '\r', '`', '"', '?'))
            or text.startswith("'") or text.endswith("'") or _DISCUSSION.search(text)):
        return None
    if text.startswith('*') and text.endswith('*'):
        text = text[1:-1].strip()
    text = _ADDRESS.sub('', text)
    if _COMPOSITE.search(text):
        return None
    normalized_full = re.sub(
        r'\s+',
        ' ',
        text.casefold().strip(' .!'),
    ).strip()
    telegraphic = _TELEGRAPHIC_PHRASES.get(normalized_full)
    if telegraphic is not None:
        action_id, modality = telegraphic
        return ActionIntent(
            message_id,
            'user',
            'sofia',
            action_id,
            modality,
        )
    match = re.fullmatch(r'i\s+(.+?)[.!]?', text, re.I)
    if match is None:
        return None
    normalized = re.sub(r'\s+', ' ', match.group(1).casefold()).strip()
    resolved = _PHRASES.get(normalized)
    if resolved is None:
        return None
    action_id, modality = resolved
    return ActionIntent(message_id, 'user', 'sofia', action_id, modality)
