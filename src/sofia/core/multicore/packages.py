"""Versioned installable Core package manifests and an inert registry.

A package manifest is metadata only.  It describes one independent Core's
caller-supplied UUID, number, slug, descriptor, personal asset references,
declared lifecycle state and presentation availability.  Registering or
decoding a manifest never allocates an identity, installs a component, starts a
process, changes immutable identity fields, or grants authority/capabilities.

Signature verification and lifecycle evidence remain owned by the existing
:class:`sofia.platform.ops.core_definition.CoreDefinitionVerifier` and
:class:`sofia.platform.ops.synthetic_core_lifecycle.SyntheticCoreLifecycle`.
This module only adapts manifests to those existing interfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from threading import RLock
from typing import Iterable, Mapping
from uuid import UUID

from sofia.core.multicore.contracts import (
    AvatarMetadata,
    CoreDescriptor,
    LifecycleState,
    VoiceMetadata,
)
from sofia.core.multicore.lifecycle import (
    CoreDefinitionRegistration,
    MulticoreCoreLifecycle,
)
from sofia.core.multicore.profiles import CoreProfile, CoreProfileSpec
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components

CORE_PACKAGE_SCHEMA = "aegis.core.package_manifest.v1"
MAX_PACKAGE_MANIFEST_BYTES = 65_536
_PACKAGE_DOMAIN = b"aegis.core.package_manifest.v1\x00"
_SLUG = re.compile(r"[a-z][a-z0-9-]{0,63}")
_BLANK_LIFECYCLES = frozenset({
    LifecycleState.DEFINED,
    LifecycleState.REGISTERED,
    LifecycleState.DETACHED,
})


class CorePackageError(ValueError):
    """A Core package manifest or registry contract was violated."""


class CorePackageAlreadyRegistered(CorePackageError):
    """A Core UUID, number or package slug is already reserved."""


class CorePackageConflict(CorePackageError):
    """A package operation would mutate immutable registration identity."""


class CorePackageAssetError(CorePackageError):
    """A declared personal asset is missing, corrupt or unreadable."""


class CorePackageBlankIdentityError(CorePackageError):
    """A blank package was asked to produce an identity-bearing artifact."""


class CorePackageSofiaSubstitution(PermissionError):
    """Package metadata attempted to occupy the canonical Sofía identity."""


def _require_uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _require_slug(value: object) -> str:
    if not isinstance(value, str) or _SLUG.fullmatch(value) is None:
        raise CorePackageError("package slug must be a lowercase identifier")
    return value


def _require_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be bool")
    return value


def _asset_payload(asset: CoreAssetReference | None) -> dict[str, object] | None:
    return None if asset is None else asset.to_payload()


def _avatar_payload(value: AvatarMetadata) -> dict[str, object]:
    return {
        "age_years": value.age_years,
        "height_inches": value.height_inches,
        "weight_pounds": value.weight_pounds,
        "build": value.build,
        "head_proportions": value.head_proportions,
        "measurements": dict(value.measurements),
        "hair": value.hair,
        "outfit": value.outfit,
        "default_expression": value.default_expression,
        "colors": dict(value.colors),
        "materials": dict(value.materials),
        "pbr": dict(value.pbr),
        "accessory": value.accessory,
    }


def _voice_payload(value: VoiceMetadata) -> dict[str, object]:
    return {
        "target": value.target,
        "register": value.register,
        "accent": value.accent,
        "cadence": value.cadence,
        "serious_delivery": value.serious_delivery,
        "model_id": value.model_id,
        "assets_created": value.assets_created,
    }


def _descriptor_payload(value: CoreDescriptor) -> dict[str, object]:
    return {
        "core_number": value.core_number,
        "full_name": value.full_name,
        "nickname": value.nickname,
        "gender": value.gender,
        "presentation_species": value.presentation_species,
        "apparent_age": value.apparent_age,
        "identity_concept": value.identity_concept,
        "personality_traits": list(value.personality_traits),
        "motivations": list(value.motivations),
        "character_flaw": value.character_flaw,
        "constitutional_priorities": list(value.constitutional_priorities),
        "avatar": _avatar_payload(value.avatar),
        "voice": _voice_payload(value.voice),
        "core_id": None if value.core_id is None else str(value.core_id),
    }


def _descriptor_from_payload(value: object) -> CoreDescriptor:
    fields = {
        "core_number", "full_name", "nickname", "gender", "presentation_species",
        "apparent_age", "identity_concept", "personality_traits", "motivations",
        "character_flaw", "constitutional_priorities", "avatar", "voice",
        "core_id",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise CorePackageError("Core descriptor fields differ")
    avatar = value["avatar"]
    voice = value["voice"]
    if not isinstance(avatar, Mapping) or set(avatar) != {
        "age_years", "height_inches", "weight_pounds", "build",
        "head_proportions", "measurements", "hair", "outfit",
        "default_expression", "colors", "materials", "pbr", "accessory",
    }:
        raise CorePackageError("Core avatar fields differ")
    if not isinstance(voice, Mapping) or set(voice) != {
        "target", "register", "accent", "cadence", "serious_delivery",
        "model_id", "assets_created",
    }:
        raise CorePackageError("Core voice fields differ")
    for label in ("measurements", "colors", "materials", "pbr"):
        if not isinstance(avatar[label], Mapping):
            raise CorePackageError(f"avatar {label} must be a mapping")
    core_id = value["core_id"]
    if core_id is not None:
        try:
            core_id = UUID(core_id)
        except (TypeError, ValueError) as exc:
            raise CorePackageError("descriptor Core UUID is invalid") from exc
    for label in (
        "personality_traits", "motivations", "constitutional_priorities",
    ):
        if not isinstance(value[label], list):
            raise CorePackageError(f"descriptor {label} must be a list")
    try:
        return CoreDescriptor(
            core_number=value["core_number"],
            full_name=value["full_name"],
            nickname=value["nickname"],
            gender=value["gender"],
            presentation_species=value["presentation_species"],
            apparent_age=value["apparent_age"],
            identity_concept=value["identity_concept"],
            personality_traits=tuple(value["personality_traits"]),
            motivations=tuple(value["motivations"]),
            character_flaw=value["character_flaw"],
            constitutional_priorities=tuple(value["constitutional_priorities"]),
            avatar=AvatarMetadata(
                age_years=avatar["age_years"],
                height_inches=avatar["height_inches"],
                weight_pounds=avatar["weight_pounds"],
                build=avatar["build"],
                head_proportions=avatar["head_proportions"],
                measurements=avatar["measurements"],
                hair=avatar["hair"],
                outfit=avatar["outfit"],
                default_expression=avatar["default_expression"],
                colors=avatar["colors"],
                materials=avatar["materials"],
                pbr=avatar["pbr"],
                accessory=avatar["accessory"],
            ),
            voice=VoiceMetadata(
                target=voice["target"],
                register=voice["register"],
                accent=voice["accent"],
                cadence=voice["cadence"],
                serious_delivery=voice["serious_delivery"],
                model_id=voice["model_id"],
                assets_created=voice["assets_created"],
            ),
            core_id=core_id,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, CorePackageError):
            raise
        raise CorePackageError("Core descriptor metadata is invalid") from exc


@dataclass(frozen=True, slots=True)
class CorePackageManifest:
    """One installable Core package; inert until an authorized lifecycle call.

    ``blank_identity`` reserves a UUID/number/slug without asserting a
    descriptor or personal assets.  A blank reservation may later be completed
    by a manifest with the same immutable identity triple.  It cannot be
    completed into a different UUID, number or slug.
    """

    core_id: UUID
    core_number: int
    slug: str
    descriptor: CoreDescriptor | None
    constitution: CoreAssetReference | None
    personality: CoreAssetReference | None
    lifecycle: LifecycleState = LifecycleState.DEFINED
    avatar_present: bool = False
    voice_present: bool = False
    blank_identity: bool = False

    def __post_init__(self) -> None:
        _require_uuid(self.core_id, "core_id")
        if type(self.core_number) is not int or self.core_number < 2:
            raise CorePackageError("package Core number must be an integer >= 2")
        _require_slug(self.slug)
        if not isinstance(self.lifecycle, LifecycleState):
            raise TypeError("package lifecycle must be a LifecycleState")
        _require_bool(self.avatar_present, "avatar_present")
        _require_bool(self.voice_present, "voice_present")
        _require_bool(self.blank_identity, "blank_identity")
        if self.blank_identity:
            if self.descriptor is not None:
                raise CorePackageError("a blank package cannot carry a descriptor")
            if self.constitution is not None or self.personality is not None:
                raise CorePackageError("a blank package cannot carry personal assets")
            if self.avatar_present or self.voice_present:
                raise CorePackageError(
                    "a blank package cannot claim avatar or voice presence"
                )
            if self.lifecycle not in _BLANK_LIFECYCLES:
                raise CorePackageError(
                    "a blank package cannot claim an active lifecycle state"
                )
            return
        if not isinstance(self.descriptor, CoreDescriptor):
            raise TypeError("a populated package requires a CoreDescriptor")
        if self.descriptor.core_number != self.core_number:
            raise CorePackageError("descriptor Core number differs from the package")
        if (
            self.descriptor.core_id is not None
            and self.descriptor.core_id != self.core_id
        ):
            raise CorePackageError(
                "descriptor Core UUID differs from the supplied package UUID"
            )
        if not isinstance(self.constitution, CoreAssetReference):
            raise TypeError("a populated package requires a constitution asset")
        if not isinstance(self.personality, CoreAssetReference):
            raise TypeError("a populated package requires a personality asset")
        if (
            self.constitution.path.casefold() == self.personality.path.casefold()
        ):
            raise CorePackageError(
                "constitution and personality must be distinct assets"
            )

    @property
    def is_blank(self) -> bool:
        return self.blank_identity

    @property
    def constitution_sha256(self) -> str | None:
        return None if self.constitution is None else self.constitution.sha256

    @property
    def personality_sha256(self) -> str | None:
        return None if self.personality is None else self.personality.sha256

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": CORE_PACKAGE_SCHEMA,
            "core_id": str(self.core_id),
            "core_number": self.core_number,
            "slug": self.slug,
            "descriptor": (
                None if self.descriptor is None
                else _descriptor_payload(self.descriptor)
            ),
            "constitution": _asset_payload(self.constitution),
            "personality": _asset_payload(self.personality),
            "lifecycle": self.lifecycle.value,
            "avatar_present": self.avatar_present,
            "voice_present": self.voice_present,
            "blank_identity": self.blank_identity,
        }

    @classmethod
    def from_payload(cls, value: object) -> "CorePackageManifest":
        fields = {
            "schema", "core_id", "core_number", "slug", "descriptor",
            "constitution", "personality", "lifecycle", "avatar_present",
            "voice_present", "blank_identity",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise CorePackageError("unsupported Core package fields/schema")
        if value["schema"] != CORE_PACKAGE_SCHEMA:
            raise CorePackageError("unsupported Core package schema")
        try:
            core_id = UUID(value["core_id"])
            descriptor = value["descriptor"]
            if descriptor is not None:
                descriptor = _descriptor_from_payload(descriptor)
            constitution = value["constitution"]
            personality = value["personality"]
            return cls(
                core_id=core_id,
                core_number=value["core_number"],
                slug=value["slug"],
                descriptor=descriptor,
                constitution=(
                    None if constitution is None
                    else CoreAssetReference.from_payload(constitution)
                ),
                personality=(
                    None if personality is None
                    else CoreAssetReference.from_payload(personality)
                ),
                lifecycle=LifecycleState(value["lifecycle"]),
                avatar_present=value["avatar_present"],
                voice_present=value["voice_present"],
                blank_identity=value["blank_identity"],
            )
        except CorePackageError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise CorePackageError("Core package manifest is invalid") from exc

    @property
    def canonical_bytes(self) -> bytes:
        raw = json.dumps(
            self.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        if len(raw) > MAX_PACKAGE_MANIFEST_BYTES:
            raise CorePackageError("package manifest exceeds its size bound")
        return raw

    @property
    def digest(self) -> str:
        return sha256(_PACKAGE_DOMAIN + self.canonical_bytes).hexdigest()

    def verify_assets(self, assets_root: Path | str) -> tuple[str, ...]:
        """Reject missing or corrupt personal assets; grants no authority."""
        if self.blank_identity:
            return ()
        root = Path(assets_root).absolute()
        assert_no_redirected_components(root, include_leaf=True)
        if not root.is_dir():
            raise CorePackageAssetError("Core package asset root is unavailable")
        verified: list[str] = []
        for asset in (self.constitution, self.personality):
            assert asset is not None
            target = root.joinpath(*asset.path.split("/"))
            try:
                actual, _ = read_artifact_file(target, asset.size_bytes)
            except (OSError, ValueError, PermissionError) as exc:
                raise CorePackageAssetError(
                    f"Core package asset is missing or unreadable: {asset.path}"
                ) from exc
            if actual != asset.sha256:
                raise CorePackageAssetError(
                    f"Core package asset digest differs: {asset.path}"
                )
            verified.append(asset.path)
        return tuple(verified)

    def core_definition(
        self,
        *,
        revision: int,
        runtime_release_sha256: str,
    ) -> CoreDefinition:
        """Adapt this manifest to the existing inert Core definition contract."""
        if self.blank_identity:
            raise CorePackageBlankIdentityError(
                "a blank package has no identity-bearing Core definition"
            )
        assert self.descriptor is not None
        assert self.constitution is not None
        assert self.personality is not None
        return CoreDefinition(
            identity=AegisIdentity(IdentityKind.CORE, self.core_id),
            name=self.descriptor.full_name,
            revision=revision,
            runtime_release_sha256=runtime_release_sha256,
            sdk_protocol=SDK_PROTOCOL_VERSION,
            constitution=self.constitution,
            personality=self.personality,
        )

    def core_profile(self) -> CoreProfile:
        """Adapt this manifest to the existing profile/lifecycle interface."""
        if self.blank_identity:
            raise CorePackageBlankIdentityError(
                "a blank package has no Core profile to register"
            )
        assert self.descriptor is not None
        assert self.constitution is not None
        assert self.personality is not None
        descriptor = self.descriptor
        if descriptor.core_id is None:
            descriptor = replace(descriptor, core_id=self.core_id)
        spec = CoreProfileSpec(
            slug=self.slug,
            core_number=self.core_number,
            full_name=descriptor.full_name,
            nickname=descriptor.nickname,
            gender=descriptor.gender,
            presentation_species=descriptor.presentation_species,
            apparent_age=descriptor.apparent_age,
            identity_concept=descriptor.identity_concept,
        )
        return CoreProfile(
            spec=spec,
            descriptor=descriptor,
            constitution_sha256=self.constitution.sha256,
            constitution_size=self.constitution.size_bytes,
            personality_sha256=self.personality.sha256,
            personality_size=self.personality.size_bytes,
            avatar_present=self.avatar_present,
            voice_present=self.voice_present,
        )


def load_core_package_manifest(path: Path | str) -> CorePackageManifest:
    """Read a bounded manifest file without installing or activating anything."""
    target = Path(path).absolute()
    try:
        assert_no_redirected_components(target, include_leaf=True)
        details = target.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(details.st_mode)
            or not 1 <= details.st_size <= MAX_PACKAGE_MANIFEST_BYTES
        ):
            raise CorePackageError(
                "package manifest must be a bounded regular file"
            )
        _, raw = read_artifact_file(
            target, details.st_size, include_data=True,
        )
        assert raw is not None
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
        return CorePackageManifest.from_payload(payload)
    except CorePackageError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, PermissionError) as exc:
        raise CorePackageError("package manifest is unreadable or corrupt") from exc


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate package manifest field")
        result[key] = value
    return result


def register_package_with_lifecycle(
    lifecycle: MulticoreCoreLifecycle,
    manifest: CorePackageManifest,
    *,
    revision: int,
    runtime_release_sha256: str,
    verifier,
    signature_b64: str,
    signer_key_id: str,
    assets_root: Path | str,
    minimum_revision: int,
) -> CoreDefinitionRegistration:
    """Register verified definition metadata through the existing lifecycle.

    No verifier or runtime is created here.  The existing
    ``MulticoreCoreLifecycle`` performs verification, records inert
    registration metadata and remains the sole lifecycle boundary.  This
    function does not install, activate, stop, remove or reconcile anything.
    """
    if not isinstance(lifecycle, MulticoreCoreLifecycle):
        raise TypeError("lifecycle must be the existing MulticoreCoreLifecycle")
    if not isinstance(manifest, CorePackageManifest):
        raise TypeError("manifest must be a CorePackageManifest")
    profile = manifest.core_profile()
    definition = manifest.core_definition(
        revision=revision, runtime_release_sha256=runtime_release_sha256,
    )
    return lifecycle.register_definition(
        profile,
        definition,
        verifier=verifier,
        signature_b64=signature_b64,
        signer_key_id=signer_key_id,
        assets_root=assets_root,
        runtime_release_sha256=runtime_release_sha256,
        minimum_revision=minimum_revision,
    )


class CorePackageRegistry:
    """Thread-safe registry of package manifests with immutable identity keys."""

    def __init__(
        self,
        *,
        sofia_instance_id: UUID | None = None,
        protected_identity_ids: Iterable[UUID] = (),
    ) -> None:
        self._lock = RLock()
        self._packages: dict[UUID, CorePackageManifest] = {}
        self._numbers: dict[int, UUID] = {}
        self._slugs: dict[str, UUID] = {}
        self._protected: set[UUID] = set()
        if sofia_instance_id is not None:
            self._protected.add(_require_uuid(sofia_instance_id, "sofia_instance_id"))
        for core_id in protected_identity_ids:
            self._protected.add(_require_uuid(core_id, "protected identity"))

    def _assert_not_substituting_sofia(self, manifest: CorePackageManifest) -> None:
        if manifest.core_id in self._protected:
            raise CorePackageSofiaSubstitution(
                "package metadata cannot occupy the canonical Sofía identity"
            )

    def register(self, manifest: CorePackageManifest) -> CorePackageManifest:
        if not isinstance(manifest, CorePackageManifest):
            raise TypeError("manifest must be a CorePackageManifest")
        self._assert_not_substituting_sofia(manifest)
        with self._lock:
            existing = self._packages.get(manifest.core_id)
            if existing is not None:
                if (
                    existing.blank_identity
                    and not manifest.blank_identity
                    and existing.core_number == manifest.core_number
                    and existing.slug == manifest.slug
                ):
                    self._packages[manifest.core_id] = manifest
                    return manifest
                if (
                    existing.blank_identity
                    and not manifest.blank_identity
                    and (
                        existing.core_number != manifest.core_number
                        or existing.slug != manifest.slug
                    )
                ):
                    raise CorePackageConflict(
                        "completion cannot change the reserved Core number or slug"
                    )
                raise CorePackageAlreadyRegistered(
                    f"Core package {manifest.slug} / #{manifest.core_number} "
                    "is already registered"
                )
            if (
                manifest.core_number in self._numbers
                or manifest.slug in self._slugs
            ):
                raise CorePackageAlreadyRegistered(
                    f"Core package {manifest.slug} / #{manifest.core_number} "
                    "is already registered"
                )
            self._packages[manifest.core_id] = manifest
            self._numbers[manifest.core_number] = manifest.core_id
            self._slugs[manifest.slug] = manifest.core_id
        return manifest

    def complete_blank(
        self, manifest: CorePackageManifest,
    ) -> CorePackageManifest:
        """Replace a blank reservation with the same identity's full package."""
        if not isinstance(manifest, CorePackageManifest):
            raise TypeError("manifest must be a CorePackageManifest")
        if manifest.blank_identity:
            raise CorePackageError("completion requires a populated package")
        self._assert_not_substituting_sofia(manifest)
        with self._lock:
            existing = self._packages.get(manifest.core_id)
            if existing is None:
                raise CorePackageError("no blank package reservation exists")
            if (
                existing.core_number != manifest.core_number
                or existing.slug != manifest.slug
            ):
                raise CorePackageConflict(
                    "completion cannot change the reserved Core number or slug"
                )
            if not existing.blank_identity:
                raise CorePackageConflict(
                    "an identity-bearing package is already registered"
                )
            self._packages[manifest.core_id] = manifest
        return manifest

    def resolve(self, selector: UUID | int | str) -> CorePackageManifest:
        with self._lock:
            if isinstance(selector, UUID):
                manifest = self._packages.get(selector)
            elif type(selector) is int:
                core_id = self._numbers.get(selector)
                manifest = (
                    None if core_id is None else self._packages.get(core_id)
                )
            elif isinstance(selector, str):
                core_id = self._slugs.get(selector)
                manifest = (
                    None if core_id is None else self._packages.get(core_id)
                )
            else:
                raise TypeError(
                    "package selector must be a UUID, number or slug"
                )
        if manifest is None:
            raise KeyError(f"no Core package registered for {selector!r}")
        return manifest

    def manifests(self) -> tuple[CorePackageManifest, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._packages.values(),
                    key=lambda item: (item.core_number, str(item.core_id)),
                )
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._packages)


__all__ = [
    "CORE_PACKAGE_SCHEMA",
    "CorePackageAlreadyRegistered",
    "CorePackageAssetError",
    "CorePackageBlankIdentityError",
    "CorePackageConflict",
    "CorePackageError",
    "CorePackageManifest",
    "CorePackageRegistry",
    "CorePackageSofiaSubstitution",
    "MAX_PACKAGE_MANIFEST_BYTES",
    "load_core_package_manifest",
    "register_package_with_lifecycle",
]
