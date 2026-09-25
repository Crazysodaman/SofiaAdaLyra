"""Headless authoritative AVATAR presentation state.

This module models what Sofía is currently presenting without requiring a
renderer. It deliberately separates current private presentation from the
public/default fallback. Nude presentation is an adult, private semantic state,
not a sexual mode, consent signal, or permission grant.

Public/default fallback rule:
    use the last successfully committed DAILY CLOTHED presentation;
    if none exists, bootstrap from the configured canonical daily outfit.

Renderer/UI code may later consume this state, but cannot rewrite it merely by
displaying something.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import re

from .wardrobe import Wardrobe, WardrobeError

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\Z")


class PresentationError(ValueError):
    pass


class PresentationConflict(RuntimeError):
    pass


class PresentationDenied(PermissionError):
    pass


class AudienceScope(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class AttireMode(str, Enum):
    CLOTHED = "clothed"
    NUDE = "nude"


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise PresentationError(f"invalid {label}")
    return value


def _text(value: str, label: str, *, limit: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise PresentationError(f"invalid {label}")
    if any(ch in value for ch in "\r\n\x00"):
        raise PresentationError(f"{label} must be one line")
    return value.strip()


def _color(value: str, label: str) -> str:
    value = _text(value, label, limit=80)
    if value.startswith("#") and not _HEX.fullmatch(value):
        raise PresentationError(f"invalid {label}")
    return value


@dataclass(frozen=True, slots=True)
class PrivatePresentationGrant:
    """Trusted host facts required before private presentation may be exposed."""

    adult_verified: bool
    owner_verified: bool
    private_session: bool
    explicit_current_opt_in: bool
    external_stop_active: bool = False

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in (
            self.adult_verified,
            self.owner_verified,
            self.private_session,
            self.explicit_current_opt_in,
            self.external_stop_active,
        )):
            raise PresentationError("private presentation facts must be booleans")

    def require(self) -> None:
        if (
            not self.adult_verified
            or not self.owner_verified
            or not self.private_session
            or not self.explicit_current_opt_in
            or self.external_stop_active
        ):
            raise PresentationDenied("private presentation is not authorized")


@dataclass(frozen=True, slots=True)
class AppearanceState:
    hairstyle: str
    hair_color: str
    tail_color: str
    style_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.hairstyle, "hairstyle")
        _color(self.hair_color, "hair color")
        _color(self.tail_color, "tail color")
        if (
            not isinstance(self.style_tags, tuple)
            or len(set(self.style_tags)) != len(self.style_tags)
            or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 64
                    for tag in self.style_tags)
        ):
            raise PresentationError("invalid style tags")


@dataclass(frozen=True, slots=True)
class PresentationState:
    revision: int
    attire: AttireMode
    outfit_id: str | None
    item_ids: tuple[str, ...]
    appearance: AppearanceState
    private_only: bool
    reason: str

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise PresentationError("revision must be positive")
        if not isinstance(self.attire, AttireMode):
            raise PresentationError("invalid attire mode")
        if not isinstance(self.appearance, AppearanceState):
            raise PresentationError("invalid appearance")
        if type(self.private_only) is not bool:
            raise PresentationError("private_only must be boolean")
        _text(self.reason, "presentation reason", limit=240)
        if not isinstance(self.item_ids, tuple) or any(
            not isinstance(item, str) for item in self.item_ids
        ):
            raise PresentationError("item_ids must be a tuple of strings")
        if self.attire is AttireMode.NUDE:
            if self.outfit_id is not None or self.item_ids:
                raise PresentationError("nude state cannot contain garments")
            if not self.private_only:
                raise PresentationError("nude presentation must be private-only")
        else:
            if self.outfit_id is None:
                raise PresentationError("clothed presentation requires outfit_id")
            _id(self.outfit_id, "outfit ID")
            if not self.item_ids:
                raise PresentationError("clothed presentation requires garments")


@dataclass(frozen=True, slots=True)
class PresentationChange:
    operation_id: str
    expected_revision: int
    attire: AttireMode
    outfit_id: str | None
    item_ids: tuple[str, ...]
    appearance: AppearanceState
    private_only: bool
    daily: bool
    reason: str


@dataclass(frozen=True, slots=True)
class PresentationProjection:
    """Audience-safe view of one authoritative presentation history."""

    audience: AudienceScope
    source_revision: int
    attire: AttireMode
    outfit_id: str | None
    item_ids: tuple[str, ...]
    appearance: AppearanceState
    private_fallback_used: bool
    reason: str


class PresentationAuthority:
    """Revisioned headless presentation authority with safe audience fallback."""

    SCHEMA = "sofia.avatar.presentation.v1"

    def __init__(
        self,
        wardrobe: Wardrobe,
        *,
        outfits: dict[str, tuple[str, ...]],
        canonical_daily_outfit_id: str,
        initial_appearance: AppearanceState,
    ) -> None:
        if not isinstance(wardrobe, Wardrobe):
            raise PresentationError("wardrobe is required")
        if not isinstance(outfits, dict) or not outfits:
            raise PresentationError("outfits are required")
        if not isinstance(initial_appearance, AppearanceState):
            raise PresentationError("initial appearance is required")
        normalized: dict[str, tuple[str, ...]] = {}
        for outfit_id, item_ids in outfits.items():
            _id(outfit_id, "outfit ID")
            if not isinstance(item_ids, tuple):
                raise PresentationError("outfit item IDs must be tuples")
            outfit = wardrobe.selection(item_ids)
            if not outfit.covered_default:
                raise PresentationDenied("daily/public outfit must be covered")
            normalized[outfit_id] = outfit.item_ids
        _id(canonical_daily_outfit_id, "canonical daily outfit ID")
        if canonical_daily_outfit_id not in normalized:
            raise PresentationError("canonical daily outfit is unknown")

        self._wardrobe = wardrobe
        self._outfits = normalized
        self._canonical_daily_outfit_id = canonical_daily_outfit_id
        initial_items = normalized[canonical_daily_outfit_id]
        initial = PresentationState(
            revision=1,
            attire=AttireMode.CLOTHED,
            outfit_id=canonical_daily_outfit_id,
            item_ids=initial_items,
            appearance=initial_appearance,
            private_only=False,
            reason="canonical_daily_bootstrap",
        )
        self._current = initial
        self._last_daily = initial
        self._pending: PresentationChange | None = None
        self._finished: set[str] = set()

    @property
    def current(self) -> PresentationState:
        return self._current

    @property
    def last_daily(self) -> PresentationState:
        return self._last_daily

    @property
    def pending(self) -> PresentationChange | None:
        return self._pending

    def propose_outfit(
        self,
        *,
        operation_id: str,
        expected_revision: int,
        outfit_id: str,
        reason: str,
        appearance: AppearanceState | None = None,
        private_only: bool = False,
        daily: bool = True,
    ) -> PresentationChange:
        self._begin(operation_id, expected_revision)
        _id(outfit_id, "outfit ID")
        if outfit_id not in self._outfits:
            raise PresentationError("unknown outfit")
        if type(private_only) is not bool or type(daily) is not bool:
            raise PresentationError("presentation flags must be booleans")
        if private_only and daily:
            raise PresentationDenied("private presentation cannot replace daily public fallback")
        self._pending = PresentationChange(
            operation_id=operation_id,
            expected_revision=expected_revision,
            attire=AttireMode.CLOTHED,
            outfit_id=outfit_id,
            item_ids=self._outfits[outfit_id],
            appearance=appearance or self._current.appearance,
            private_only=private_only,
            daily=daily,
            reason=_text(reason, "change reason", limit=240),
        )
        return self._pending

    def propose_nude(
        self,
        *,
        operation_id: str,
        expected_revision: int,
        reason: str,
        grant: PrivatePresentationGrant,
        appearance: AppearanceState | None = None,
    ) -> PresentationChange:
        if not isinstance(grant, PrivatePresentationGrant):
            raise PresentationDenied("private presentation grant is required")
        grant.require()
        self._begin(operation_id, expected_revision)
        self._pending = PresentationChange(
            operation_id=operation_id,
            expected_revision=expected_revision,
            attire=AttireMode.NUDE,
            outfit_id=None,
            item_ids=(),
            appearance=appearance or self._current.appearance,
            private_only=True,
            daily=False,
            reason=_text(reason, "change reason", limit=240),
        )
        return self._pending

    def propose_appearance(
        self,
        *,
        operation_id: str,
        expected_revision: int,
        appearance: AppearanceState,
        reason: str,
    ) -> PresentationChange:
        if not isinstance(appearance, AppearanceState):
            raise PresentationError("appearance is required")
        self._begin(operation_id, expected_revision)
        self._pending = PresentationChange(
            operation_id=operation_id,
            expected_revision=expected_revision,
            attire=self._current.attire,
            outfit_id=self._current.outfit_id,
            item_ids=self._current.item_ids,
            appearance=appearance,
            private_only=self._current.private_only,
            daily=(
                self._current.attire is AttireMode.CLOTHED
                and not self._current.private_only
                and self._current.outfit_id == self._last_daily.outfit_id
            ),
            reason=_text(reason, "change reason", limit=240),
        )
        return self._pending

    def commit_text(
        self,
        *,
        operation_id: str,
        renderer_unavailable: bool,
        grant: PrivatePresentationGrant | None = None,
    ) -> PresentationState:
        if type(renderer_unavailable) is not bool or not renderer_unavailable:
            raise PresentationDenied("headless commit requires renderer-unavailable evidence")
        change = self._require_pending(operation_id)
        if change.private_only or change.attire is AttireMode.NUDE:
            if not isinstance(grant, PrivatePresentationGrant):
                raise PresentationDenied("private commit requires a grant")
            grant.require()
        if change.expected_revision != self._current.revision:
            raise PresentationConflict("presentation changed before commit")
        revision = self._current.revision + 1
        state = PresentationState(
            revision=revision,
            attire=change.attire,
            outfit_id=change.outfit_id,
            item_ids=change.item_ids,
            appearance=change.appearance,
            private_only=change.private_only,
            reason=change.reason,
        )
        self._current = state
        if change.daily:
            if state.attire is not AttireMode.CLOTHED or state.private_only:
                raise PresentationConflict("daily fallback must be public and clothed")
            self._last_daily = state
        self._pending = None
        self._finished.add(operation_id)
        return state

    def cancel(self, *, operation_id: str) -> None:
        _id(operation_id, "operation ID")
        if self._pending is None or self._pending.operation_id != operation_id:
            raise PresentationConflict("no matching pending presentation change")
        self._pending = None
        self._finished.add(operation_id)

    def projection(
        self,
        audience: AudienceScope,
        *,
        grant: PrivatePresentationGrant | None = None,
    ) -> PresentationProjection:
        if not isinstance(audience, AudienceScope):
            raise PresentationError("audience scope is required")
        state = self._current
        fallback = False
        if audience is AudienceScope.PUBLIC:
            if state.private_only or state.attire is AttireMode.NUDE:
                state = self._last_daily
                fallback = True
        else:
            if state.private_only or state.attire is AttireMode.NUDE:
                if not isinstance(grant, PrivatePresentationGrant):
                    state = self._last_daily
                    fallback = True
                else:
                    try:
                        grant.require()
                    except PresentationDenied:
                        state = self._last_daily
                        fallback = True
        return PresentationProjection(
            audience=audience,
            source_revision=state.revision,
            attire=state.attire,
            outfit_id=state.outfit_id,
            item_ids=state.item_ids,
            appearance=state.appearance,
            private_fallback_used=fallback,
            reason=state.reason,
        )

    def snapshot(self) -> dict[str, Any]:
        if self._pending is not None:
            raise PresentationConflict("cannot snapshot an unresolved change")
        return {
            "schema": self.SCHEMA,
            "canonical_daily_outfit_id": self._canonical_daily_outfit_id,
            "current": self._state_dict(self._current),
            "last_daily": self._state_dict(self._last_daily),
            "finished": sorted(self._finished),
        }

    @classmethod
    def restore(
        cls,
        wardrobe: Wardrobe,
        *,
        outfits: dict[str, tuple[str, ...]],
        snapshot: dict[str, Any],
    ) -> "PresentationAuthority":
        if not isinstance(snapshot, dict) or snapshot.get("schema") != cls.SCHEMA:
            raise PresentationError("unsupported presentation snapshot")
        canonical = snapshot.get("canonical_daily_outfit_id")
        current_data = snapshot.get("current")
        daily_data = snapshot.get("last_daily")
        if not isinstance(current_data, dict) or not isinstance(daily_data, dict):
            raise PresentationError("snapshot is incomplete")
        daily_appearance = cls._appearance_from_dict(daily_data.get("appearance"))
        authority = cls(
            wardrobe,
            outfits=outfits,
            canonical_daily_outfit_id=canonical,
            initial_appearance=daily_appearance,
        )
        current = authority._state_from_dict(current_data)
        daily = authority._state_from_dict(daily_data)
        if daily.attire is not AttireMode.CLOTHED or daily.private_only:
            raise PresentationDenied("restored daily fallback must be public and clothed")
        authority._validate_clothed_state(current)
        authority._validate_clothed_state(daily)
        if daily.revision > current.revision:
            raise PresentationError("daily fallback cannot be newer than current")
        finished = snapshot.get("finished", [])
        if not isinstance(finished, list) or any(not isinstance(x, str) for x in finished):
            raise PresentationError("invalid finished operation list")
        authority._current = current
        authority._last_daily = daily
        authority._finished = set(finished)
        return authority

    def _begin(self, operation_id: str, expected_revision: int) -> None:
        _id(operation_id, "operation ID")
        if operation_id in self._finished:
            raise PresentationConflict("operation ID was already used")
        if self._pending is not None:
            raise PresentationConflict("another presentation change is pending")
        if type(expected_revision) is not int or expected_revision != self._current.revision:
            raise PresentationConflict("stale presentation revision")

    def _require_pending(self, operation_id: str) -> PresentationChange:
        _id(operation_id, "operation ID")
        if self._pending is None or self._pending.operation_id != operation_id:
            raise PresentationConflict("no matching pending presentation change")
        return self._pending

    def _validate_clothed_state(self, state: PresentationState) -> None:
        if state.attire is AttireMode.CLOTHED:
            if state.outfit_id not in self._outfits:
                raise PresentationError("snapshot references unknown outfit")
            expected = self._outfits[state.outfit_id]
            if expected != state.item_ids:
                raise PresentationError("snapshot outfit items do not match catalog")

    @staticmethod
    def _state_dict(state: PresentationState) -> dict[str, Any]:
        return {
            "revision": state.revision,
            "attire": state.attire.value,
            "outfit_id": state.outfit_id,
            "item_ids": list(state.item_ids),
            "appearance": {
                "hairstyle": state.appearance.hairstyle,
                "hair_color": state.appearance.hair_color,
                "tail_color": state.appearance.tail_color,
                "style_tags": list(state.appearance.style_tags),
            },
            "private_only": state.private_only,
            "reason": state.reason,
        }

    @staticmethod
    def _appearance_from_dict(data: Any) -> AppearanceState:
        if not isinstance(data, dict):
            raise PresentationError("appearance snapshot is invalid")
        tags = data.get("style_tags", [])
        if not isinstance(tags, list):
            raise PresentationError("appearance style_tags must be a list")
        return AppearanceState(
            hairstyle=data.get("hairstyle"),
            hair_color=data.get("hair_color"),
            tail_color=data.get("tail_color"),
            style_tags=tuple(tags),
        )

    def _state_from_dict(self, data: dict[str, Any]) -> PresentationState:
        attire_raw = data.get("attire")
        try:
            attire = AttireMode(attire_raw)
        except (TypeError, ValueError) as exc:
            raise PresentationError("invalid snapshot attire") from exc
        item_ids = data.get("item_ids", [])
        if not isinstance(item_ids, list):
            raise PresentationError("snapshot item_ids must be a list")
        return PresentationState(
            revision=data.get("revision"),
            attire=attire,
            outfit_id=data.get("outfit_id"),
            item_ids=tuple(item_ids),
            appearance=self._appearance_from_dict(data.get("appearance")),
            private_only=data.get("private_only"),
            reason=data.get("reason"),
        )
