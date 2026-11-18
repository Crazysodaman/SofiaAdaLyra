"""Stable per-Core continuity across restart, model and provider changes.

A Core's continuity record binds its persistent UUID, readable identity and
Constitution hash to a single evolving state lineage.  Loading verifies the
recorded checksum and, when provided, the expected Core descriptor before any
value is returned.  A missing, corrupt, substituted or mismatched record fails
closed: this module never mints a replacement UUID, name or memory set.

Runtime fields record which model/provider/process most recently served the
Core.  Changing them cannot change the Core's identity or memories.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
from uuid import UUID, uuid4

from sofia.core.multicore.contracts import (
    CoreDescriptor,
    PersistentCoreIdentity,
)
from sofia.platform.state.atomic_file import atomic_write_text


CONTINUITY_SCHEMA = "aegis.core.multicore.continuity.v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_PAYLOAD_KEYS = frozenset({
    "identity",
    "model_id",
    "provider_id",
    "process_id",
    "personality_revision",
    "personality_digest",
    "emotion_revision",
    "relationships_revision",
    "memory_ids",
    "revision",
    "updated_at",
})
_IDENTITY_KEYS = frozenset({
    "core_id",
    "core_number",
    "full_name",
    "slug",
    "generation",
    "constitution_sha256",
    "created_at",
})


class ContinuityError(RuntimeError):
    """Base failure for invalid or unavailable Core continuity."""


class ContinuityIntegrityError(ContinuityError):
    """Protected continuity failed verification.  Nothing is replaced."""


def _utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _text(value: object, label: str, *, maximum: int = 160) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise ValueError(f"{label} must be bounded single-line text")
    return value.strip()


def _optional_text(value: object, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _nonnegative(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be lowercase SHA-256 or empty")
    if value == "":
        return value
    if _HEX64.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase SHA-256 or empty")
    return value


@dataclass(frozen=True, slots=True)
class CoreContinuityState:
    """One Core's protected identity plus its evolving runtime continuity."""

    identity: PersistentCoreIdentity
    model_id: str | None = None
    provider_id: str | None = None
    process_id: str | None = None
    personality_revision: int = 0
    personality_digest: str = ""
    emotion_revision: int = 0
    relationships_revision: int = 0
    memory_ids: tuple[UUID, ...] = ()
    revision: int = 1
    updated_at: datetime = field(default_factory=_now)
    schema: str = CONTINUITY_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.identity, PersistentCoreIdentity):
            raise TypeError("identity must be PersistentCoreIdentity")
        if self.schema != CONTINUITY_SCHEMA:
            raise ValueError("unsupported continuity schema")
        _optional_text(self.model_id, "model_id")
        _optional_text(self.provider_id, "provider_id")
        _optional_text(self.process_id, "process_id")
        _nonnegative(self.personality_revision, "personality_revision")
        _digest(self.personality_digest, "personality_digest")
        _nonnegative(self.emotion_revision, "emotion_revision")
        _nonnegative(self.relationships_revision, "relationships_revision")
        if not isinstance(self.memory_ids, tuple):
            raise TypeError("memory_ids must be a tuple")
        for item in self.memory_ids:
            _uuid(item, "memory_id")
        if len(set(self.memory_ids)) != len(self.memory_ids):
            raise ValueError("memory identifiers must be distinct")
        _positive(self.revision, "revision")
        object.__setattr__(
            self,
            "updated_at",
            _utc(self.updated_at, "updated_at"),
        )

    @property
    def core_id(self) -> UUID:
        return self.identity.core_id

    @property
    def core_number(self) -> int:
        return self.identity.core_number

    @property
    def full_name(self) -> str:
        return self.identity.full_name

    def with_runtime(
        self,
        *,
        model_id: str | None,
        provider_id: str | None,
        process_id: str | None,
        now: datetime,
    ) -> CoreContinuityState:
        """Record the serving runtime without touching identity or memories."""
        stamp = _utc(now, "now")
        if stamp < self.updated_at:
            raise ValueError("continuity clock cannot move backward")
        return replace(
            self,
            model_id=model_id,
            provider_id=provider_id,
            process_id=process_id,
            revision=self.revision + 1,
            updated_at=stamp,
        )

    def with_memory(self, memory_id: UUID, *, now: datetime) -> CoreContinuityState:
        """Append one memory identifier.  Existing memories are never removed."""
        memory = _uuid(memory_id, "memory_id")
        if memory in self.memory_ids:
            return self
        stamp = _utc(now, "now")
        if stamp < self.updated_at:
            raise ValueError("continuity clock cannot move backward")
        return replace(
            self,
            memory_ids=(*self.memory_ids, memory),
            revision=self.revision + 1,
            updated_at=stamp,
        )

    def with_personal_state(
        self,
        *,
        personality_revision: int,
        personality_digest: str,
        emotion_revision: int,
        relationships_revision: int,
        now: datetime,
    ) -> CoreContinuityState:
        """Record personal-state progress without replacing the identity."""
        stamp = _utc(now, "now")
        if stamp < self.updated_at:
            raise ValueError("continuity clock cannot move backward")
        if personality_revision < self.personality_revision:
            raise ValueError("personality revision cannot move backward")
        if emotion_revision < self.emotion_revision:
            raise ValueError("emotion revision cannot move backward")
        if relationships_revision < self.relationships_revision:
            raise ValueError("relationship revision cannot move backward")
        return replace(
            self,
            personality_revision=personality_revision,
            personality_digest=personality_digest,
            emotion_revision=emotion_revision,
            relationships_revision=relationships_revision,
            revision=self.revision + 1,
            updated_at=stamp,
        )


def _identity_payload(identity: PersistentCoreIdentity) -> dict:
    return {
        "core_id": str(identity.core_id),
        "core_number": identity.core_number,
        "full_name": identity.full_name,
        "slug": identity.slug,
        "generation": identity.generation,
        "constitution_sha256": identity.constitution_sha256,
        "created_at": identity.created_at.isoformat(),
    }


def _payload(state: CoreContinuityState) -> dict:
    return {
        "identity": _identity_payload(state.identity),
        "model_id": state.model_id,
        "provider_id": state.provider_id,
        "process_id": state.process_id,
        "personality_revision": state.personality_revision,
        "personality_digest": state.personality_digest,
        "emotion_revision": state.emotion_revision,
        "relationships_revision": state.relationships_revision,
        "memory_ids": [str(item) for item in state.memory_ids],
        "revision": state.revision,
        "updated_at": state.updated_at.isoformat(),
    }


def _checksum(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _identity_from_payload(value: object) -> PersistentCoreIdentity:
    if not isinstance(value, dict) or set(value) != _IDENTITY_KEYS:
        raise ContinuityIntegrityError("continuity identity payload is invalid")
    try:
        return PersistentCoreIdentity(
            core_id=UUID(value["core_id"]),
            core_number=value["core_number"],
            full_name=value["full_name"],
            slug=value["slug"],
            generation=value["generation"],
            constitution_sha256=value["constitution_sha256"],
            created_at=datetime.fromisoformat(value["created_at"]),
        )
    except (TypeError, ValueError, KeyError):
        raise ContinuityIntegrityError(
            "continuity identity payload failed validation"
        ) from None


def _state_from_payload(payload: object) -> CoreContinuityState:
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_KEYS:
        raise ContinuityIntegrityError("continuity payload is invalid")
    identity = _identity_from_payload(payload["identity"])
    memory_values = payload["memory_ids"]
    if not isinstance(memory_values, list):
        raise ContinuityIntegrityError("continuity memory identifiers are invalid")
    try:
        memory_ids = tuple(UUID(item) for item in memory_values)
        return CoreContinuityState(
            identity=identity,
            model_id=payload["model_id"],
            provider_id=payload["provider_id"],
            process_id=payload["process_id"],
            personality_revision=payload["personality_revision"],
            personality_digest=payload["personality_digest"],
            emotion_revision=payload["emotion_revision"],
            relationships_revision=payload["relationships_revision"],
            memory_ids=memory_ids,
            revision=payload["revision"],
            updated_at=datetime.fromisoformat(payload["updated_at"]),
        )
    except (TypeError, ValueError, KeyError):
        raise ContinuityIntegrityError(
            "continuity payload failed validation"
        ) from None


class CoreContinuityStore:
    """One canonical continuity file for one Core identity lineage."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def initialize(
        self,
        *,
        descriptor: CoreDescriptor,
        constitution_sha256: str,
        now: datetime,
        core_id: UUID | None = None,
    ) -> CoreContinuityState:
        """Create the first continuity record for a Core.

        This is the only path that may create a record.  It refuses to run if
        a record already exists, so an existing identity is never silently
        replaced by a new UUID.
        """
        if not isinstance(descriptor, CoreDescriptor):
            raise TypeError("descriptor must be a CoreDescriptor")
        if self.path.exists():
            raise ContinuityIntegrityError(
                "continuity already exists; refusing to mint a replacement identity"
            )
        if not isinstance(constitution_sha256, str) or _HEX64.fullmatch(
            constitution_sha256
        ) is None:
            raise ValueError("constitution_sha256 must be lowercase SHA-256")
        stamp = _utc(now, "now")
        if core_id is not None:
            chosen = _uuid(core_id, "core_id")
            if descriptor.core_id is not None and descriptor.core_id != chosen:
                raise ContinuityIntegrityError(
                    "descriptor core_id does not match the continuity identity"
                )
        elif descriptor.core_id is not None:
            chosen = descriptor.core_id
        else:
            chosen = uuid4()
        slug = descriptor.slug
        if not slug:
            raise ValueError("descriptor full_name must yield a usable slug")
        identity = PersistentCoreIdentity(
            core_id=chosen,
            core_number=descriptor.core_number,
            full_name=descriptor.full_name,
            slug=slug,
            generation=1,
            constitution_sha256=constitution_sha256,
            created_at=stamp,
        )
        state = CoreContinuityState(
            identity=identity,
            revision=1,
            updated_at=stamp,
        )
        self.save(state)
        return state

    def load(
        self,
        *,
        expected_core_id: UUID | None = None,
        descriptor: CoreDescriptor | None = None,
    ) -> CoreContinuityState:
        """Load and verify continuity.  Never creates or repairs a file."""
        if not self.path.exists():
            raise ContinuityIntegrityError(
                "continuity state is missing; refusing to create a replacement"
            )
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ContinuityIntegrityError(
                "continuity state could not be read"
            ) from None
        if not isinstance(raw, dict) or set(raw) != {
            "schema",
            "payload",
            "sha256",
        }:
            raise ContinuityIntegrityError("continuity envelope is invalid")
        if raw["schema"] != CONTINUITY_SCHEMA:
            raise ContinuityIntegrityError("continuity schema is unsupported")
        if not isinstance(raw["sha256"], str) or not isinstance(raw["payload"], dict):
            raise ContinuityIntegrityError("continuity envelope is invalid")
        expected_checksum = _checksum(raw["payload"])
        if not hmac.compare_digest(raw["sha256"], expected_checksum):
            raise ContinuityIntegrityError(
                "continuity integrity verification failed"
            )
        state = _state_from_payload(raw["payload"])
        if expected_core_id is not None:
            if not isinstance(expected_core_id, UUID):
                raise TypeError("expected_core_id must be a UUID or None")
            if state.core_id != expected_core_id:
                raise ContinuityIntegrityError(
                    "continuity belongs to a different Core identity"
                )
        if descriptor is not None:
            self._verify_descriptor(state, descriptor)
        return state

    load_strict = load

    @staticmethod
    def _verify_descriptor(
        state: CoreContinuityState,
        descriptor: CoreDescriptor,
    ) -> None:
        if not isinstance(descriptor, CoreDescriptor):
            raise TypeError("descriptor must be a CoreDescriptor")
        if (
            state.identity.full_name != descriptor.full_name
            or state.identity.core_number != descriptor.core_number
            or state.identity.slug != descriptor.slug
        ):
            raise ContinuityIntegrityError(
                "continuity identity does not match the Core descriptor"
            )
        if (
            descriptor.core_id is not None
            and descriptor.core_id != state.core_id
        ):
            raise ContinuityIntegrityError(
                "continuity core_id does not match the Core descriptor"
            )

    def verify(
        self,
        *,
        expected_core_id: UUID | None = None,
        descriptor: CoreDescriptor | None = None,
    ) -> bool:
        """Return True after verification; raise on any integrity failure."""
        self.load(expected_core_id=expected_core_id, descriptor=descriptor)
        return True

    def save(self, state: CoreContinuityState) -> None:
        """Atomically persist one state without allowing identity replacement."""
        if not isinstance(state, CoreContinuityState):
            raise TypeError("state must be CoreContinuityState")
        if self.path.exists():
            existing = self.load()
            if existing.identity != state.identity:
                raise ContinuityIntegrityError(
                    "continuity identity replacement is forbidden"
                )
            if state.revision < existing.revision:
                raise ContinuityIntegrityError(
                    "continuity revision cannot move backward"
                )
            if state.updated_at < existing.updated_at:
                raise ContinuityIntegrityError(
                    "continuity timestamp cannot move backward"
                )
            if not set(existing.memory_ids).issubset(state.memory_ids):
                raise ContinuityIntegrityError(
                    "continuity memories cannot be removed or replaced"
                )
        payload = _payload(state)
        envelope = {
            "schema": CONTINUITY_SCHEMA,
            "payload": payload,
            "sha256": _checksum(payload),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        )

    def switch_runtime(
        self,
        *,
        model_id: str | None,
        provider_id: str | None,
        process_id: str | None,
        now: datetime,
    ) -> CoreContinuityState:
        """Change the serving model/provider/process while preserving identity."""
        state = self.load()
        updated = state.with_runtime(
            model_id=model_id,
            provider_id=provider_id,
            process_id=process_id,
            now=now,
        )
        self.save(updated)
        return updated

    def record_memory(
        self,
        memory_id: UUID,
        *,
        now: datetime,
    ) -> CoreContinuityState:
        state = self.load()
        updated = state.with_memory(memory_id, now=now)
        if updated is not state:
            self.save(updated)
        return updated
