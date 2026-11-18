"""Additive gesture-class bridge over the existing interaction registry.

The legacy catalog remains the canonical alias vocabulary and is never rewritten
here.  This module declares which existing or newly reviewed entries are
universal, anatomy-specific or personal, and builds inert ``GestureDefinition``
objects for compatibility checks.  Registering a declaration changes no legacy
parser, engine, region map or runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from sofia.modules.interaction import registry as legacy
from sofia.sdk.core_capabilities import BodyCapability, RendererCapability
from sofia.sdk.gesture_contract import (
    GestureClass,
    GestureDefinition,
    GestureError,
    GestureParty,
    GesturePrivacy,
)

CATEGORIES = ("gesture", "action", "expression", "pose", "presentation")

_LEGACY_DEFINITIONS = {
    "gesture": legacy.GESTURE_DEFINITIONS,
    "action": legacy.ACTION_DEFINITIONS,
    "expression": legacy.EXPRESSION_DEFINITIONS,
    "pose": legacy.POSE_DEFINITIONS,
    "presentation": legacy.PRESENTATION_DEFINITIONS,
}

_ANATOMY_EXPRESSIONS: Mapping[str, tuple[BodyCapability, ...]] = {
    "ear-perk": (BodyCapability.FOX_EARS,),
    "ear-flick": (BodyCapability.FOX_EARS,),
    "ear-flatten": (BodyCapability.FOX_EARS,),
    "tail-swish": (BodyCapability.FOX_TAIL,),
    "tail-curl": (BodyCapability.FOX_TAIL,),
    "tail-still": (BodyCapability.FOX_TAIL,),
    "slow-tail-sway": (BodyCapability.FOX_TAIL,),
}

_UNIVERSAL_ADDITIONS: Mapping[str, tuple[str, ...]] = {
    "wave": ("waving",),
    "nod": ("nodding",),
    "shake-head": ("shake head", "shaking head"),
    "point": ("pointing",),
    "sit": ("sitting", "sit down"),
    "stand": ("standing", "stand up"),
    "walk": ("walking",),
    "handshake": ("hand shake",),
}


class GestureCatalogError(ValueError):
    """A bridge declaration collides with or contradicts legacy vocabulary."""


@dataclass(frozen=True, slots=True)
class RegistryGestureEntry:
    """One category-scoped declaration; the legacy namespace is preserved."""

    category: str
    canonical_id: str
    aliases: tuple[str, ...]
    gesture_class: GestureClass
    privacy: GesturePrivacy
    required_body: tuple[BodyCapability, ...]
    renderer_capabilities: tuple[RendererCapability, ...]
    provenance: str
    definition: GestureDefinition

    @property
    def key(self) -> tuple[str, str]:
        return (self.category, self.canonical_id)


def _validate_category(category: object) -> str:
    if not isinstance(category, str) or category not in CATEGORIES:
        raise GestureCatalogError("unsupported semantic category")
    return category


def _aliases(category: str, canonical_id: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    combined = [canonical_id, *aliases]
    normalized = []
    for phrase in combined:
        try:
            normalized.append(legacy.normalize_alias(phrase))
        except ValueError as exc:
            raise GestureCatalogError("legacy alias normalization failed") from exc
    return tuple(dict.fromkeys(normalized))


def _classification(
    category: str, canonical_id: str,
) -> tuple[GestureClass, tuple[BodyCapability, ...], GesturePrivacy]:
    if category == "expression" and canonical_id in _ANATOMY_EXPRESSIONS:
        return (
            GestureClass.ANATOMY_SPECIFIC,
            _ANATOMY_EXPRESSIONS[canonical_id],
            GesturePrivacy.PUBLIC,
        )
    privacy = (
        GesturePrivacy.ADULT_PRIVATE
        if (category, canonical_id) in legacy.PRIVATE_SEMANTICS
        else GesturePrivacy.PUBLIC
    )
    return GestureClass.UNIVERSAL, (BodyCapability.HUMAN_FORM,), privacy


def _definition(
    *,
    category: str,
    canonical_id: str,
    aliases: tuple[str, ...],
    gesture_class: GestureClass,
    privacy: GesturePrivacy,
    required_body: tuple[BodyCapability, ...],
    renderer_capabilities: tuple[RendererCapability, ...],
    provenance: str,
) -> GestureDefinition:
    return GestureDefinition(
        gesture_id=canonical_id,
        version=1,
        gesture_class=gesture_class,
        actor=GestureParty.any_core(),
        target=GestureParty.any_core(),
        required_body=required_body,
        renderer_capabilities=renderer_capabilities,
        privacy=privacy,
        provenance=provenance,
        aliases=aliases,
        semantic_parameters={"category": category},
    )


class InteractionGestureCatalog:
    """Additive, immutable-per-entry declaration layer over legacy aliases."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegistryGestureEntry] = {}
        self._aliases: dict[str, dict[str, str]] = {category: {} for category in CATEGORIES}
        for category in CATEGORIES:
            for definition in _LEGACY_DEFINITIONS[category]:
                gesture_class, required_body, privacy = _classification(
                    category, definition.id
                )
                self._register(
                    category=category,
                    canonical_id=definition.id,
                    aliases=definition.aliases,
                    gesture_class=gesture_class,
                    privacy=privacy,
                    required_body=required_body,
                    renderer_capabilities=(RendererCapability.TEXT,),
                    provenance=f"{legacy.CATALOG_VERSION}:{category}",
                )
        for canonical_id, aliases in _UNIVERSAL_ADDITIONS.items():
            self.declare(
                "gesture",
                canonical_id,
                aliases=aliases,
                gesture_class=GestureClass.UNIVERSAL,
                required_body=(BodyCapability.HUMAN_FORM,),
                renderer_capabilities=(RendererCapability.TEXT,),
                privacy=GesturePrivacy.PUBLIC,
                provenance="aegis.gesture.universal.v1",
            )

    def _register(
        self,
        *,
        category: str,
        canonical_id: str,
        aliases: tuple[str, ...],
        gesture_class: GestureClass,
        privacy: GesturePrivacy,
        required_body: tuple[BodyCapability, ...],
        renderer_capabilities: tuple[RendererCapability, ...],
        provenance: str,
    ) -> RegistryGestureEntry:
        normalize = _aliases(category, canonical_id, aliases)
        key = (category, canonical_id)
        if key in self._entries:
            raise GestureCatalogError("duplicate canonical gesture declaration")
        mapping = self._aliases[category]
        for alias in normalize:
            existing = mapping.get(alias)
            if existing is not None and existing != canonical_id:
                raise GestureCatalogError(
                    f"alias {alias!r} already names {existing!r}"
                )
        definition = _definition(
            category=category,
            canonical_id=canonical_id,
            aliases=tuple(normalize[1:]),
            gesture_class=gesture_class,
            privacy=privacy,
            required_body=required_body,
            renderer_capabilities=renderer_capabilities,
            provenance=provenance,
        )
        entry = RegistryGestureEntry(
            category=category,
            canonical_id=canonical_id,
            aliases=tuple(normalize[1:]),
            gesture_class=gesture_class,
            privacy=privacy,
            required_body=required_body,
            renderer_capabilities=renderer_capabilities,
            provenance=provenance,
            definition=definition,
        )
        self._entries[key] = entry
        for alias in normalize:
            mapping[alias] = canonical_id
        return entry

    def declare(
        self,
        category: str,
        canonical_id: str,
        *,
        aliases: tuple[str, ...] = (),
        gesture_class: GestureClass = GestureClass.PERSONAL,
        required_body: tuple[BodyCapability, ...] = (BodyCapability.HUMAN_FORM,),
        renderer_capabilities: tuple[RendererCapability, ...] = (RendererCapability.TEXT,),
        privacy: GesturePrivacy = GesturePrivacy.PUBLIC,
        provenance: str = "aegis.gesture.declared.v1",
    ) -> RegistryGestureEntry:
        """Declare an entry without editing or extending legacy ``registry``."""
        _validate_category(category)
        if not isinstance(gesture_class, GestureClass):
            raise GestureCatalogError("gesture_class must be a GestureClass")
        if not isinstance(privacy, GesturePrivacy):
            raise GestureCatalogError("privacy must be a GesturePrivacy")
        try:
            return self._register(
                category=category,
                canonical_id=canonical_id,
                aliases=aliases,
                gesture_class=gesture_class,
                privacy=privacy,
                required_body=required_body,
                renderer_capabilities=renderer_capabilities,
                provenance=provenance,
            )
        except GestureError as exc:
            raise GestureCatalogError("gesture declaration is invalid") from exc

    def resolve(self, category: str, name: str) -> str | None:
        """Exact alias resolution only; unknown names never remap to touch."""
        _validate_category(category)
        try:
            key = legacy.normalize_alias(name)
        except ValueError:
            return None
        return self._aliases[category].get(key)

    def aliases_for(self, category: str) -> Mapping[str, str]:
        _validate_category(category)
        return MappingProxyType(dict(self._aliases[category]))

    def entry(self, category: str, canonical_id: str) -> RegistryGestureEntry:
        _validate_category(category)
        try:
            return self._entries[(category, canonical_id)]
        except KeyError as exc:
            raise GestureCatalogError("gesture declaration does not exist") from exc

    def entries(self) -> tuple[RegistryGestureEntry, ...]:
        return tuple(
            self._entries[key] for key in sorted(self._entries)
        )

    def universal(self) -> tuple[RegistryGestureEntry, ...]:
        return tuple(
            entry for entry in self.entries()
            if entry.gesture_class is GestureClass.UNIVERSAL
        )

    def anatomy_specific(self) -> tuple[RegistryGestureEntry, ...]:
        return tuple(
            entry for entry in self.entries()
            if entry.gesture_class is GestureClass.ANATOMY_SPECIFIC
        )

    def personal(self) -> tuple[RegistryGestureEntry, ...]:
        return tuple(
            entry for entry in self.entries()
            if entry.gesture_class is GestureClass.PERSONAL
        )


DEFAULT_GESTURE_CATALOG = InteractionGestureCatalog()


def canonical_semantic_id(category: str, name: str) -> str | None:
    """Resolve through the unchanged legacy aliases plus additive declarations."""
    return DEFAULT_GESTURE_CATALOG.resolve(category, name)


def legacy_aliases(category: str) -> Mapping[str, str]:
    return DEFAULT_GESTURE_CATALOG.aliases_for(category)


__all__ = [
    "CATEGORIES",
    "DEFAULT_GESTURE_CATALOG",
    "GestureCatalogError",
    "InteractionGestureCatalog",
    "RegistryGestureEntry",
    "canonical_semantic_id",
    "legacy_aliases",
]
