"""Authoritative wardrobe state shared by avatar and text presentation.

This module coordinates logical wardrobe truth only. It does not render assets,
authenticate renderer receipts, generate prose, persist memory, or infer state
from user text. A trusted host must call the explicit acknowledgement methods
only after verifying renderer or text-fallback conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re

from .wardrobe import Garment, Outfit, Wardrobe, WardrobeError

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


class WardrobeStateError(ValueError):
    pass


class WardrobeStateConflict(RuntimeError):
    pass


class WardrobeStateDenied(PermissionError):
    pass


class PresentationMode(str, Enum):
    AVATAR_PRIMARY = "avatar_primary"
    TEXT_FALLBACK = "text_fallback"


class TransitionStatus(str, Enum):
    PENDING = "pending"
    RENDER_FAILED = "render_failed"


def _key(value: str, label: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise WardrobeStateError(f"invalid {label}")
    return value


@dataclass(frozen=True, slots=True)
class WardrobeState:
    revision: int
    item_ids: tuple[str, ...]
    coverage: frozenset[str]
    outfit_id: str | None
    presentation_mode: PresentationMode
    avatar_synced_revision: int | None

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise WardrobeStateError("revision must be a positive integer")
        if not isinstance(self.item_ids, tuple) or not all(isinstance(x, str) for x in self.item_ids):
            raise WardrobeStateError("item IDs must be a tuple of strings")
        if not isinstance(self.coverage, frozenset) or not all(isinstance(x, str) for x in self.coverage):
            raise WardrobeStateError("coverage must be a frozenset of strings")
        if self.outfit_id is not None:
            _key(self.outfit_id, "outfit ID")
        if not isinstance(self.presentation_mode, PresentationMode):
            raise WardrobeStateError("invalid presentation mode")
        if self.avatar_synced_revision is not None:
            if type(self.avatar_synced_revision) is not int or self.avatar_synced_revision < 1:
                raise WardrobeStateError("avatar synced revision must be positive")
            if self.avatar_synced_revision > self.revision:
                raise WardrobeStateError("avatar cannot be synced to a future revision")
        if self.presentation_mode is PresentationMode.AVATAR_PRIMARY:
            if self.avatar_synced_revision != self.revision:
                raise WardrobeStateError("avatar-primary state must be synced to current revision")
        elif self.avatar_synced_revision == self.revision:
            raise WardrobeStateError("text fallback cannot claim current avatar sync")

    @property
    def avatar_visible(self) -> bool:
        return (
            self.presentation_mode is PresentationMode.AVATAR_PRIMARY
            and self.avatar_synced_revision == self.revision
        )


@dataclass(frozen=True, slots=True)
class WardrobeChange:
    operation_id: str
    expected_revision: int
    item_ids: tuple[str, ...]
    coverage: frozenset[str]
    outfit_id: str | None
    status: TransitionStatus


@dataclass(frozen=True, slots=True)
class WardrobeItemProjection:
    """Stable clothing metadata for text grounding; no renderer authority."""

    item_id: str
    name: str
    layer: str
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    tail_clearance: bool
    ear_clearance: bool

    @classmethod
    def from_garment(cls, garment: Garment) -> "WardrobeItemProjection":
        return cls(
            item_id=garment.item_id,
            name=garment.name,
            layer=garment.layer.name.lower(),
            slots=garment.slots,
            coverage=garment.coverage,
            tail_clearance=garment.tail_clearance,
            ear_clearance=garment.ear_clearance,
        )


@dataclass(frozen=True, slots=True)
class WardrobeTextProjection:
    """Compact INTERACT-facing view; current and unresolved state stay separate."""

    revision: int
    current_item_ids: tuple[str, ...]
    current_items: tuple[WardrobeItemProjection, ...]
    current_outfit_id: str | None
    current_coverage: frozenset[str]
    presentation_mode: PresentationMode
    avatar_visible: bool
    pending_operation_id: str | None
    pending_item_ids: tuple[str, ...] | None
    pending_items: tuple[WardrobeItemProjection, ...] | None
    pending_outfit_id: str | None
    pending_status: TransitionStatus | None


class SharedWardrobeState:
    """One wardrobe authority with avatar-primary and text-fallback presentation.

    A requested outfit is never current until explicitly acknowledged. Avatar
    success commits the new state and marks that exact revision visually synced.
    If the renderer is unavailable or a render attempt failed, a trusted host may
    explicitly commit the same validated change in text-fallback mode. While in
    fallback, the avatar must remain hidden/non-body until sync_avatar() applies
    the current revision successfully.
    """

    def __init__(
        self,
        wardrobe: Wardrobe,
        *,
        initial_item_ids: tuple[str, ...],
        initial_outfit_id: str | None = None,
        initial_mode: PresentationMode = PresentationMode.TEXT_FALLBACK,
        avatar_initially_verified: bool = False,
    ) -> None:
        if not isinstance(wardrobe, Wardrobe):
            raise WardrobeStateError("wardrobe must be a Wardrobe")
        if not isinstance(initial_mode, PresentationMode):
            raise WardrobeStateError("invalid initial presentation mode")
        if type(avatar_initially_verified) is not bool:
            raise WardrobeStateError("avatar verification must be a strict boolean")
        outfit = self._validate_clothed_selection(wardrobe, initial_item_ids)
        if initial_outfit_id is not None:
            _key(initial_outfit_id, "outfit ID")
        if initial_mode is PresentationMode.AVATAR_PRIMARY and not avatar_initially_verified:
            raise WardrobeStateDenied("avatar-primary initialization requires verified visual state")
        self._wardrobe = wardrobe
        self._state = WardrobeState(
            revision=1,
            item_ids=outfit.item_ids,
            coverage=outfit.coverage,
            outfit_id=initial_outfit_id,
            presentation_mode=initial_mode,
            avatar_synced_revision=1 if initial_mode is PresentationMode.AVATAR_PRIMARY else None,
        )
        self._pending: WardrobeChange | None = None
        self._failed: dict[str, WardrobeChange] = {}
        self._finished: set[str] = set()

    @staticmethod
    def _validate_clothed_selection(wardrobe: Wardrobe, item_ids: tuple[str, ...]) -> Outfit:
        try:
            outfit = wardrobe.selection(item_ids)
        except (WardrobeError, RuntimeError) as error:
            raise WardrobeStateDenied("invalid wardrobe selection") from error
        if not outfit.covered_default:
            raise WardrobeStateDenied("normal shared wardrobe state must satisfy covered default")
        return outfit

    @property
    def state(self) -> WardrobeState:
        return self._state

    @property
    def pending(self) -> WardrobeChange | None:
        return self._pending

    def propose(
        self,
        *,
        operation_id: str,
        item_ids: tuple[str, ...],
        expected_revision: int,
        outfit_id: str | None = None,
    ) -> WardrobeChange:
        _key(operation_id, "operation ID")
        if operation_id in self._finished or operation_id in self._failed:
            raise WardrobeStateConflict("operation ID was already used")
        if self._pending is not None:
            raise WardrobeStateConflict("another wardrobe transition is pending")
        if self._failed:
            raise WardrobeStateConflict("failed wardrobe transition must be resolved or canceled")
        if type(expected_revision) is not int or expected_revision != self._state.revision:
            raise WardrobeStateConflict("stale wardrobe revision")
        if outfit_id is not None:
            _key(outfit_id, "outfit ID")
        outfit = self._validate_clothed_selection(self._wardrobe, item_ids)
        self._pending = WardrobeChange(
            operation_id, expected_revision, outfit.item_ids, outfit.coverage,
            outfit_id, TransitionStatus.PENDING,
        )
        return self._pending

    def acknowledge_avatar(
        self,
        *,
        operation_id: str,
        renderer_succeeded: bool,
        assets_verified: bool,
    ) -> WardrobeState:
        """Trusted adapter reports whether the proposed outfit actually rendered."""
        _key(operation_id, "operation ID")
        if type(renderer_succeeded) is not bool or type(assets_verified) is not bool:
            raise WardrobeStateDenied("renderer receipt fields must be strict booleans")
        change = self._require_pending(operation_id)
        if self._state.revision != change.expected_revision:
            raise WardrobeStateConflict("wardrobe state changed before acknowledgement")
        if renderer_succeeded and assets_verified:
            state = self._commit(change, PresentationMode.AVATAR_PRIMARY, avatar_synced=True)
            self._pending = None
            self._finished.add(operation_id)
            return state
        self._failed[operation_id] = replace(change, status=TransitionStatus.RENDER_FAILED)
        self._pending = None
        return self._state

    def acknowledge_text_fallback(
        self,
        *,
        operation_id: str,
        renderer_unavailable: bool,
    ) -> WardrobeState:
        """Commit one validated change while the avatar is unavailable/hidden."""
        _key(operation_id, "operation ID")
        if type(renderer_unavailable) is not bool or not renderer_unavailable:
            raise WardrobeStateDenied("text fallback requires trusted renderer-unavailable state")
        if self._pending is not None and self._pending.operation_id == operation_id:
            change = self._pending
            self._pending = None
        elif operation_id in self._failed:
            change = self._failed.pop(operation_id)
        else:
            raise WardrobeStateConflict("no matching pending or failed wardrobe transition")
        if self._state.revision != change.expected_revision:
            raise WardrobeStateConflict("cannot fallback a stale wardrobe transition")
        state = self._commit(change, PresentationMode.TEXT_FALLBACK, avatar_synced=False)
        self._finished.add(operation_id)
        return state

    def cancel(self, *, operation_id: str) -> None:
        _key(operation_id, "operation ID")
        if self._pending is not None and self._pending.operation_id == operation_id:
            self._pending = None
            self._finished.add(operation_id)
            return
        if operation_id in self._failed:
            del self._failed[operation_id]
            self._finished.add(operation_id)
            return
        raise WardrobeStateConflict("no cancelable wardrobe transition")

    def sync_avatar(
        self,
        *,
        expected_revision: int,
        renderer_succeeded: bool,
        assets_verified: bool,
    ) -> WardrobeState:
        """Resynchronize a returning avatar to the already-authoritative outfit."""
        if type(expected_revision) is not int or expected_revision != self._state.revision:
            raise WardrobeStateConflict("stale avatar sync revision")
        if type(renderer_succeeded) is not bool or type(assets_verified) is not bool:
            raise WardrobeStateDenied("renderer sync fields must be strict booleans")
        if renderer_succeeded and assets_verified:
            self._state = replace(
                self._state,
                presentation_mode=PresentationMode.AVATAR_PRIMARY,
                avatar_synced_revision=self._state.revision,
            )
        else:
            self._state = replace(
                self._state,
                presentation_mode=PresentationMode.TEXT_FALLBACK,
                avatar_synced_revision=None,
            )
        return self._state

    def force_text_fallback(self, *, renderer_unavailable: bool) -> WardrobeState:
        """Hide an unavailable/stale avatar without changing current clothes."""
        if type(renderer_unavailable) is not bool or not renderer_unavailable:
            raise WardrobeStateDenied("fallback requires trusted renderer-unavailable state")
        self._state = replace(
            self._state,
            presentation_mode=PresentationMode.TEXT_FALLBACK,
            avatar_synced_revision=None,
        )
        return self._state

    def text_projection(self) -> WardrobeTextProjection:
        unresolved = self._pending
        if unresolved is None and self._failed:
            unresolved = next(iter(self._failed.values()))
        current_items = tuple(
            WardrobeItemProjection.from_garment(item)
            for item in self._wardrobe.garments(self._state.item_ids)
        )
        pending_items = None
        if unresolved is not None:
            pending_items = tuple(
                WardrobeItemProjection.from_garment(item)
                for item in self._wardrobe.garments(unresolved.item_ids)
            )
        return WardrobeTextProjection(
            revision=self._state.revision,
            current_item_ids=self._state.item_ids,
            current_items=current_items,
            current_outfit_id=self._state.outfit_id,
            current_coverage=self._state.coverage,
            presentation_mode=self._state.presentation_mode,
            avatar_visible=self._state.avatar_visible,
            pending_operation_id=unresolved.operation_id if unresolved else None,
            pending_item_ids=unresolved.item_ids if unresolved else None,
            pending_items=pending_items,
            pending_outfit_id=unresolved.outfit_id if unresolved else None,
            pending_status=unresolved.status if unresolved else None,
        )

    def snapshot(self) -> dict[str, object]:
        if self._pending is not None or self._failed:
            raise WardrobeStateConflict("cannot snapshot with unresolved wardrobe transition")
        return {
            "schema": 1,
            "revision": self._state.revision,
            "item_ids": list(self._state.item_ids),
            "coverage": sorted(self._state.coverage),
            "outfit_id": self._state.outfit_id,
            "presentation_mode": self._state.presentation_mode.value,
            "avatar_synced_revision": self._state.avatar_synced_revision,
            "finished": sorted(self._finished),
        }

    def _require_pending(self, operation_id: str) -> WardrobeChange:
        if self._pending is None or self._pending.operation_id != operation_id:
            raise WardrobeStateConflict("no matching pending wardrobe transition")
        return self._pending

    def _commit(
        self,
        change: WardrobeChange,
        mode: PresentationMode,
        *,
        avatar_synced: bool,
    ) -> WardrobeState:
        revision = self._state.revision + 1
        self._state = WardrobeState(
            revision=revision,
            item_ids=change.item_ids,
            coverage=change.coverage,
            outfit_id=change.outfit_id,
            presentation_mode=mode,
            avatar_synced_revision=revision if avatar_synced else None,
        )
        return self._state
