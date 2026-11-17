"""Canonical Core profiles, asset loading and a generic Core registry.

Profiles are inert metadata.  They do not allocate an identity, grant
authority, install a component, or prove that voice/avatar assets exist.  A
caller must supply the Core UUID explicitly; no production UUID is embedded
here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from importlib.resources import files
import json
import math
from pathlib import Path
import re
from typing import Callable, Mapping
from uuid import UUID

from sofia.core.multicore.contracts import (
    AvatarMetadata,
    CoreDescriptor,
    VoiceMetadata,
)
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind

PERSONALITY_SCHEMA = "aegis.core.personality.v1"
AVATAR_SCHEMA = "aegis.core.avatar.v1"
VOICE_SCHEMA = "aegis.core.voice.v1"
CORE_ASSET_FILES = (
    "constitution.md",
    "personality.json",
    "avatar.json",
    "voice.json",
)
_SLUG = re.compile(r"[a-z][a-z0-9-]{0,63}")


class CoreProfileError(ValueError):
    """A canonical Core profile or package asset is invalid."""


class CoreProfileAlreadyRegistered(CoreProfileError):
    """The registry already contains this Core slug or number."""


class UnknownCoreProfile(KeyError):
    """No registered Core profile matches the requested slug or number."""


def _positive_finite(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CoreProfileError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise CoreProfileError(f"{label} must be positive and finite")
    return number


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise CoreProfileError(f"{label} must be a nonempty mapping")
    return value


def _text(value: object, label: str, *, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 0x20 and character not in "\n\t" for character in value)
    ):
        raise CoreProfileError(f"{label} must be bounded visible text")
    return value


def _tuple_text(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CoreProfileError(f"{label} must be a nonempty list")
    return tuple(_text(item, label, maximum=512) for item in value)


def _require_core_id(value: object) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError("an externally supplied nonzero Core UUID is required")
    return value


@dataclass(frozen=True, slots=True)
class CoreProfileSpec:
    """Stable package identity for one Core; metadata lives in its assets."""

    slug: str
    core_number: int
    full_name: str
    nickname: str | None
    gender: str
    presentation_species: str
    apparent_age: int
    identity_concept: str
    accessory: str | None = None
    required_measurements: Mapping[str, float] = field(default_factory=dict)
    required_pbr: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.slug, str) or _SLUG.fullmatch(self.slug) is None:
            raise CoreProfileError("Core profile slug must be a lowercase identifier")
        if type(self.core_number) is not int or self.core_number < 2:
            raise CoreProfileError("Core profile number must be an integer >= 2")
        _text(self.full_name, "full_name", maximum=160)
        if self.nickname is not None:
            _text(self.nickname, "nickname", maximum=160)
        _text(self.gender, "gender", maximum=64)
        _text(self.presentation_species, "presentation_species", maximum=128)
        if type(self.apparent_age) is not int or self.apparent_age < 1:
            raise CoreProfileError("apparent_age must be a positive integer")
        _text(self.identity_concept, "identity_concept", maximum=256)
        if self.accessory is not None:
            _text(self.accessory, "accessory", maximum=128)
        for label, values in (
            ("required_measurements", self.required_measurements),
            ("required_pbr", self.required_pbr),
        ):
            for name, value in values.items():
                if not isinstance(name, str) or not name:
                    raise CoreProfileError(f"{label} names must be text")
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise CoreProfileError(f"{label} values must be finite")

    @property
    def constitution_path(self) -> str:
        return f"cores/{self.slug}/constitution.md"

    @property
    def personality_path(self) -> str:
        return f"cores/{self.slug}/personality.json"


MACK_PROFILE = CoreProfileSpec(
    slug="mack",
    core_number=2,
    full_name="Mack Fuller",
    nickname="Mack",
    gender="Male",
    presentation_species="Human",
    apparent_age=34,
    identity_concept="The Frontier Gentleman",
)

NOVA_PROFILE = CoreProfileSpec(
    slug="nova",
    core_number=3,
    full_name="Nova Arden",
    nickname=None,
    gender="Female",
    presentation_species="Half-elf",
    apparent_age=27,
    identity_concept="The Unbound Scholar",
    accessory="Pendant",
    required_measurements={"bust": 31.25},
    required_pbr={"trim_metallic": 0.00},
)


@dataclass(frozen=True, slots=True)
class CoreProfile:
    """Validated canonical metadata plus truthful presentation availability."""

    spec: CoreProfileSpec
    descriptor: CoreDescriptor
    constitution_sha256: str
    constitution_size: int
    personality_sha256: str
    personality_size: int
    avatar_present: bool
    voice_present: bool

    @property
    def text_only(self) -> bool:
        """Text operation never depends on voice or avatar assets being present."""
        return True

    def core_definition(
        self, *, revision: int, runtime_release_sha256: str,
    ) -> CoreDefinition:
        core_id = self.descriptor.core_id
        if core_id is None:
            raise ValueError("Core profile descriptor has no supplied Core UUID")
        return CoreDefinition(
            identity=AegisIdentity(IdentityKind.CORE, core_id),
            name=self.descriptor.full_name,
            revision=revision,
            runtime_release_sha256=runtime_release_sha256,
            sdk_protocol=SDK_PROTOCOL_VERSION,
            constitution=CoreAssetReference(
                self.spec.constitution_path,
                self.constitution_sha256,
                self.constitution_size,
            ),
            personality=CoreAssetReference(
                self.spec.personality_path,
                self.personality_sha256,
                self.personality_size,
            ),
        )


def _asset_root(resource_root: Path | None):
    return files("sofia.core.cores") if resource_root is None else Path(resource_root)


def _read_bytes(root, *parts: str, required: bool) -> bytes | None:
    target = root.joinpath(*parts)
    try:
        if not target.is_file():
            if required:
                raise CoreProfileError(f"missing required Core asset: {'/'.join(parts)}")
            return None
        return target.read_bytes()
    except OSError as exc:
        raise CoreProfileError(f"Core asset is unreadable: {'/'.join(parts)}") from exc


def _read_json(
    root, *parts: str, required: bool,
) -> tuple[Mapping[str, object], bytes] | None:
    raw = _read_bytes(root, *parts, required=required)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CoreProfileError(f"Core asset is not valid UTF-8 JSON: {'/'.join(parts)}") from exc
    if not isinstance(value, Mapping):
        raise CoreProfileError(f"Core asset must be a JSON object: {'/'.join(parts)}")
    return value, raw


def _validate_personality(
    value: Mapping[str, object], spec: CoreProfileSpec,
) -> tuple[tuple[str, ...], tuple[str, ...], str, tuple[str, ...]]:
    if value.get("schema") != PERSONALITY_SCHEMA:
        raise CoreProfileError("unsupported personality asset schema")
    if value.get("core_number") != spec.core_number:
        raise CoreProfileError("personality asset belongs to another Core number")
    if value.get("full_name") != spec.full_name:
        raise CoreProfileError("personality asset full_name differs from the profile")
    if value.get("nickname") != spec.nickname:
        raise CoreProfileError("personality asset nickname differs from the profile")
    if value.get("identity_concept") != spec.identity_concept:
        raise CoreProfileError("personality asset identity_concept differs from the profile")
    traits = _tuple_text(value.get("traits"), "traits")
    motivations = _tuple_text(value.get("motivations"), "motivations")
    priorities = _tuple_text(
        value.get("constitutional_priorities"), "constitutional_priorities",
    )
    flaw = _text(value.get("character_flaw"), "character_flaw", maximum=1024)
    if "preference_states" in value:
        states = _tuple_text(value.get("preference_states"), "preference_states")
        expected = {
            "UNEXPLORED", "TENTATIVE", "DEVELOPING",
            "ESTABLISHED", "DORMANT", "REVISED",
        }
        if set(states) != expected:
            raise CoreProfileError("preference state vocabulary differs")
    if "hobbies" in value:
        hobbies = value.get("hobbies")
        if not isinstance(hobbies, Mapping) or hobbies.get("established") is not False:
            raise CoreProfileError("hobbies must remain explicitly unestablished")
    return traits, motivations, flaw, priorities


def _validate_avatar(
    value: Mapping[str, object], spec: CoreProfileSpec,
) -> AvatarMetadata:
    if value.get("schema") != AVATAR_SCHEMA:
        raise CoreProfileError("unsupported avatar asset schema")
    if value.get("core_number") != spec.core_number:
        raise CoreProfileError("avatar asset belongs to another Core number")
    age = value.get("age_years")
    if type(age) is not int or age != spec.apparent_age:
        raise CoreProfileError("avatar age differs from the profile apparent age")
    height = _positive_finite(value.get("height_inches"), "height_inches")
    weight = _positive_finite(value.get("weight_pounds"), "weight_pounds")
    head = _positive_finite(value.get("head_proportions"), "head_proportions")
    measurements = _mapping(value.get("measurements"), "measurements")
    normalized: dict[str, float] = {}
    for name, number in measurements.items():
        normalized[_text(name, "measurement name", maximum=160)] = _positive_finite(
            number, f"measurement {name}",
        )
    for name, expected in spec.required_measurements.items():
        if normalized.get(name) != expected:
            raise CoreProfileError(f"avatar measurement {name} must be exactly {expected}")
    colors = _mapping(value.get("colors"), "colors")
    materials = _mapping(value.get("materials"), "materials")
    pbr_value = _mapping(value.get("pbr"), "pbr")
    pbr: dict[str, float] = {}
    for name, number in pbr_value.items():
        if not isinstance(number, (int, float)) or isinstance(number, bool):
            raise CoreProfileError(f"pbr {name} must be numeric")
        pbr[_text(name, "pbr name", maximum=160)] = float(number)
    for name, expected in spec.required_pbr.items():
        if pbr.get(name) != expected:
            raise CoreProfileError(f"avatar pbr {name} must be exactly {expected}")
    accessory = value.get("accessory")
    if accessory is not None:
        _text(accessory, "accessory", maximum=128)
    if accessory != spec.accessory:
        raise CoreProfileError("avatar accessory differs from the profile")
    try:
        return AvatarMetadata(
            age_years=age,
            height_inches=height,
            weight_pounds=weight,
            build=_text(value.get("build"), "build", maximum=256),
            head_proportions=head,
            measurements=normalized,
            hair=_text(value.get("hair"), "hair", maximum=512),
            outfit=_text(value.get("outfit"), "outfit", maximum=512),
            default_expression=_text(
                value.get("default_expression"), "default_expression", maximum=512,
            ),
            colors=colors,
            materials=materials,
            pbr=pbr,
            accessory=accessory,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, CoreProfileError):
            raise
        raise CoreProfileError("avatar metadata is invalid") from exc


def _validate_voice(
    value: Mapping[str, object], spec: CoreProfileSpec,
) -> VoiceMetadata:
    if value.get("schema") != VOICE_SCHEMA:
        raise CoreProfileError("unsupported voice asset schema")
    if value.get("core_number") != spec.core_number:
        raise CoreProfileError("voice asset belongs to another Core number")
    if value.get("model_id") is not None:
        raise CoreProfileError("voice model must remain unselected")
    if value.get("assets_created") is not False:
        raise CoreProfileError("voice assets must not be claimed present")
    try:
        return VoiceMetadata(
            target=_text(value.get("target"), "voice target", maximum=512),
            register=_text(value.get("register"), "voice register", maximum=256),
            accent=(
                None if value.get("accent") is None
                else _text(value.get("accent"), "voice accent", maximum=256)
            ),
            cadence=_text(value.get("cadence"), "voice cadence", maximum=512),
            serious_delivery=_text(
                value.get("serious_delivery"), "voice serious_delivery", maximum=512,
            ),
            model_id=None,
            assets_created=False,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, CoreProfileError):
            raise
        raise CoreProfileError("voice metadata is invalid") from exc


def _text_only_avatar(spec: CoreProfileSpec) -> AvatarMetadata:
    """Neutral placeholder for text-only operation; not appearance evidence."""
    return AvatarMetadata(
        age_years=spec.apparent_age,
        height_inches=1.0,
        weight_pounds=1.0,
        build="text-only placeholder (no avatar asset)",
        head_proportions=1.0,
        measurements={},
        hair="unspecified (no avatar asset)",
        outfit="unspecified (no avatar asset)",
        default_expression="unspecified (no avatar asset)",
        colors={},
        materials={},
        pbr={},
        accessory=None,
    )


def _text_only_voice() -> VoiceMetadata:
    return VoiceMetadata(
        target="unselected (no voice asset)",
        register="unselected",
        accent=None,
        cadence="unselected",
        serious_delivery="unselected",
        model_id=None,
        assets_created=False,
    )


def load_core_profile(
    spec: CoreProfileSpec,
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    """Load and validate one profile using package resources by default."""
    if not isinstance(spec, CoreProfileSpec):
        raise TypeError("spec must be a CoreProfileSpec")
    supplied = _require_core_id(core_id)
    root = _asset_root(resource_root)
    constitution = _read_bytes(root, spec.slug, "constitution.md", required=True)
    assert constitution is not None
    try:
        constitution_text = constitution.decode("utf-8")
    except UnicodeError as exc:
        raise CoreProfileError("Core constitution must be UTF-8 text") from exc
    if not constitution_text.strip():
        raise CoreProfileError("Core constitution must be nonempty text")
    personality_raw = _read_json(root, spec.slug, "personality.json", required=True)
    assert personality_raw is not None
    personality, personality_bytes = personality_raw
    avatar_raw = _read_json(root, spec.slug, "avatar.json", required=False)
    voice_raw = _read_json(root, spec.slug, "voice.json", required=False)
    avatar_value = None if avatar_raw is None else avatar_raw[0]
    voice_value = None if voice_raw is None else voice_raw[0]
    if require_presentation_assets and (avatar_value is None or voice_value is None):
        raise CoreProfileError("avatar and voice metadata assets are required")
    traits, motivations, flaw, priorities = _validate_personality(personality, spec)
    avatar = (
        _text_only_avatar(spec) if avatar_value is None
        else _validate_avatar(avatar_value, spec)
    )
    voice = _text_only_voice() if voice_value is None else _validate_voice(voice_value, spec)
    try:
        descriptor = CoreDescriptor(
            core_number=spec.core_number,
            full_name=spec.full_name,
            nickname=spec.nickname,
            gender=spec.gender,
            presentation_species=spec.presentation_species,
            apparent_age=spec.apparent_age,
            identity_concept=spec.identity_concept,
            personality_traits=traits,
            motivations=motivations,
            character_flaw=flaw,
            constitutional_priorities=priorities,
            avatar=avatar,
            voice=voice,
            core_id=supplied,
        )
    except (TypeError, ValueError) as exc:
        raise CoreProfileError("Core descriptor metadata is invalid") from exc
    return CoreProfile(
        spec=spec,
        descriptor=descriptor,
        constitution_sha256=sha256(constitution).hexdigest(),
        constitution_size=len(constitution),
        personality_sha256=sha256(personality_bytes).hexdigest(),
        personality_size=len(personality_bytes),
        avatar_present=avatar_value is not None,
        voice_present=voice_value is not None,
    )


def mack_core_profile(
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    return load_core_profile(
        MACK_PROFILE, core_id,
        resource_root=resource_root,
        require_presentation_assets=require_presentation_assets,
    )


def nova_core_profile(
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    return load_core_profile(
        NOVA_PROFILE, core_id,
        resource_root=resource_root,
        require_presentation_assets=require_presentation_assets,
    )


def mack_core_descriptor(core_id: UUID, **options) -> CoreDescriptor:
    """Canonical Mack descriptor; the caller supplies the Core UUID."""
    return mack_core_profile(core_id, **options).descriptor


def nova_core_descriptor(core_id: UUID, **options) -> CoreDescriptor:
    """Canonical Nova descriptor; the caller supplies the Core UUID."""
    return nova_core_profile(core_id, **options).descriptor


ProfileBuilder = Callable[..., CoreProfile]


class CoreProfileRegistry:
    """Generic registry for current and future independent Cores."""

    def __init__(self) -> None:
        self._profiles: dict[str, CoreProfileSpec] = {}
        self._numbers: dict[int, str] = {}

    def register(self, spec: CoreProfileSpec) -> None:
        if not isinstance(spec, CoreProfileSpec):
            raise TypeError("spec must be a CoreProfileSpec")
        if spec.slug in self._profiles or spec.core_number in self._numbers:
            raise CoreProfileAlreadyRegistered(
                f"Core profile {spec.slug} / #{spec.core_number} is already registered"
            )
        self._profiles[spec.slug] = spec
        self._numbers[spec.core_number] = spec.slug

    def specs(self) -> tuple[CoreProfileSpec, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def resolve(self, selector: str | int) -> CoreProfileSpec:
        if isinstance(selector, int):
            slug = self._numbers.get(selector)
            if slug is None:
                raise UnknownCoreProfile(f"no Core profile registered for #{selector}")
            return self._profiles[slug]
        if not isinstance(selector, str):
            raise TypeError("Core profile selector must be a slug or number")
        spec = self._profiles.get(selector)
        if spec is None:
            raise UnknownCoreProfile(f"no Core profile registered for {selector!r}")
        return spec

    def create(
        self,
        selector: str | int,
        core_id: UUID,
        *,
        resource_root: Path | None = None,
        require_presentation_assets: bool = False,
    ) -> CoreProfile:
        return load_core_profile(
            self.resolve(selector),
            core_id,
            resource_root=resource_root,
            require_presentation_assets=require_presentation_assets,
        )

    def descriptor(self, selector: str | int, core_id: UUID, **options) -> CoreDescriptor:
        return self.create(selector, core_id, **options).descriptor


DEFAULT_CORE_PROFILES = CoreProfileRegistry()
DEFAULT_CORE_PROFILES.register(MACK_PROFILE)
DEFAULT_CORE_PROFILES.register(NOVA_PROFILE)


def create_core_profile(
    selector: str | int,
    core_id: UUID,
    **options,
) -> CoreProfile:
    """Create any registered profile; the UUID is always externally supplied."""
    return DEFAULT_CORE_PROFILES.create(selector, core_id, **options)


__all__ = [
    "AVATAR_SCHEMA",
    "CORE_ASSET_FILES",
    "CoreProfile",
    "CoreProfileAlreadyRegistered",
    "CoreProfileError",
    "CoreProfileRegistry",
    "CoreProfileSpec",
    "DEFAULT_CORE_PROFILES",
    "MACK_PROFILE",
    "NOVA_PROFILE",
    "PERSONALITY_SCHEMA",
    "VOICE_SCHEMA",
    "UnknownCoreProfile",
    "create_core_profile",
    "load_core_profile",
    "mack_core_descriptor",
    "mack_core_profile",
    "nova_core_descriptor",
    "nova_core_profile",
]
