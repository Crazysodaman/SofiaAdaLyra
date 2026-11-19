"""Vera — Core #6 identity, assets, appearance autonomy and authority boundary.

Vera's canonical metadata is inert.  Loading these assets does not allocate an
identity, grant authority, install a component, or prove that voice or avatar
art exists.  The caller supplies Vera's UUID explicitly; no production UUID is
embedded here.  Callsign ``S-039`` is character metadata only, never a UUID or
security principal.

Autobiographical memory begins at real initialization.  Nothing in this module
manufactures service, childhood, battle, injury or relationship history.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from sofia.core.multicore.contracts import CoreDescriptor
from sofia.core.multicore.profiles import (
    CoreProfile,
    CoreProfileError,
    load_core_profile,
)
from sofia.core.vera.profile import VERA_PROFILE

VERA_CORE_NUMBER = 6
VERA_PERSONAL_NAME = "Vera"
VERA_CALLSIGN = "S-039"
VERA_SURNAME: None = None
VERA_GENDER = "Female"
VERA_APPARENT_AGE = 26
VERA_VISUAL_SPECIES = "Human"
VERA_PERSONA_CONCEPT = "Original Spartan-inspired character"
VERA_APPEARANCE_SCHEMA = "aegis.core.appearance.v1"
VERA_ASSET_FILES = (
    "constitution.md",
    "personality.json",
    "avatar.json",
    "voice.json",
)

VERA_MEASUREMENTS: Mapping[str, float] = MappingProxyType(
    dict(VERA_PROFILE.required_measurements)
)
VERA_HAIR_COLOR = "#2D170E"
VERA_EYE_COLOR = "#2D170E"
VERA_EYEBROW_COLOR = "#2D170E"
VERA_SKIN_COLOR = "#FFDFC4"
VERA_COLORS: Mapping[str, str] = MappingProxyType({
    "hair": VERA_HAIR_COLOR,
    "eyes": VERA_EYE_COLOR,
    "eyebrows": VERA_EYEBROW_COLOR,
    "skin": VERA_SKIN_COLOR,
})
VERA_HEIGHT_INCHES = 79.0
VERA_WEIGHT_POUNDS = 230.0
VERA_HAIR_LENGTH_INCHES = 4.0
VERA_VOICE_BREATHINESS = 16

VERA_ARMOR_HOOK: Mapping[str, object] = MappingProxyType({
    "owner": "Agent 3",
    "reference_only": True,
    "implementation": "external",
    "duplicated": False,
})


@dataclass(frozen=True, slots=True)
class VeraAuthorityBoundary:
    """Vera's non-negotiable authority posture.

    Responding and proposing are permitted.  Consequential execution, privilege
    or callsign impersonation, protected-memory access and self-granted
    authority are not.
    """

    can_respond: bool = True
    can_propose: bool = True
    can_execute: bool = False
    may_impersonate_privilege: bool = False
    can_access_protected_memory: bool = False
    can_self_grant_authority: bool = False
    inherits_constitution: bool = True
    uses_sofia_voice: bool = False

    def __post_init__(self) -> None:
        for name in (
            "can_respond",
            "can_propose",
            "can_execute",
            "may_impersonate_privilege",
            "can_access_protected_memory",
            "can_self_grant_authority",
            "inherits_constitution",
            "uses_sofia_voice",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not self.can_respond or not self.can_propose:
            raise ValueError("Vera must be able to respond and propose")
        if (
            self.can_execute
            or self.may_impersonate_privilege
            or self.can_access_protected_memory
            or self.can_self_grant_authority
            or not self.inherits_constitution
            or self.uses_sofia_voice
        ):
            raise ValueError("Vera's authority boundary cannot be weakened")


VERA_AUTHORITY = VeraAuthorityBoundary()


class VeraAppearanceError(ValueError):
    """A Vera appearance preference is invalid or unsupported."""


class VeraAppearanceAuthorityError(PermissionError):
    """A change exceeds the authority available for that appearance field."""


class AppearanceAuthority(str, Enum):
    SELF = "SELF"
    JOINT = "JOINT"


SELF_AUTHORITY_FIELDS = frozenset({
    "hair_part",
    "scar_position",
    "scar_style",
    "scar_count",
    "scar_dimensions",
    "scar_visibility",
    "materials",
    "avatar_format",
    "rigging",
    "facial_expression_system",
})
JOINT_AUTHORITY_FIELDS = frozenset({"voice", "wardrobe"})
APPEARANCE_FIELDS = SELF_AUTHORITY_FIELDS | JOINT_AUTHORITY_FIELDS

VERA_APPEARANCE_AUTHORITY: Mapping[str, AppearanceAuthority] = MappingProxyType({
    **{name: AppearanceAuthority.SELF for name in SELF_AUTHORITY_FIELDS},
    **{name: AppearanceAuthority.JOINT for name in JOINT_AUTHORITY_FIELDS},
})


def _text_or_none(value: object, label: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > 512
        or any(ord(character) < 0x20 for character in value)
    ):
        raise VeraAppearanceError(f"{label} must be bounded visible text or null")
    return value.strip()


def _materials(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise VeraAppearanceError("materials must be a mapping")
    normalized: dict[str, str] = {}
    for name, material in value.items():
        if not isinstance(name, str) or not name.strip():
            raise VeraAppearanceError("material names must be nonempty text")
        if not isinstance(material, str) or not material.strip():
            raise VeraAppearanceError("material values must be nonempty text")
        if any(ord(character) < 0x20 for character in name + material):
            raise VeraAppearanceError("materials cannot contain control characters")
        normalized[name] = material
    return MappingProxyType(normalized)


def _validate_appearance_value(name: str, value: object) -> object:
    if name == "materials":
        return _materials(value)
    if name == "scar_count":
        if value is None:
            return None
        if type(value) is not int or value < 1:
            raise VeraAppearanceError("scar_count must be a positive integer or null")
        return value
    return _text_or_none(value, name)


@dataclass(frozen=True, slots=True)
class VeraAppearancePreferences:
    """Versioned appearance state with SELF/JOINT change authority.

    Hair part, scar location/style and rendering/material choices belong to
    Vera.  Voice and further wardrobe changes require joint owner/Core approval.
    This record grants no execution authority and no security privilege.
    """

    revision: int = 1
    hair_part: str | None = None
    scar_position: str | None = None
    scar_style: str | None = None
    scar_count: int | None = None
    scar_dimensions: str | None = None
    scar_visibility: str | None = None
    materials: Mapping[str, str] = field(default_factory=dict)
    avatar_format: str | None = None
    rigging: str | None = None
    facial_expression_system: str | None = None
    voice: str | None = None
    wardrobe: str | None = None

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise VeraAppearanceError("appearance revision must be a positive integer")
        for name in APPEARANCE_FIELDS:
            validated = _validate_appearance_value(name, getattr(self, name))
            object.__setattr__(self, name, validated)

    @property
    def scars_assigned(self) -> bool:
        return any(
            getattr(self, name) is not None
            for name in (
                "scar_position",
                "scar_style",
                "scar_count",
                "scar_dimensions",
                "scar_visibility",
            )
        )

    @staticmethod
    def authority_for(field_name: str) -> AppearanceAuthority:
        try:
            return VERA_APPEARANCE_AUTHORITY[field_name]
        except KeyError as exc:
            raise VeraAppearanceError(
                f"{field_name!r} is not an appearance preference field"
            ) from exc

    def revise(
        self,
        *,
        authority: str | AppearanceAuthority,
        **changes: object,
    ) -> "VeraAppearancePreferences":
        """Return a new revision without mutating the current preferences."""
        try:
            level = AppearanceAuthority(authority)
        except ValueError as exc:
            raise VeraAppearanceAuthorityError(
                "authority must be SELF or JOINT"
            ) from exc
        if not changes:
            raise VeraAppearanceError("at least one appearance change is required")
        updates: dict[str, object] = {}
        for name, value in changes.items():
            if name == "revision":
                raise VeraAppearanceError("revision advances automatically")
            if name not in APPEARANCE_FIELDS:
                raise VeraAppearanceError(f"unknown appearance field: {name!r}")
            required = VERA_APPEARANCE_AUTHORITY[name]
            if required is AppearanceAuthority.JOINT and level is AppearanceAuthority.SELF:
                raise VeraAppearanceAuthorityError(
                    f"{name} requires joint owner/Core approval"
                )
            updates[name] = value
        if "materials" in updates:
            merged = dict(self.materials)
            merged.update(_materials(updates["materials"]))
            updates["materials"] = merged
        return replace(self, revision=self.revision + 1, **updates)


def _asset_root(resource_root: Path | None):
    return files("sofia.core") if resource_root is None else Path(resource_root)


def _read_asset_bytes(resource_root: Path | None, *parts: str) -> bytes:
    target = _asset_root(resource_root).joinpath(*parts)
    try:
        return target.read_bytes()
    except OSError as exc:
        raise VeraAppearanceError(
            "Vera asset is unreadable: " + "/".join(parts)
        ) from exc


def _read_asset_json(resource_root: Path | None, *parts: str) -> Mapping[str, object]:
    raw = _read_asset_bytes(resource_root, *parts)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VeraAppearanceError(
            "Vera asset is not valid UTF-8 JSON: " + "/".join(parts)
        ) from exc
    if not isinstance(value, Mapping):
        raise VeraAppearanceError(
            "Vera asset must be a JSON object: " + "/".join(parts)
        )
    return value


def load_vera_appearance_preferences(
    resource_root: Path | None = None,
) -> VeraAppearancePreferences:
    """Load Vera's initial versioned appearance state from her avatar asset."""
    avatar = _read_asset_json(resource_root, "vera", "avatar.json")
    block = avatar.get("appearance_preferences")
    if not isinstance(block, Mapping):
        raise VeraAppearanceError("avatar asset has no appearance preferences")
    if block.get("schema") != VERA_APPEARANCE_SCHEMA:
        raise VeraAppearanceError("unsupported appearance preference schema")
    unknown = set(block) - (APPEARANCE_FIELDS | {"schema", "revision"})
    if unknown:
        raise VeraAppearanceError(
            "unsupported appearance preference fields: " + ", ".join(sorted(unknown))
        )
    try:
        return VeraAppearancePreferences(
            revision=block.get("revision"),
            hair_part=block.get("hair_part"),
            scar_position=block.get("scar_position"),
            scar_style=block.get("scar_style"),
            scar_count=block.get("scar_count"),
            scar_dimensions=block.get("scar_dimensions"),
            scar_visibility=block.get("scar_visibility"),
            materials=block.get("materials", {}),
            avatar_format=block.get("avatar_format"),
            rigging=block.get("rigging"),
            facial_expression_system=block.get("facial_expression_system"),
            voice=block.get("voice"),
            wardrobe=block.get("wardrobe"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, VeraAppearanceError):
            raise
        raise VeraAppearanceError("appearance preferences are invalid") from exc


def initial_appearance_preferences(
    resource_root: Path | None = None,
) -> VeraAppearancePreferences:
    return load_vera_appearance_preferences(resource_root)


def vera_asset_digests(
    resource_root: Path | None = None,
) -> Mapping[str, str]:
    """SHA-256 digests for every Vera package asset, keyed by file name."""
    return MappingProxyType({
        name: sha256(
            _read_asset_bytes(resource_root, "vera", name)
        ).hexdigest()
        for name in VERA_ASSET_FILES
    })


def _assert_canonical_presentation(profile: CoreProfile) -> None:
    if not profile.avatar_present:
        return
    avatar = profile.descriptor.avatar
    if (
        avatar.height_inches != VERA_HEIGHT_INCHES
        or float(avatar.weight_pounds) != VERA_WEIGHT_POUNDS
    ):
        raise CoreProfileError("Vera avatar height or mass differs from canonical metadata")
    if dict(avatar.colors) != dict(VERA_COLORS):
        raise CoreProfileError("Vera avatar colors differ from canonical metadata")


def vera_core_profile(
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    """Canonical Vera profile; the caller always supplies the Core UUID."""
    profile = load_core_profile(
        VERA_PROFILE,
        core_id,
        resource_root=resource_root,
        require_presentation_assets=require_presentation_assets,
    )
    _assert_canonical_presentation(profile)
    return profile


def vera_core_descriptor(core_id: UUID, **options) -> CoreDescriptor:
    return vera_core_profile(core_id, **options).descriptor


__all__ = [
    "APPEARANCE_FIELDS",
    "AppearanceAuthority",
    "JOINT_AUTHORITY_FIELDS",
    "SELF_AUTHORITY_FIELDS",
    "VERA_APPEARANCE_AUTHORITY",
    "VERA_APPEARANCE_SCHEMA",
    "VERA_ARMOR_HOOK",
    "VERA_ASSET_FILES",
    "VERA_AUTHORITY",
    "VERA_CALLSIGN",
    "VERA_COLORS",
    "VERA_CORE_NUMBER",
    "VERA_EYE_COLOR",
    "VERA_EYEBROW_COLOR",
    "VERA_GENDER",
    "VERA_HAIR_COLOR",
    "VERA_HAIR_LENGTH_INCHES",
    "VERA_HEIGHT_INCHES",
    "VERA_MEASUREMENTS",
    "VERA_PERSONA_CONCEPT",
    "VERA_PERSONAL_NAME",
    "VERA_PROFILE",
    "VERA_SKIN_COLOR",
    "VERA_SURNAME",
    "VERA_VISUAL_SPECIES",
    "VERA_VOICE_BREATHINESS",
    "VERA_WEIGHT_POUNDS",
    "VeraAppearanceAuthorityError",
    "VeraAppearanceError",
    "VeraAppearancePreferences",
    "VeraAuthorityBoundary",
    "initial_appearance_preferences",
    "load_vera_appearance_preferences",
    "vera_asset_digests",
    "vera_core_descriptor",
    "vera_core_profile",
]
