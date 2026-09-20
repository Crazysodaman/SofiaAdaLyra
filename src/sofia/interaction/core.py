"""Shared, headless semantics for text gestures and simulated avatar hits.

No renderer, physical sensing, UI authentication, or authorization is supplied
by this module. Its lab adapter is not an entry point for untrusted UI events.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from sofia.embodiment.model import Embodiment

REGISTRY_VERSION = "human-fox-interaction-v1"
GESTURES = frozenset({"pat", "tap", "touch", "stroke", "rub", "hold", "release", "poke"})
# Form-derived coverage is not a claim that a renderer has geometry for a region.
_SINGLE = (
    "head", "scalp", "hair", "forehead", "face", "nose", "mouth", "lips",
    "chin", "jaw", "neck", "throat", "chest", "torso", "back", "abdomen",
    "waist", "hips", "pelvis", "buttocks", "groin", "genitals",
)
_PAIRED = (
    "cheek", "shoulder", "upper-arm", "elbow", "forearm", "wrist", "hand",
    "palm", "finger", "thumb", "breast", "hip", "thigh", "inner-thigh",
    "knee", "shin", "calf", "ankle", "foot", "toe",
)
# Privacy metadata for redacted test exports only. This is NOT a denied-region
# set, a consent grant, a moral assessment, or an intimacy-mode permission.
_PRIVATE = frozenset({"chest", "breast", "buttocks", "groin", "genitals", "inner-thigh"})
_VERBS = {
    "pats": "pat", "pat": "pat", "patting": "pat",
    "taps": "tap", "tap": "tap", "tapping": "tap",
    "touches": "touch", "touch": "touch", "touching": "touch",
    "strokes": "stroke", "stroke": "stroke", "stroking": "stroke",
    "rubs": "rub", "rub": "rub", "rubbing": "rub",
    "holds": "hold", "hold": "hold", "holding": "hold",
    "releases": "release", "release": "release", "releasing": "release",
    "pokes": "poke", "poke": "poke", "poking": "poke",
}
_ACTION = re.compile(
    r"^(?:i\s+)?(?:(?:gently|softly|lightly|briefly)\s+)?"
    r"(?P<verb>" + "|".join(_VERBS) + r")\s+"
    r"(?:(?:your|her|sofia's|the)\s+)?(?P<region>[a-z -]+?)"
    r"(?:\s+(?:gently|softly|lightly|briefly))?[.!]?$",
    re.IGNORECASE,
)
_DISCUSSION = re.compile(
    r"\b(?:don't|do not|never|not|if|would|could|should|imagine|pretend|hypothetically)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Region:
    id: str
    origin: str  # 'human_form' or 'explicit_fox_anatomy'
    private: bool  # Redact anatomy in fixture exports, NEVER deny solely for it.


@dataclass(frozen=True)
class InteractionEvent:
    event_id: str
    session_id: str
    evidence_ref: str
    source: str  # user_text or virtual_lab, never an unverified real sensor
    actor: str
    region_id: str | None
    gesture: str
    phase: str
    occurred_at: datetime
    registry_version: str = REGISTRY_VERSION

    @property
    def semantics(self) -> tuple[str, str | None, str, str]:
        """Modality-independent meaning; provenance remains in separate fields."""
        return (self.actor, self.region_id, self.gesture, self.phase)


@dataclass(frozen=True)
class InteractionDecision:
    event: InteractionEvent
    status: str  # accepted (classified), denied (stopped), clarify, acknowledged
    reason: str
    emotion_options: tuple[str, ...] = ()
    text_cues: tuple[str, ...] = ()


class InteractionEngine:
    """Versioned regions, shared policy and optional expressive suggestions."""

    def __init__(self, embodiment: Embodiment) -> None:
        if not isinstance(embodiment, Embodiment):
            raise TypeError("Canonical Embodiment is required.")
        physical = embodiment.physical_self
        if physical.form.casefold() != "human":
            raise ValueError("No verified interaction registry for this embodiment form.")
        regions = [Region(name, "human_form", name in _PRIVATE) for name in _SINGLE]
        regions += [Region(f"{side}-{name}", "human_form", name in _PRIVATE)
                    for name in _PAIRED for side in ("left", "right")]
        features = set(physical.additional_features)
        anatomy = dict(physical.anatomy)
        if "fox ears" in features:
            if anatomy.get("ears") != "2 fox ears":
                raise ValueError("Fox ear anatomy and features disagree.")
            regions += [Region(name, "explicit_fox_anatomy", False)
                        for name in ("ears", "left-ear", "right-ear", "left-ear-base",
                                     "right-ear-base", "left-ear-tip", "right-ear-tip")]
        if "fox tail" in features:
            if anatomy.get("tail") != "1 fox tail":
                raise ValueError("Fox tail anatomy and features disagree.")
            regions += [Region(name, "explicit_fox_anatomy", False)
                        for name in ("tail", "tail-base", "tail-length", "tail-tip",
                                     "tail-left-side", "tail-right-side")]
        if features - {"fox ears", "fox tail"}:
            raise ValueError("Unmapped canonical additional features require a registry revision.")
        self.regions = {region.id: region for region in regions}

    def resolve_region(self, description: str) -> str | None:
        """Exact alias resolution only. Unspecified side remains ambiguous."""
        name = re.sub(r"\s+", "-", description.casefold().strip())
        name = {"head-pats": "head", "fox-ears": "ears", "fox-tail": "tail",
                "hands": "both-hands", "feet": "both-feet"}.get(name, name)
        if name in ("both-hands", "both-feet"):
            return None  # Group hit-testing needs an explicit future map.
        if name in self.regions:
            return name
        return None

    def _event(self, *, event_id: str, session_id: str, evidence_ref: str,
               source: str, actor: str, region_id: str | None, gesture: str,
               occurred_at: datetime, phase: str = "end") -> InteractionEvent:
        for label, value in (("event_id", event_id), ("session_id", session_id),
                             ("evidence_ref", evidence_ref)):
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError(f"{label} requires a bounded nonempty ID.")
        if actor not in ("user", "sofia"):
            raise ValueError("Actor must be explicitly resolved.")
        if gesture not in GESTURES or phase not in ("begin", "update", "end", "cancel"):
            raise ValueError("Unsupported gesture or phase.")
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("An aware event timestamp is required.")
        return InteractionEvent(event_id, session_id, evidence_ref, source, actor,
                                region_id, gesture, phase, occurred_at.astimezone(timezone.utc))

    def _decide(self, event: InteractionEvent, *, stopped: bool = False) -> InteractionDecision:
        region = self.regions.get(event.region_id)
        if stopped or event.phase == "cancel":
            return InteractionDecision(event, "denied", "Interaction stopped or cancelled.")
        if region is None:
            return InteractionDecision(event, "clarify", "Region is unknown or its side is ambiguous.")
        if event.phase != "end" or event.gesture == "release":
            return InteractionDecision(event, "acknowledged", "No completed contact or emotion inferred.")
        if "ear" in region.id:
            emotions, cues = ("curiosity", "surprise", "playfulness", "caution", "frustration"), ("*one ear flicks*", "*ears perk up*")
        elif "tail" in region.id:
            emotions, cues = ("fondness", "amusement", "caution", "curiosity", "frustration"), ("*tail swishes once*", "*tail curls closer*")
        elif "hand" in region.id or "palm" in region.id or "finger" in region.id:
            emotions, cues = ("appreciation", "curiosity", "caution", "frustration"), ("*a hand shifts slightly*",)
        elif region.private:
            # Privacy metadata never dictates the response. Positive, neutral
            # and negative possibilities remain available in every region.
            emotions, cues = ("fondness", "appreciation", "caution", "uncertainty", "bashfulness", "frustration"), ()
        else:
            emotions, cues = ("curiosity", "warmth", "caution", "surprise", "frustration"), ()
        return InteractionDecision(
            event, "accepted",
            "User-described virtual gesture classified; not approval, sensation or physical contact. Sofía may welcome, question or reject it in context.",
            emotions, cues,
        )

    def from_text(self, *, content: str, message_id: str, session_id: str,
                  occurred_at: datetime, stopped: bool = False) -> InteractionDecision | None:
        """Only complete, explicitly addressed action phrases are classified.

        General natural-language understanding remains a later parser adapter;
        discussing an action, quotes, code, negation and hypotheticals abstain.
        """
        if not isinstance(content, str):
            raise TypeError("Text must be a string.")
        text = content.strip()
        if not text or len(text) > 160 or "\n" in text or "`" in text or '"' in text or _DISCUSSION.search(text):
            return None
        if text.startswith("*") and text.endswith("*") and len(text) > 2:
            text = text[1:-1].strip()
        if re.fullmatch(r"head pats?[.!]?", text, re.IGNORECASE):
            verb, named = "pat", "head"
        else:
            match = _ACTION.fullmatch(text)
            if match is None:
                return None
            verb, named = _VERBS[match.group("verb").casefold()], match.group("region")
        region_id = self.resolve_region(named)
        event = self._event(event_id=f"interaction:{message_id}", session_id=session_id,
                            evidence_ref=message_id, source="user_text", actor="user",
                            region_id=region_id, gesture=verb, occurred_at=occurred_at)
        return self._decide(event, stopped=stopped)

    def from_lab_pointer(self, *, fixture_id: str, session_id: str, region_id: str | None,
                         gesture: str, occurred_at: datetime, phase: str = "end",
                         stopped: bool = False) -> InteractionDecision:
        """Synthetic resolved-hit fixture, NOT a real UI or click-to-pat classifier."""
        event = self._event(event_id=f"lab:{fixture_id}", session_id=session_id,
                            evidence_ref=fixture_id, source="virtual_lab", actor="user",
                            region_id=region_id, gesture=gesture, occurred_at=occurred_at,
                            phase=phase)
        return self._decide(event, stopped=stopped)
