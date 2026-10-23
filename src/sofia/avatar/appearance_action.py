"""Bounded owner-conversation commands for reversible virtual appearance.

The existing AVATAR clothing handler calls this before wardrobe parsing.
Commands can change presentation only. They never modify canonical body,
private metadata, approval grants, or physical devices.
"""
from __future__ import annotations

from dataclasses import replace
import re

from sofia.platform.safe.operator_stop import OperatorStopStore

from .presentation import AppearanceState, PresentationError
from .presentation_runtime import PresentationRuntimeBundle


_STYLE = re.compile(
    r"^(?:please\s+)?(?:change|set|make)\s+(?:your\s+)?"
    r"(?P<part>hair(?:\s+color|\s+length|\s+style)?|hairstyle|"
    r"eye\s+color|eyes|posture|ear\s+pose|tail\s+pose|expression|"
    r"fur\s+style|makeup|freckles)\s+(?:to\s+)?(?P<target>.+)$",
    re.IGNORECASE,
)
_ADD = re.compile(
    r"^(?:please\s+)?(?:add|try|wear)\s+(?:a\s+|an\s+)?"
    r"(?P<item>tattoo|piercing)\s+(?:of\s+|on\s+|at\s+)?(?P<value>.+)$",
    re.IGNORECASE,
)
_CLEAR = re.compile(
    r"^(?:please\s+)?(?:remove|clear)\s+(?:your\s+|all\s+)?"
    r"(?P<item>tattoos?|piercings?)$",
    re.IGNORECASE,
)
_SAVE = re.compile(
    r"^(?:please\s+)?save\s+(?:this\s+)?(?:look|style)"
    r"\s+as\s+(?P<name>.+)$", re.IGNORECASE,
)
_LOAD = re.compile(
    r"^(?:please\s+)?(?:use|restore|load)\s+(?:your\s+)?"
    r"(?:favorite\s+)?(?:look|style)\s+(?P<name>.+)$", re.IGNORECASE,
)
_LIST = frozenset(("list your looks", "list your saved looks", "show your saved styles"))
_COLORS = {
    "black": "#171A21", "blue": "#4169E1", "cyan": "#19D3C5",
    "deep crimson": "#8B1E3F", "green": "#2EAD67", "pink": "#F080B2",
    "purple": "#8F5BDB", "red": "#D32F45", "violet": "#8F5BDB",
    "white": "#F1E9D8", "gold": "#E1B943", "amber": "#DB8C27",
}
_PARTS = {
    "hair": "hair_color", "hair color": "hair_color",
    "hair length": "hair_length", "hair style": "hairstyle",
    "hairstyle": "hairstyle", "eye color": "eye_color",
    "eyes": "eye_color", "posture": "posture",
    "ear pose": "ear_pose", "tail pose": "tail_pose",
    "expression": "expression", "fur style": "fur_style",
    "makeup": "makeup", "freckles": "freckles",
}


class AppearanceActionService:
    """No inference about anatomy; only explicit, reviewable cosmetics."""

    def __init__(
        self, bundle: PresentationRuntimeBundle,
        *, operator_stop_store: OperatorStopStore | None = None,
    ) -> None:
        if not isinstance(bundle, PresentationRuntimeBundle):
            raise TypeError("bundle must be PresentationRuntimeBundle")
        self.bundle = bundle
        self._stop = operator_stop_store

    def handle(self, *, content: str, operation_id: str) -> str | None:
        if not isinstance(content, str):
            raise TypeError("content must be text")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id required")
        text = " ".join(content.strip().rstrip(".!?").split())
        if not text:
            return None
        style = _STYLE.fullmatch(text)
        add = _ADD.fullmatch(text)
        clear = _CLEAR.fullmatch(text)
        save = _SAVE.fullmatch(text)
        load = _LOAD.fullmatch(text)
        listing = text.casefold() in _LIST
        if not any((style, add, clear, save, load, listing)):
            return None
        if self._stop is not None and self._stop.current().active:
            return "I can't change my appearance while the operator stop is active."
        authority = self.bundle.authority
        if authority.current.private_only:
            return "My current presentation is private. Please switch to a public outfit before changing or saving styles."
        current = authority.current.appearance
        if listing:
            names = tuple(self.bundle.store.list_style_favorites())
            return ("My saved looks: " + ", ".join(names) + ".") if names else "I haven't saved any looks yet."
        if save:
            name = save.group("name").strip()
            self.bundle.store.save_style_favorite(name=name, appearance=current)
            return f"I saved this reversible look as {name}."
        if load:
            name = load.group("name").strip()
            favorites = self.bundle.store.list_style_favorites()
            selected = favorites.get(name)
            if selected is None:
                return f"I don't have a saved look called {name}."
            desired = selected
            reason = "appearance:restore-favorite:" + name[:70]
        elif style:
            part = " ".join(style.group("part").lower().split())
            field = _PARTS[part]
            value = style.group("target").strip()
            if field in {"hair_color", "eye_color"}:
                named = _COLORS.get(value.casefold())
                if named is None and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is None:
                    return "Please choose a known color or give me a six-digit hex color."
                value = named or value
            if field == "freckles" and value.casefold() in ("none", "off"):
                value = "none"
            try:
                desired = replace(current, **{field: value})
            except PresentationError:
                return "That appearance value isn't supported."
            reason = "appearance:owner-request:" + field
        elif add:
            item = add.group("item").lower()
            value = add.group("value").strip()
            field = "tattoos" if item == "tattoo" else "piercings"
            existing = getattr(current, field)
            if value in existing:
                return "I already have that temporary decoration."
            try:
                desired = replace(current, **{field: existing + (value,)})
            except PresentationError:
                return "That temporary decoration isn't supported."
            reason = "appearance:owner-request:" + field
        else:
            field = "tattoos" if clear.group("item").lower().startswith("tattoo") else "piercings"
            desired = replace(current, **{field: ()})
            reason = "appearance:owner-request:clear-" + field
        if desired == current:
            return "I'm already using that appearance."
        def commit():
            authority.propose_appearance(
                operation_id=operation_id,
                expected_revision=authority.current.revision,
                appearance=desired,
                reason=reason,
            )
            return authority.commit_text(
                operation_id=operation_id,
                renderer_unavailable=True,
            )
        settled = self.bundle.store.persist_mutation(authority, commit)
        return (
            f"I saved my new appearance at revision {settled.revision}. "
            "Any visible animation still depends on the active renderer."
        )
