"""Per-Core personal gesture preferences, variants and owner-private storage.

A personal gesture is owned by exactly one Core.  Learning or teaching a gesture
creates a new immutable per-Core variant while preserving the originator's
provenance; it never mutates the originator's record and never allocates another
canonical state writer.  This slice deliberately uses an injectable repository
or owner-private JSON, not the canonical Core SQLite database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import RLock
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable
from uuid import UUID, uuid4

from sofia.platform.state.private_file import (
    assert_no_redirected_components,
    assert_not_protected_state_path,
    assert_owner_private_path,
    atomic_write_private_text,
    ensure_owner_private_directory,
)
from sofia.sdk.gesture_contract import (
    GestureDefinition,
    GestureError,
    _identifier,
    _ratio,
    _text,
    _utc,
    _uuid,
)

GESTURE_LIBRARY_SCHEMA = "aegis.core.gesture_library.v1"
GESTURE_VARIANT_SCHEMA = "aegis.core.gesture_variant.v1"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class GestureLibraryError(RuntimeError):
    """A per-Core gesture library contract was violated."""


class DuplicateGestureVariant(GestureLibraryError):
    """A variant id already exists in the owning library."""


GestureExceptionTypes = (GestureLibraryError, GestureError)


class GestureUsePreference(str, Enum):
    WELCOMED = "welcomed"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"
    DECLINED = "declined"


class GestureShareMethod(str, Enum):
    LEARNED = "learned"
    TAUGHT = "taught"
    SHARED = "shared"
    IMPORTED = "imported"


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GestureLibraryError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise GestureLibraryError(f"{label} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class GestureOrigin:
    """Immutable provenance; sharing preserves the originator's record."""

    origin_core_id: UUID
    origin_variant_id: UUID
    origin_gesture_id: str
    origin_version: int
    origin_digest: str
    method: GestureShareMethod
    recorded_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.origin_core_id, "origin_core_id")
        _uuid(self.origin_variant_id, "origin_variant_id")
        _identifier(self.origin_gesture_id, "origin_gesture_id")
        _positive(self.origin_version, "origin_version")
        _digest(self.origin_digest, "origin_digest")
        if not isinstance(self.method, GestureShareMethod):
            raise GestureLibraryError("method must be GestureShareMethod")
        _utc(self.recorded_at, "recorded_at")

    def to_payload(self) -> dict[str, object]:
        return {
            "origin_core_id": str(self.origin_core_id),
            "origin_variant_id": str(self.origin_variant_id),
            "origin_gesture_id": self.origin_gesture_id,
            "origin_version": self.origin_version,
            "origin_digest": self.origin_digest,
            "method": self.method.value,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "GestureOrigin":
        fields = frozenset({
            "origin_core_id", "origin_variant_id", "origin_gesture_id",
            "origin_version", "origin_digest", "method", "recorded_at",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureLibraryError("gesture origin fields differ")
        try:
            return cls(
                origin_core_id=UUID(str(value["origin_core_id"])),
                origin_variant_id=UUID(str(value["origin_variant_id"])),
                origin_gesture_id=value["origin_gesture_id"],
                origin_version=value["origin_version"],
                origin_digest=value["origin_digest"],
                method=GestureShareMethod(value["method"]),
                recorded_at=datetime.fromisoformat(str(value["recorded_at"])),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, GestureLibraryError):
                raise
            raise GestureLibraryError("gesture origin is invalid") from exc


@dataclass(frozen=True, slots=True)
class GesturePreference:
    """Owner-scoped style/intensity/pacing preference; never a consent grant."""

    core_id: UUID
    gesture_id: str
    style: str
    intensity: float
    pacing: float
    use: GestureUsePreference
    updated_at: datetime
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _identifier(self.gesture_id, "gesture_id")
        _text(self.style, "style", maximum=256)
        _ratio(self.intensity, "intensity")
        _ratio(self.pacing, "pacing")
        if not isinstance(self.use, GestureUsePreference):
            raise GestureLibraryError("use must be GestureUsePreference")
        _utc(self.updated_at, "updated_at")
        _positive(self.revision, "revision")

    def to_payload(self) -> dict[str, object]:
        return {
            "core_id": str(self.core_id),
            "gesture_id": self.gesture_id,
            "style": self.style,
            "intensity": self.intensity,
            "pacing": self.pacing,
            "use": self.use.value,
            "updated_at": self.updated_at.isoformat(),
            "revision": self.revision,
        }

    @classmethod
    def from_payload(cls, value: object) -> "GesturePreference":
        fields = frozenset({
            "core_id", "gesture_id", "style", "intensity", "pacing", "use",
            "updated_at", "revision",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureLibraryError("gesture preference fields differ")
        try:
            return cls(
                core_id=UUID(str(value["core_id"])),
                gesture_id=value["gesture_id"],
                style=value["style"],
                intensity=value["intensity"],
                pacing=value["pacing"],
                use=GestureUsePreference(value["use"]),
                updated_at=datetime.fromisoformat(str(value["updated_at"])),
                revision=value["revision"],
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, GestureExceptionTypes):
                raise
            raise GestureLibraryError("gesture preference is invalid") from exc


@dataclass(frozen=True, slots=True)
class PersonalGestureVariant:
    """One owner's immutable personal style plus origin provenance."""

    variant_id: UUID
    owner_core_id: UUID
    definition: GestureDefinition
    preference: GesturePreference
    origin: GestureOrigin
    created_at: datetime
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.variant_id, "variant_id")
        _uuid(self.owner_core_id, "owner_core_id")
        if not isinstance(self.definition, GestureDefinition):
            raise GestureLibraryError("definition must be a GestureDefinition")
        if not isinstance(self.preference, GesturePreference):
            raise GestureLibraryError("preference must be GesturePreference")
        if not isinstance(self.origin, GestureOrigin):
            raise GestureLibraryError("origin must be GestureOrigin")
        _utc(self.created_at, "created_at")
        _positive(self.revision, "revision")
        if self.preference.core_id != self.owner_core_id:
            raise GestureLibraryError("preference owner differs from variant owner")
        if self.preference.gesture_id != self.definition.gesture_id:
            raise GestureLibraryError("preference gesture differs from definition")
        if self.origin.origin_gesture_id != self.definition.gesture_id:
            raise GestureLibraryError("origin gesture differs from definition")
        if self.origin.origin_version != self.definition.version:
            raise GestureLibraryError("origin version differs from definition")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": GESTURE_VARIANT_SCHEMA,
            "variant_id": str(self.variant_id),
            "owner_core_id": str(self.owner_core_id),
            "definition": self.definition.to_payload(),
            "preference": self.preference.to_payload(),
            "origin": self.origin.to_payload(),
            "created_at": self.created_at.isoformat(),
            "revision": self.revision,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(
            b"aegis.core.gesture_variant.v1\x00" + self.canonical_bytes
        ).hexdigest()

    @classmethod
    def from_payload(cls, value: object) -> "PersonalGestureVariant":
        fields = frozenset({
            "schema", "variant_id", "owner_core_id", "definition",
            "preference", "origin", "created_at", "revision",
        })
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureLibraryError("gesture variant fields differ")
        if value["schema"] != GESTURE_VARIANT_SCHEMA:
            raise GestureLibraryError("unsupported gesture variant schema")
        try:
            return cls(
                variant_id=UUID(str(value["variant_id"])),
                owner_core_id=UUID(str(value["owner_core_id"])),
                definition=GestureDefinition.from_payload(value["definition"]),
                preference=GesturePreference.from_payload(value["preference"]),
                origin=GestureOrigin.from_payload(value["origin"]),
                created_at=datetime.fromisoformat(str(value["created_at"])),
                revision=value["revision"],
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, GestureExceptionTypes):
                raise
            raise GestureLibraryError("gesture variant is invalid") from exc


@dataclass(frozen=True, slots=True)
class GestureLibrary:
    """Immutable per-Core variant collection; one owner only."""

    core_id: UUID
    variants: Mapping[UUID, PersonalGestureVariant] = field(default_factory=dict)
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _positive(self.revision, "revision")
        if not isinstance(self.variants, Mapping):
            raise GestureLibraryError("variants must be a mapping")
        frozen: dict[UUID, PersonalGestureVariant] = {}
        for key, variant in self.variants.items():
            _uuid(key, "variant key")
            if not isinstance(variant, PersonalGestureVariant):
                raise GestureLibraryError("variants must be PersonalGestureVariant")
            if key != variant.variant_id:
                raise GestureLibraryError("variant key differs from its id")
            if variant.owner_core_id != self.core_id:
                raise GestureLibraryError("a library cannot own another Core's variant")
            frozen[key] = variant
        object.__setattr__(self, "variants", MappingProxyType(frozen))

    def variant(self, variant_id: UUID) -> PersonalGestureVariant:
        _uuid(variant_id, "variant_id")
        try:
            return self.variants[variant_id]
        except KeyError as exc:
            raise GestureLibraryError("gesture variant does not exist") from exc

    def variants_for(self, gesture_id: str) -> tuple[PersonalGestureVariant, ...]:
        _identifier(gesture_id, "gesture_id")
        return tuple(
            variant for variant in self.variants.values()
            if variant.definition.gesture_id == gesture_id
        )

    def with_variant(self, variant: PersonalGestureVariant) -> "GestureLibrary":
        if not isinstance(variant, PersonalGestureVariant):
            raise GestureLibraryError("variant must be a PersonalGestureVariant")
        if variant.owner_core_id != self.core_id:
            raise GestureLibraryError("a library cannot adopt another Core's variant")
        if variant.variant_id in self.variants:
            raise DuplicateGestureVariant("gesture variant id already exists")
        updated = dict(self.variants)
        updated[variant.variant_id] = variant
        return GestureLibrary(
            core_id=self.core_id,
            variants=updated,
            revision=self.revision + 1,
        )

    def learn(
        self,
        definition: GestureDefinition,
        *,
        style: str,
        intensity: float,
        pacing: float,
        use: GestureUsePreference,
        at: datetime,
        variant_id: UUID | None = None,
    ) -> "GestureLibrary":
        """Learn a personal variant owned by this Core."""
        return self.with_variant(
            _new_variant(
                owner_core_id=self.core_id,
                definition=definition,
                style=style,
                intensity=intensity,
                pacing=pacing,
                use=use,
                at=at,
                method=GestureShareMethod.LEARNED,
                origin=None,
                variant_id=variant_id,
            )
        )

    def teach(
        self,
        shared: PersonalGestureVariant,
        *,
        style: str | None = None,
        intensity: float | None = None,
        pacing: float | None = None,
        use: GestureUsePreference | None = None,
        at: datetime,
        variant_id: UUID | None = None,
    ) -> "GestureLibrary":
        """Import a shared gesture as a new variant without mutating its origin."""
        if not isinstance(shared, PersonalGestureVariant):
            raise GestureLibraryError("shared must be a PersonalGestureVariant")
        if shared.owner_core_id == self.core_id:
            raise GestureLibraryError("teaching a Core its own variant is not import")
        return self.with_variant(
            _new_variant(
                owner_core_id=self.core_id,
                definition=shared.definition,
                style=shared.preference.style if style is None else style,
                intensity=(
                    shared.preference.intensity if intensity is None else intensity
                ),
                pacing=shared.preference.pacing if pacing is None else pacing,
                use=shared.preference.use if use is None else use,
                at=at,
                method=GestureShareMethod.TAUGHT,
                origin=shared.origin,
                variant_id=variant_id,
            )
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": GESTURE_LIBRARY_SCHEMA,
            "core_id": str(self.core_id),
            "revision": self.revision,
            "variants": [
                self.variants[key].to_payload()
                for key in sorted(self.variants, key=str)
            ],
        }

    @classmethod
    def empty(cls, core_id: UUID) -> "GestureLibrary":
        return cls(core_id=core_id)

    @classmethod
    def from_payload(cls, value: object) -> "GestureLibrary":
        fields = frozenset({"schema", "core_id", "revision", "variants"})
        if not isinstance(value, Mapping) or set(value) != fields:
            raise GestureLibraryError("gesture library fields differ")
        if value["schema"] != GESTURE_LIBRARY_SCHEMA:
            raise GestureLibraryError("unsupported gesture library schema")
        raw_variants = value["variants"]
        if not isinstance(raw_variants, list):
            raise GestureLibraryError("gesture library variants must be a list")
        try:
            variants = {}
            for item in raw_variants:
                variant = PersonalGestureVariant.from_payload(item)
                if variant.variant_id in variants:
                    raise GestureLibraryError("duplicate gesture variant in library")
                variants[variant.variant_id] = variant
            return cls(
                core_id=UUID(str(value["core_id"])),
                variants=variants,
                revision=value["revision"],
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, GestureExceptionTypes):
                raise
            raise GestureLibraryError("gesture library is invalid") from exc


def _new_variant(
    *,
    owner_core_id: UUID,
    definition: GestureDefinition,
    style: str,
    intensity: float,
    pacing: float,
    use: GestureUsePreference,
    at: datetime,
    method: GestureShareMethod,
    origin: GestureOrigin | None,
    variant_id: UUID | None,
) -> PersonalGestureVariant:
    if not isinstance(definition, GestureDefinition):
        raise GestureLibraryError("definition must be a GestureDefinition")
    if not isinstance(use, GestureUsePreference):
        raise GestureLibraryError("use must be GestureUsePreference")
    _utc(at, "at")
    identifier = uuid4() if variant_id is None else _uuid(variant_id, "variant_id")
    preference = GesturePreference(
        core_id=owner_core_id,
        gesture_id=definition.gesture_id,
        style=style,
        intensity=intensity,
        pacing=pacing,
        use=use,
        updated_at=at,
    )
    provenance = origin if origin is not None else GestureOrigin(
        origin_core_id=owner_core_id,
        origin_variant_id=identifier,
        origin_gesture_id=definition.gesture_id,
        origin_version=definition.version,
        origin_digest=definition.digest,
        method=method,
        recorded_at=at,
    )
    if provenance.origin_core_id != owner_core_id and method is GestureShareMethod.LEARNED:
        raise GestureLibraryError("learned gestures originate with their owner")
    return PersonalGestureVariant(
        variant_id=identifier,
        owner_core_id=owner_core_id,
        definition=definition,
        preference=preference,
        origin=provenance,
        created_at=at,
    )


@runtime_checkable
class GestureRepository(Protocol):
    """Injectable per-Core library persistence boundary."""

    def load(self, core_id: UUID) -> GestureLibrary:
        ...

    def save(self, library: GestureLibrary) -> None:
        ...


class InMemoryGestureRepository:
    """Disposable in-memory repository; preserves per-Core isolation."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._libraries: dict[UUID, GestureLibrary] = {}

    def load(self, core_id: UUID) -> GestureLibrary:
        supplied = _uuid(core_id, "core_id")
        with self._lock:
            return self._libraries.get(supplied, GestureLibrary.empty(supplied))

    def save(self, library: GestureLibrary) -> None:
        if not isinstance(library, GestureLibrary):
            raise GestureLibraryError("library must be a GestureLibrary")
        with self._lock:
            self._libraries[library.core_id] = library


class OwnerPrivateGestureStore:
    """Owner-private JSON store; never touches ``sofia.db`` or another writer."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        if not self.directory.is_absolute():
            raise ValueError("gesture library directory must be absolute")
        for component in (self.directory, *self.directory.parents):
            assert_not_protected_state_path(component)
        assert_no_redirected_components(self.directory, include_leaf=True)
        ensure_owner_private_directory(self.directory)
        self._lock = RLock()

    def _path(self, core_id: UUID) -> Path:
        return self.directory / f"{_uuid(core_id, 'core_id')}.json"

    def load(self, core_id: UUID) -> GestureLibrary:
        supplied = _uuid(core_id, "core_id")
        path = self._path(supplied)
        with self._lock:
            assert_not_protected_state_path(path)
            assert_no_redirected_components(path, include_leaf=True)
            if not path.exists():
                return GestureLibrary.empty(supplied)
            assert_owner_private_path(path, directory=False)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise GestureLibraryError("gesture library is unreadable or corrupt") from exc
            library = GestureLibrary.from_payload(payload)
            if library.core_id != supplied:
                raise GestureLibraryError("gesture library belongs to another Core")
            return library

    def save(self, library: GestureLibrary) -> None:
        if not isinstance(library, GestureLibrary):
            raise GestureLibraryError("library must be a GestureLibrary")
        path = self._path(library.core_id)
        content = json.dumps(
            library.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ) + "\n"
        with self._lock:
            assert_not_protected_state_path(path)
            atomic_write_private_text(path, content)
            assert_owner_private_path(path, directory=False)


def share_personal_gesture(
    source: GestureLibrary,
    variant_id: UUID,
    target: GestureLibrary,
    *,
    at: datetime,
    style: str | None = None,
    intensity: float | None = None,
    pacing: float | None = None,
    use: GestureUsePreference | None = None,
) -> GestureLibrary:
    """Offer one variant to another Core, returning the target's new library."""
    if not isinstance(source, GestureLibrary) or not isinstance(target, GestureLibrary):
        raise GestureLibraryError("source and target must be GestureLibrary values")
    shared = source.variant(variant_id)
    return target.teach(
        shared,
        at=at,
        style=style,
        intensity=intensity,
        pacing=pacing,
        use=use,
    )


__all__ = [
    "DuplicateGestureVariant",
    "GESTURE_LIBRARY_SCHEMA",
    "GESTURE_VARIANT_SCHEMA",
    "GestureLibrary",
    "GestureLibraryError",
    "GestureOrigin",
    "GesturePreference",
    "GestureRepository",
    "GestureShareMethod",
    "GestureUsePreference",
    "InMemoryGestureRepository",
    "OwnerPrivateGestureStore",
    "PersonalGestureVariant",
    "share_personal_gesture",
]
