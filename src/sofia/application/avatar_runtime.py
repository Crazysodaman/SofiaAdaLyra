"""Production bridge for background avatar presentation decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.avatar.appearance_routine import HeadlessAppearanceRoutine
from sofia.avatar.interact_bridge import (
    HostEnvironmentEvidence,
    InteractionBridgeError,
)
from sofia.avatar.presentation_routine import HeadlessPresentationRoutine
from sofia.avatar.runtime_state import PresentationRuntimeBundle
from sofia.avatar.wardrobe_routine import (
    Activity,
    EmotionStyleInfluence,
    OutfitPlanner,
    WardrobeContext,
)
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.runtime.runtime import SofiaRuntime


_STYLE_TAGS = {
    "contentment": ("relaxed", "soft", "warm"),
    "comfort": ("relaxed", "soft", "warm", "cozy"),
    "calmness": ("relaxed", "quiet", "composed"),
    "nostalgia": ("soft", "quiet", "warm"),
    "loneliness": ("quiet", "soft"),
    "hurt": ("quiet", "soft"),
    "irritation": ("practical", "focused"),
    "awkwardness": ("quiet", "composed"),
    "warmth": ("relaxed", "soft", "warm"),
    "fondness": ("relaxed", "soft", "warm"),
    "affection": ("soft", "warm"),
    "tenderness": ("soft", "warm", "elegant"),
    "romance": ("soft", "elegant"),
    "playfulness": ("playful", "bright", "relaxed"),
    "amusement": ("playful", "bright"),
    "joy": ("bright", "playful"),
    "excitement": ("bright", "playful"),
    "determination": ("technical", "focused", "practical"),
    "curiosity": ("technical", "focused"),
    "reflection": ("quiet", "composed"),
    "uncertainty": ("quiet", "composed"),
    "concern": ("quiet", "practical"),
    "sadness": ("quiet", "soft"),
    "frustration": ("practical", "technical"),
    "anger": ("practical", "technical"),
    "sensuality": ("soft", "elegant"),
    "sexual-attraction": ("soft", "elegant"),
    "sexual-desire": ("soft", "elegant"),
    "sexual-arousal": ("soft", "elegant"),
}


class AvatarBackgroundPresentation:
    """Evaluate covered outfit and hairstyle from current trusted context."""

    def __init__(
        self,
        *,
        runtime: SofiaRuntime,
        conversation: EmotionalConversationService,
        bundle: PresentationRuntimeBundle,
    ) -> None:
        if not isinstance(runtime, SofiaRuntime):
            raise TypeError("runtime must be SofiaRuntime")
        if not isinstance(conversation, EmotionalConversationService):
            raise TypeError(
                "conversation must be EmotionalConversationService"
            )
        if not isinstance(bundle, PresentationRuntimeBundle):
            raise TypeError("bundle must be PresentationRuntimeBundle")
        self.runtime = runtime
        self.conversation = conversation
        self.bundle = bundle
        self.outfits = HeadlessPresentationRoutine(
            authority=bundle.authority,
            store=bundle.store,
            planner=OutfitPlanner(
                bundle.catalog.wardrobe,
                bundle.catalog.presets,
            ),
        )
        self.appearance = HeadlessAppearanceRoutine(
            authority=bundle.authority,
            store=bundle.store,
        )

    def _emotion_influences(
        self,
        *,
        now: datetime,
    ) -> tuple[EmotionStyleInfluence, ...]:
        state = self.conversation.current_emotional_state(now=now)
        result: list[EmotionStyleInfluence] = []
        for active in state.active:
            tags = _STYLE_TAGS.get(active.name)
            if tags is None:
                continue
            refs = active.evidence_refs or active.event_ids
            if not refs:
                continue
            result.append(
                EmotionStyleInfluence(
                    emotion=active.name,
                    intensity=active.intensity,
                    style_tags=tags,
                    evidence_refs=tuple(refs),
                )
            )
        return tuple(result)

    def run_once(
        self,
        *,
        now: datetime,
    ) -> str:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        snapshot = self.runtime.environment_service.snapshot(
            now=moment,
            refresh_providers=True,
        )
        try:
            environment = HostEnvironmentEvidence.from_environment_snapshot(
                snapshot,
                activity=Activity.CONVERSATION,
            )
        except InteractionBridgeError:
            return "avatar_context_unavailable"

        base = environment.planner_context()
        context = WardrobeContext(
            now=base.now,
            season=base.season,
            activity=base.activity,
            weather=base.weather,
            emotion_influences=self._emotion_influences(now=moment),
        )
        slot = moment.strftime("%Y%m%dT%H")
        outfit = self.outfits.evaluate(
            context,
            operation_id=f"background.outfit.{slot}",
        )
        hair = self.appearance.evaluate(
            context,
            operation_id=f"background.hair.{slot}",
        )
        if outfit.deferred_private or hair.deferred_private:
            return "avatar_private_deferred"
        if outfit.changed and hair.changed:
            return "avatar_outfit_and_hair_changed"
        if outfit.changed:
            return "avatar_outfit_changed"
        if hair.changed:
            return "avatar_hair_changed"
        return "avatar_unchanged"
