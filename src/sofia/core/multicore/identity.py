"""Persistent independent Core identity records with writer fencing.

The store never allocates a Core UUID, never creates an identity for a missing
record, and never substitutes Sofía's canonical identity.  A caller supplies
the Core UUID.  Saving or loading identity metadata grants no authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Iterable, Mapping
from uuid import UUID

from sofia.core.multicore.contracts import CoreDescriptor, PersistentCoreIdentity
from sofia.platform.state.private_file import (
    assert_no_redirected_components,
    assert_not_protected_state_path,
    assert_owner_private_path,
    atomic_write_private_text,
    ensure_owner_private_directory,
)

IDENTITY_RECORD_SCHEMA = "aegis.core.multicore.identity_record.v1"
_WRITER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SLUG = re.compile(r"[a-z][a-z0-9-]{0,63}")


class MulticoreIdentityError(RuntimeError):
    """A persistent independent Core identity contract was violated."""


class CoreIdentityNotFound(MulticoreIdentityError):
    """No record exists for the requested Core UUID."""


class DuplicateCoreIdentity(MulticoreIdentityError):
    """A Core UUID, number or slug is already registered."""


class DuplicateActiveWriterGeneration(MulticoreIdentityError):
    """A writer generation is already active for this Core."""


class StaleWriterGeneration(MulticoreIdentityError):
    """A writer operation used an obsolete generation."""


class WriterFenceMismatch(MulticoreIdentityError):
    """A writer release did not match the active fence."""


class SofiaIdentitySubstitution(PermissionError):
    """The canonical Sofía identity cannot be stored as a multicore Core."""


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MulticoreIdentityError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _bounded(value: object, label: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise MulticoreIdentityError(f"{label} must be a bounded canonical identifier")
    return value


def _optional_identifier(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _bounded(value, label, _WRITER)


def _require_core_id(value: object) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError("an externally supplied nonzero Core UUID is required")
    return value


@dataclass(frozen=True, slots=True)
class WriterFence:
    """One active writer generation; duplicate active fences are refused."""

    writer_id: str
    generation: int
    claimed_at: datetime

    def __post_init__(self) -> None:
        _bounded(self.writer_id, "writer_id", _WRITER)
        if type(self.generation) is not int or self.generation < 1:
            raise MulticoreIdentityError("writer generation must be positive")
        _aware(self.claimed_at, "claimed_at")

    def to_payload(self) -> dict[str, object]:
        return {
            "writer_id": self.writer_id,
            "generation": self.generation,
            "claimed_at": self.claimed_at.astimezone(timezone.utc).isoformat(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "WriterFence":
        if not isinstance(value, Mapping) or set(value) != {
            "writer_id", "generation", "claimed_at",
        }:
            raise MulticoreIdentityError("writer fence fields differ")
        try:
            claimed_at = datetime.fromisoformat(str(value["claimed_at"]))
        except ValueError as exc:
            raise MulticoreIdentityError("writer fence time is invalid") from exc
        return cls(
            writer_id=value["writer_id"],
            generation=value["generation"],
            claimed_at=claimed_at,
        )


@dataclass(frozen=True, slots=True)
class CoreIdentityRecord:
    """Durable identity plus presentation-independent host selection metadata."""

    identity: PersistentCoreIdentity
    slug: str
    updated_at: datetime
    model_id: str | None = None
    provider_id: str | None = None
    writer_fence: WriterFence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, PersistentCoreIdentity):
            raise TypeError("identity must be a PersistentCoreIdentity")
        _bounded(self.slug, "slug", _SLUG)
        _aware(self.updated_at, "updated_at")
        if self.updated_at < self.identity.created_at:
            raise MulticoreIdentityError("updated_at cannot precede created_at")
        _optional_identifier(self.model_id, "model_id")
        _optional_identifier(self.provider_id, "provider_id")
        if self.writer_fence is not None:
            if not isinstance(self.writer_fence, WriterFence):
                raise TypeError("writer_fence must be a WriterFence")
            if self.writer_fence.generation != self.identity.generation:
                raise MulticoreIdentityError(
                    "writer fence generation must equal the identity generation"
                )

    def to_payload(self) -> dict[str, object]:
        identity = self.identity
        return {
            "schema": IDENTITY_RECORD_SCHEMA,
            "core_id": str(identity.core_id),
            "core_number": identity.core_number,
            "full_name": identity.full_name,
            "slug": identity.slug,
            "generation": identity.generation,
            "constitution_sha256": identity.constitution_sha256,
            "created_at": identity.created_at.astimezone(timezone.utc).isoformat(),
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "writer_fence": (
                None if self.writer_fence is None else self.writer_fence.to_payload()
            ),
        }

    @classmethod
    def from_payload(cls, value: object) -> "CoreIdentityRecord":
        fields = {
            "schema", "core_id", "core_number", "full_name", "slug", "generation",
            "constitution_sha256", "created_at", "updated_at", "model_id",
            "provider_id", "writer_fence",
        }
        if not isinstance(value, Mapping) or set(value) != fields:
            raise MulticoreIdentityError("identity record fields differ")
        if value["schema"] != IDENTITY_RECORD_SCHEMA:
            raise MulticoreIdentityError("unsupported identity record schema")
        try:
            core_id = UUID(value["core_id"])
            created_at = datetime.fromisoformat(str(value["created_at"]))
            updated_at = datetime.fromisoformat(str(value["updated_at"]))
            identity = PersistentCoreIdentity(
                core_id=core_id,
                core_number=value["core_number"],
                full_name=value["full_name"],
                slug=value["slug"],
                generation=value["generation"],
                constitution_sha256=value["constitution_sha256"],
                created_at=created_at,
            )
            fence = value["writer_fence"]
            return cls(
                identity=identity,
                slug=value["slug"],
                updated_at=updated_at,
                model_id=value["model_id"],
                provider_id=value["provider_id"],
                writer_fence=None if fence is None else WriterFence.from_payload(fence),
            )
        except (TypeError, ValueError, KeyError) as exc:
            if isinstance(exc, MulticoreIdentityError):
                raise
            raise MulticoreIdentityError("identity record is invalid") from exc


class MulticoreIdentityStore:
    """Owner-private per-Core identity records with duplicate/fence checks."""

    def __init__(
        self,
        directory: Path | str,
        *,
        sofia_instance_id: UUID | None = None,
        protected_identity_ids: Iterable[UUID] = (),
    ) -> None:
        self.directory = Path(directory)
        if not self.directory.is_absolute():
            raise ValueError("multicore identity directory must be absolute")
        self._lock = RLock()
        self._protected = set()
        if sofia_instance_id is not None:
            self._protected.add(_require_core_id(sofia_instance_id))
        for core_id in protected_identity_ids:
            self._protected.add(_require_core_id(core_id))
        for component in (self.directory, *self.directory.parents):
            assert_not_protected_state_path(component)
        assert_no_redirected_components(self.directory, include_leaf=True)
        ensure_owner_private_directory(self.directory)

    def _path(self, core_id: UUID) -> Path:
        return self.directory / f"{_require_core_id(core_id)}.json"

    def _assert_safe_target(self, path: Path) -> None:
        for component in (path, *path.parents):
            assert_not_protected_state_path(component)
        assert_no_redirected_components(path, include_leaf=True)

    def _claim_new_path(self, path: Path) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise DuplicateCoreIdentity("Core identity record already exists") from exc
        except OSError as exc:
            raise MulticoreIdentityError("Core identity record could not be created") from exc
        else:
            os.close(descriptor)

    def _assert_not_substituting_sofia(self, core_id: UUID) -> None:
        if core_id in self._protected:
            raise SofiaIdentitySubstitution(
                "the canonical Sofía identity cannot be stored as an independent Core"
            )

    def _read(self, path: Path) -> CoreIdentityRecord:
        self._assert_safe_target(path)
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MulticoreIdentityError("identity record is unreadable or corrupt") from exc
        record = CoreIdentityRecord.from_payload(payload)
        if path.name != f"{record.identity.core_id}.json":
            raise MulticoreIdentityError(
                "identity record filename does not match its Core UUID"
            )
        return record

    def _records_unlocked(self) -> tuple[CoreIdentityRecord, ...]:
        assert_no_redirected_components(self.directory, include_leaf=True)
        paths = sorted(
            path for path in self.directory.glob("*.json")
            if path.is_file()
        )
        records: list[CoreIdentityRecord] = []
        seen_ids: set[UUID] = set()
        seen_numbers: set[int] = set()
        seen_slugs: set[str] = set()
        for path in paths:
            record = self._read(path)
            identity = record.identity
            if identity.core_id in seen_ids:
                raise DuplicateCoreIdentity("duplicate Core UUID in identity store")
            if identity.core_number in seen_numbers:
                raise DuplicateCoreIdentity("duplicate Core number in identity store")
            if record.slug in seen_slugs:
                raise DuplicateCoreIdentity("duplicate Core slug in identity store")
            seen_ids.add(identity.core_id)
            seen_numbers.add(identity.core_number)
            seen_slugs.add(record.slug)
            records.append(record)
        return tuple(records)

    def _write(self, record: CoreIdentityRecord) -> None:
        if not isinstance(record, CoreIdentityRecord):
            raise TypeError("record must be a CoreIdentityRecord")
        self._assert_not_substituting_sofia(record.identity.core_id)
        path = self._path(record.identity.core_id)
        self._assert_safe_target(path)
        content = json.dumps(
            record.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ) + "\n"
        atomic_write_private_text(path, content)
        assert_owner_private_path(path, directory=False)

    def register(
        self,
        *,
        core_id: UUID,
        core_number: int,
        full_name: str,
        slug: str,
        constitution_sha256: str,
        generation: int = 1,
        created_at: datetime | None = None,
    ) -> CoreIdentityRecord:
        """Register a new Core exactly once; UUIDs are always supplied."""
        supplied = _require_core_id(core_id)
        self._assert_not_substituting_sofia(supplied)
        now = _aware(created_at or datetime.now(timezone.utc), "created_at")
        identity = PersistentCoreIdentity(
            core_id=supplied,
            core_number=core_number,
            full_name=full_name,
            slug=slug,
            generation=generation,
            constitution_sha256=constitution_sha256,
            created_at=now,
        )
        record = CoreIdentityRecord(
            identity=identity,
            slug=slug,
            updated_at=now,
        )
        with self._lock:
            for existing in self._records_unlocked():
                if existing.identity.core_id == supplied:
                    raise DuplicateCoreIdentity(
                        "Core UUID is already registered"
                    )
                if existing.identity.core_number == core_number:
                    raise DuplicateCoreIdentity(
                        "Core number is already registered"
                    )
                if existing.slug == slug:
                    raise DuplicateCoreIdentity("Core slug is already registered")
            path = self._path(supplied)
            self._claim_new_path(path)
            self._write(record)
        return record

    def register_descriptor(
        self,
        descriptor: CoreDescriptor,
        *,
        constitution_sha256: str,
        created_at: datetime | None = None,
    ) -> CoreIdentityRecord:
        if not isinstance(descriptor, CoreDescriptor):
            raise TypeError("descriptor must be a CoreDescriptor")
        if descriptor.core_id is None:
            raise ValueError("descriptor requires an externally supplied Core UUID")
        if _SHA256.fullmatch(constitution_sha256) is None:
            raise ValueError("constitution_sha256 must be lowercase SHA-256")
        return self.register(
            core_id=descriptor.core_id,
            core_number=descriptor.core_number,
            full_name=descriptor.full_name,
            slug=descriptor.slug,
            constitution_sha256=constitution_sha256,
            created_at=created_at,
        )

    def load(self, core_id: UUID) -> CoreIdentityRecord:
        """Load an existing record; a missing UUID never falls back to Sofía."""
        supplied = _require_core_id(core_id)
        self._assert_not_substituting_sofia(supplied)
        with self._lock:
            path = self._path(supplied)
            self._assert_safe_target(path)
            if not path.exists():
                raise CoreIdentityNotFound("Core identity record does not exist")
            return self._read(path)

    def load_all(self) -> tuple[CoreIdentityRecord, ...]:
        with self._lock:
            return self._records_unlocked()

    def claim_writer(
        self,
        core_id: UUID,
        *,
        writer_id: str,
        expected_generation: int,
        claimed_at: datetime | None = None,
    ) -> CoreIdentityRecord:
        """Take the single active writer slot for the next generation."""
        supplied = _require_core_id(core_id)
        writer = _bounded(writer_id, "writer_id", _WRITER)
        if type(expected_generation) is not int or expected_generation < 1:
            raise ValueError("expected_generation must be positive")
        at = _aware(claimed_at or datetime.now(timezone.utc), "claimed_at")
        with self._lock:
            record = self.load(supplied)
            if record.writer_fence is not None:
                raise DuplicateActiveWriterGeneration(
                    "another writer generation is already active for this Core"
                )
            if record.identity.generation != expected_generation:
                raise StaleWriterGeneration(
                    "writer claim used a stale Core generation"
                )
            generation = record.identity.generation + 1
            updated = replace(
                record,
                identity=replace(record.identity, generation=generation),
                writer_fence=WriterFence(writer, generation, at),
                updated_at=at,
            )
            self._write(updated)
            return updated

    def release_writer(
        self,
        core_id: UUID,
        *,
        writer_id: str,
        generation: int,
        released_at: datetime | None = None,
    ) -> CoreIdentityRecord:
        """Release the exact active writer fence; identity UUID is unchanged."""
        supplied = _require_core_id(core_id)
        writer = _bounded(writer_id, "writer_id", _WRITER)
        at = _aware(released_at or datetime.now(timezone.utc), "released_at")
        with self._lock:
            record = self.load(supplied)
            fence = record.writer_fence
            if (
                fence is None
                or fence.writer_id != writer
                or fence.generation != generation
            ):
                raise WriterFenceMismatch(
                    "writer release does not match the active Core fence"
                )
            updated = replace(record, writer_fence=None, updated_at=at)
            self._write(updated)
            return updated

    def bind_model(
        self,
        core_id: UUID,
        *,
        model_id: str | None,
        provider_id: str | None,
        bound_at: datetime | None = None,
    ) -> CoreIdentityRecord:
        """Select a cognition engine without changing Core identity continuity."""
        supplied = _require_core_id(core_id)
        at = _aware(bound_at or datetime.now(timezone.utc), "bound_at")
        with self._lock:
            record = self.load(supplied)
            updated = replace(
                record,
                model_id=_optional_identifier(model_id, "model_id"),
                provider_id=_optional_identifier(provider_id, "provider_id"),
                updated_at=at,
            )
            self._write(updated)
            return updated


__all__ = [
    "CoreIdentityNotFound",
    "CoreIdentityRecord",
    "DuplicateActiveWriterGeneration",
    "DuplicateCoreIdentity",
    "IDENTITY_RECORD_SCHEMA",
    "MulticoreIdentityError",
    "MulticoreIdentityStore",
    "SofiaIdentitySubstitution",
    "StaleWriterGeneration",
    "WriterFence",
    "WriterFenceMismatch",
]
