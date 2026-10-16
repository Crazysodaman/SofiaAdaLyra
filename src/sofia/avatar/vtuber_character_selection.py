"""Deterministic choice of existing 2D face/fox sprite variants.

No facial anatomy mutation, gesture consent, synthetic sight/sensation, voice
activity inference, or new persistence. The compositor must draw only real
verified assets from the character-parts manifest and issue a frame receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .presentation import AudienceScope, PresentationProjection
from .vtuber_character_parts import character_part_options


@dataclass(frozen=True, slots=True)
class CharacterPartSelection:
    source_revision: int
    groups: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str]:
        return dict(self.groups)


def select_character_parts(
    presentation: PresentationProjection,
    *,
    expression: str = "neutral",
    gesture: str | None = None,
    talking: bool = False,
    gaze: str = "center",
    optional_freckles: bool = False,
) -> CharacterPartSelection:
    """Map trusted state to approved sprite IDs; no nonexistent variants."""
    if not isinstance(presentation, PresentationProjection):
        raise TypeError("trusted presentation projection required")
    if presentation.audience is not AudienceScope.PUBLIC:
        raise PermissionError("public head part selection requires public projection")
    if type(talking) is not bool or type(optional_freckles) is not bool:
        raise TypeError("talking and freckles must be real boolean state")
    if gaze not in ("center", "left", "right"):
        raise ValueError("unsupported gaze")
    if not isinstance(expression,str):
        raise TypeError("expression label required")
    appearance=presentation.appearance
    opts=character_part_options()
    warnings=[]

    haircut=(appearance.hairstyle or "").casefold().replace("_","-")
    if haircut in ("tied-back","ponytail","tied back","work ponytail"):
        hair="tied_back"
    elif haircut in ("long layered","long-layered","layered"):
        hair="long_layered"
    else:
        hair="long_layered"
        warnings.append("requested hairstyle has no verified sprite variation")

    if (appearance.hair_color or "").casefold() not in ("deep crimson", "#8b1e3f"):
        warnings.append("hair recolor needs verified colorized sprite")
    if (appearance.tail_color or "").casefold() not in ("dark violet", "#3a245c"):
        warnings.append("tail recolor needs verified colorized sprite")
    if (appearance.eye_color or "violet").casefold() not in (
        "violet", "#8f5bdb", "#793ec1",
    ):
        warnings.append("eye recolor needs verified iris sprite")

    if expression in ("skeptical","focused","annoyed"):
        brows="skeptical"
    else:
        brows="neutral"
    if talking:
        mouth="talk_small"
    elif expression in ("smile","happy","affectionate","playful"):
        mouth="smile"
    else:
        mouth="closed"

    if gesture in ("ear-perk","ear-flick"):
        ears="perked"
    elif gesture == "ear-flatten" or appearance.ear_pose in ("flattened","relaxed"):
        ears="relaxed"
        if gesture == "ear-flatten" or appearance.ear_pose == "flattened":
            warnings.append("fully flattened fox ears need another sprite")
    else:
        ears="perked"
    if gesture in ("tail-swish","slow-tail-sway","tail-flick"):
        tail="flick"
    elif appearance.tail_pose=="raised":
        tail="raised"
    else:
        tail="calm"
    eyes={
        "center":"open",
        "left":"looking_left",
        "right":"looking_right",
    }[gaze]
    if expression in ("sleepy","tired"):
        eyes="half"

    choices={
        "face":"neutral",
        "freckles":"on" if optional_freckles else "off",
        "eye_left":"closed" if expression == "wink" else eyes,
        "eye_right":eyes,
        "brow_left":brows,
        "brow_right":"neutral" if expression == "skeptical" else brows,
        "mouth":mouth,
        "hair_back":hair,
        "hair_front":hair,
        "ear_left":ears,
        "ear_right":ears,
        "tail":tail,
    }
    if set(choices)!=set(opts) or any(
        variant not in opts[group] for group,variant in choices.items()
    ):
        raise ValueError("visual character option has no authored sprite")
    return CharacterPartSelection(
        source_revision=presentation.source_revision,
        groups=tuple(sorted(choices.items())),
        warnings=tuple(warnings),
    )
