"""Versioned, side-effect-free catalog for Sofía's *represented* embodiment.

Vocabulary only: never contact, consent, emotion, animation, or background work.
The v1 runtime deliberately does not consume this v2 catalog yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping
import re

CATALOG_VERSION = "human-fox-interaction-catalog-v2"


def normalize_alias(value: str) -> str:
    """Normalize a complete name, never substring-match it within prose."""
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise ValueError("A nonempty alias of at most 120 characters is required.")
    text = value.casefold().replace("’", "'").strip()
    text = re.sub(r"[\s_-]+", " ", text)
    text = re.sub(r"^(?:(?:your|her|the|sofia's|sofía's) )+", "", text)
    text = re.sub(r"(?:'s|s')$", "", text).strip(" .!?,")
    if not text or re.search(r"[^\w\s'\-]", text):
        raise ValueError("Alias contains unsupported punctuation or is empty.")
    return text


@dataclass(frozen=True)
class Resolution:
    status: str  # resolved, ambiguous, unknown
    canonical_id: str | None = None
    candidates: tuple[str, ...] = ()
    version: str = CATALOG_VERSION


@dataclass(frozen=True)
class SemanticDefinition:
    id: str
    aliases: tuple[str, ...]
    category: str  # gesture, action, expression
    channel: str = "text"  # hint only, not an execution claim


# Explicit names preserve anatomical scope: chest != a particular breast.
# Multiple candidates mean genuine ambiguity, not a preferred answer.
_ANATOMY_ALIASES: Mapping[str, tuple[str, ...]] = {
    "tummy": ("abdomen",), "belly": ("abdomen",), "stomach": ("abdomen",),
    "brow": ("forehead",), "fore head": ("forehead",),
    "backside": ("buttocks",), "bottom": ("buttocks",),
    "boobs": ("left-breast", "right-breast"),
    "breasts": ("left-breast", "right-breast"),
    "breast": ("left-breast", "right-breast"),
    "ear": ("left-ear", "right-ear"),
    "fox ear": ("left-ear", "right-ear"),
    "both ears": ("ears",), "fox ears": ("ears",),
    "hand": ("left-hand", "right-hand"),
    "hands": ("left-hand", "right-hand"),
    "arm": ("left-upper-arm", "right-upper-arm", "left-forearm", "right-forearm"),
    "arms": ("left-upper-arm", "right-upper-arm", "left-forearm", "right-forearm"),
    "leg": ("left-thigh", "right-thigh", "left-calf", "right-calf", "left-shin", "right-shin"),
    "legs": ("left-thigh", "right-thigh", "left-calf", "right-calf", "left-shin", "right-shin"),
    "foot": ("left-foot", "right-foot"), "feet": ("left-foot", "right-foot"),
    "fox tail": ("tail",), "tail end": ("tail-tip",),
    "tail root": ("tail-base",), "tail middle": ("tail-length",),
    "left ear": ("left-ear",), "right ear": ("right-ear",),
    "left ear tip": ("left-ear-tip",), "right ear tip": ("right-ear-tip",),
    "left ear base": ("left-ear-base",), "right ear base": ("right-ear-base",),
    "left boob": ("left-breast",), "right boob": ("right-breast",),
    "left breast": ("left-breast",), "right breast": ("right-breast",),
    "left arm": ("left-upper-arm", "left-forearm"),
    "right arm": ("right-upper-arm", "right-forearm"),
    "left leg": ("left-thigh", "left-calf", "left-shin"),
    "right leg": ("right-thigh", "right-calf", "right-shin"),
    "left hand": ("left-hand",), "right hand": ("right-hand",),
    "left foot": ("left-foot",), "right foot": ("right-foot",),
}


def _definitions(category: str, entries: Mapping[str, tuple[str, ...]],
                 channel: str = "text") -> tuple[SemanticDefinition, ...]:
    return tuple(SemanticDefinition(name, aliases, category, channel)
                 for name, aliases in entries.items())


GESTURE_DEFINITIONS = _definitions("gesture", {
    "pat": ("pat", "patting", "patted"),
    "tap": ("tap", "tapping", "tapped"),
    "touch": ("touch", "touching", "touched"),
    "stroke": ("stroke", "stroking", "stroked"),
    "rub": ("rub", "rubbing", "rubbed"),
    "hold": ("hold", "holding", "held"),
    "release": ("release", "releasing", "let go"),
    "poke": ("poke", "poking", "poked"),
    "brush": ("brush", "brushing", "brushed"),
    "scratch": ("scratch", "scratching", "scratched"),
    "squeeze": ("squeeze", "squeezing", "squeezed"),
    "cup": ("cup", "cupping", "cupped"),
    "boop": ("boop", "booping", "booped"),
    "kiss": ("kiss", "kissing", "kissed"),
    "nuzzle": ("nuzzle", "nuzzling", "nuzzled"),
    "tickle": ("tickle", "tickling", "tickled"),
    "pinch": ("pinch", "pinching", "pinched"),
    "tug": ("tug", "tugging", "tugged"),
    "trace": ("trace", "tracing", "traced"),
    "caress": ("caress", "caressing", "caressed"),
    "grab": ("grab", "grabbing", "grabbed"),
    "massage": ("massage", "massaging", "massaged"),
    "intimate-touch": ("intimate touch",),  # Explicit only; never an unknown-verb fallback.
})

ACTION_DEFINITIONS = _definitions("action", {
    "hug": ("hug", "embrace"), "cuddle": ("cuddle", "snuggle"),
    "lean-on": ("lean on", "lean against"),
    "offer-hand": ("offer a hand", "offer my hand"),
    "take-hand": ("take a hand", "take your hand"),
    "hold-hands": ("hold hands",),
    "sit-beside": ("sit beside", "sit next to"),
    "sit-in-lap": ("sit in lap", "sit on lap"),
    "move-closer": ("move closer", "step closer"),
    "move-away": ("move away", "step away"),
    "give-space": ("give space", "back off"),
    "groom": ("groom", "brush fur"),
    "dress": ("get dressed", "dress"),
    "undress": ("get undressed", "undress"),
    "offer-tool": ("offer a tool", "hand over a tool"),
    "accept-tool": ("accept a tool", "take a tool"),
    "help-in-lab": ("help in the lab", "work together"),
    "ask-permission": ("ask permission", "ask first"),
    "decline": ("decline", "say no"),
})

EXPRESSION_DEFINITIONS = _definitions("expression", {
    "none": ("no expression", "still", "quiet"),
    "laugh": ("laugh", "laughing"), "chuckle": ("chuckle", "chuckling"),
    "giggle": ("giggle", "giggling"), "cry": ("cry", "crying"),
    "tear-up": ("tear up", "eyes well up"), "sob": ("sob", "sobbing"),
    "sniffle": ("sniffle", "sniffling"), "sigh": ("sigh", "sighing"),
    "gasp": ("gasp", "gasping"), "smile": ("smile", "smiling"),
    "grin": ("grin", "grinning"), "frown": ("frown", "frowning"),
    "blush": ("blush", "blushing"),
    "avert-gaze": ("avert gaze", "look away"),
    "pause": ("pause", "hesitate"),
    "speak-softly": ("speak softly", "lower voice"),
    "tremble": ("tremble", "trembling"),
    "ear-perk": ("ears perk", "perk ears"),
    "ear-flick": ("ear flick", "flick ears"),
    "ear-flatten": ("ears flatten", "flatten ears"),
    "tail-swish": ("tail swish", "swish tail"),
    "tail-curl": ("tail curl", "curl tail"),
    "tail-still": ("tail still", "still tail"),
    "shift-posture": ("shift posture", "shift weight"),
})

# Prospective emotion IDs. These do NOT mutate the current emotion journal.
EMOTION_EXTENSIONS = frozenset({
    "anger", "fear", "jealousy", "embarrassment", "humiliation",
    "sexual-arousal", "aversion", "disgust", "nervousness", "shame",
    "pride", "tenderness", "affectionate-uncertainty",
})


class InteractionCatalog:
    """Immutable, versioned vocabulary; does not execute or persist actions."""

    def __init__(self, region_ids: Iterable[str]) -> None:
        regions = frozenset(region_ids)
        if not regions or any(not isinstance(r, str) or not r for r in regions):
            raise ValueError("Canonical region IDs are required.")
        raw: dict[str, tuple[str, ...]] = {}
        for region in sorted(regions):
            alias = normalize_alias(region)
            if alias in raw and raw[alias] != (region,):
                raise ValueError(f"Canonical alias collision: {alias}")
            raw[alias] = (region,)
        # Every bilateral subregion gets an explicitly ambiguous unsided name
        # unless its canonical group already exists.
        for region in sorted(regions):
            if not region.startswith("left-"):
                continue
            stem = region.removeprefix("left-")
            right = f"right-{stem}"
            if right in regions:
                raw.setdefault(normalize_alias(stem), (region, right))
        for alias, targets in _ANATOMY_ALIASES.items():
            if not set(targets).issubset(regions):
                continue  # Conditional ears/tail and future body forms.
            name = normalize_alias(alias)
            existing = raw.get(name)
            if existing is not None and existing != targets:
                # Canonical names always win; never override a stable ID.
                continue
            raw[name] = targets
        self.region_ids = regions
        self.anatomy_aliases: Mapping[str, tuple[str, ...]] = MappingProxyType(raw)
        namespaces = {}
        for category, definitions in (
            ("gesture", GESTURE_DEFINITIONS),
            ("action", ACTION_DEFINITIONS),
            ("expression", EXPRESSION_DEFINITIONS),
        ):
            aliases: dict[str, str] = {}
            for definition in definitions:
                if definition.category != category:
                    raise ValueError("Semantic namespace mismatch.")
                for phrase in (definition.id, *definition.aliases):
                    key = normalize_alias(phrase)
                    if key in aliases and aliases[key] != definition.id:
                        raise ValueError(f"Ambiguous {category} alias: {phrase}")
                    aliases[key] = definition.id
            namespaces[category] = MappingProxyType(aliases)
        self.semantic_aliases: Mapping[str, Mapping[str, str]] = MappingProxyType(namespaces)

    def resolve_region(self, name: str) -> Resolution:
        targets = self.anatomy_aliases.get(normalize_alias(name), ())
        if not targets:
            return Resolution("unknown")
        if len(targets) > 1:
            return Resolution("ambiguous", candidates=targets)
        return Resolution("resolved", canonical_id=targets[0], candidates=targets)

    def resolve_semantic(self, category: str, name: str) -> Resolution:
        if category not in self.semantic_aliases:
            raise ValueError("Unknown semantic namespace.")
        semantic_id = self.semantic_aliases[category].get(normalize_alias(name))
        if semantic_id is None:
            return Resolution("unknown")
        return Resolution("resolved", canonical_id=semantic_id,
                          candidates=(semantic_id,))


def catalog_for_engine(engine: object) -> InteractionCatalog:
    """Read the existing engine's IDs without changing its parser or state."""
    return InteractionCatalog(getattr(engine, "regions"))
