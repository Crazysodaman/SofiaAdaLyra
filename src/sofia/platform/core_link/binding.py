"""Protected local Core Link binding registry.

This registry is deliberately not canonical Core state.  It stores only the
minimum enrolled destination identity and local client routing metadata.  It
never stores a Core database, persona, transcript, reusable execution grant,
or credential material; ``credential_ref`` points at an OS/Platform secret
owner.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import re
from typing import Mapping

from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.state.private_file import (
    assert_owner_private_path,
    atomic_write_private_text,
    ensure_owner_private_directory,
)
from sofia.sdk.contracts import ProtocolVersion


CORE_LINK_BINDING_STORE_ENV = "SOFIA_CORE_LINK_BINDING_STORE"
_STORE_SCHEMA = "companion.platform.core_link_store.v1"
_BINDING_SCHEMA = "companion.platform.core_link.v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
_CREDENTIAL_REF = re.compile(
    r"^(?:os-keystore|secret-store):[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$"
)
_SCOPE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class CoreLinkBindingState(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    VERIFYING = "verifying"
    ACTIVE = "active"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class CoreLinkBinding:
    binding_id: str
    local_platform_id: str
    remote_platform_id: str
    remote_core_identity_id: str
    remote_core_generation: int
    endpoint_id: str
    credential_ref: str
    trust_anchor_ref: str
    audience_id: str
    granted_scopes: tuple[str, ...]
    protocol_version: ProtocolVersion
    state: CoreLinkBindingState
    revision: int
    created_at: datetime
    updated_at: datetime
    last_verified_contact_at: datetime | None = None

    def __post_init__(self) -> None:
        for label in (
            "binding_id", "local_platform_id", "remote_platform_id",
            "remote_core_identity_id", "endpoint_id", "audience_id",
        ):
            _identifier(getattr(self, label), label)
        if type(self.remote_core_generation) is not int or self.remote_core_generation < 1:
            raise ValueError("remote_core_generation must be positive")
        if not isinstance(self.credential_ref, str) or _CREDENTIAL_REF.fullmatch(
            self.credential_ref
        ) is None:
            raise ValueError("credential_ref must be a protected secret-store reference")
        if not isinstance(self.trust_anchor_ref, str) or _FINGERPRINT.fullmatch(
            self.trust_anchor_ref
        ) is None:
            raise ValueError("trust_anchor_ref must be an exact SHA-256 fingerprint")
        if (
            not isinstance(self.granted_scopes, tuple)
            or not self.granted_scopes
            or len(self.granted_scopes) > 32
            or any(_SCOPE.fullmatch(scope) is None for scope in self.granted_scopes)
            or len(set(self.granted_scopes)) != len(self.granted_scopes)
        ):
            raise ValueError("granted_scopes must be a bounded unique scope tuple")
        if not isinstance(self.protocol_version, ProtocolVersion):
            raise TypeError("protocol_version must be ProtocolVersion")
        if not isinstance(self.state, CoreLinkBindingState):
            raise TypeError("state must be CoreLinkBindingState")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        created = _utc(self.created_at, "created_at")
        updated = _utc(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot precede created_at")
        if self.last_verified_contact_at is not None:
            contact = _utc(self.last_verified_contact_at, "last_verified_contact_at")
            if contact < created or contact > updated:
                raise ValueError("last verified contact must fall within binding history")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": _BINDING_SCHEMA,
            "binding_id": self.binding_id,
            "local_platform_id": self.local_platform_id,
            "remote_platform_id": self.remote_platform_id,
            "remote_core_identity_id": self.remote_core_identity_id,
            "remote_core_generation": self.remote_core_generation,
            "endpoint_id": self.endpoint_id,
            "credential_ref": self.credential_ref,
            "trust_anchor_ref": self.trust_anchor_ref,
            "audience_id": self.audience_id,
            "granted_scopes": list(self.granted_scopes),
            "protocol_version": str(self.protocol_version),
            "state": self.state.value,
            "revision": self.revision,
            "created_at": _utc(self.created_at, "created_at").isoformat(),
            "updated_at": _utc(self.updated_at, "updated_at").isoformat(),
            "last_verified_contact_at": (
                None if self.last_verified_contact_at is None
                else _utc(self.last_verified_contact_at, "last_verified_contact_at").isoformat()
            ),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "CoreLinkBinding":
        keys = {
            "schema", "binding_id", "local_platform_id", "remote_platform_id",
            "remote_core_identity_id", "remote_core_generation", "endpoint_id",
            "credential_ref", "trust_anchor_ref", "audience_id", "granted_scopes",
            "protocol_version", "state", "revision", "created_at", "updated_at",
            "last_verified_contact_at",
        }
        if not isinstance(payload, Mapping) or set(payload) != keys:
            raise ValueError("Core Link binding must contain exactly reviewed fields")
        if payload["schema"] != _BINDING_SCHEMA:
            raise ValueError("unsupported Core Link binding schema")
        scopes = payload["granted_scopes"]
        if not isinstance(scopes, list):
            raise ValueError("granted_scopes must be a list")
        try:
            contact_raw = payload["last_verified_contact_at"]
            return cls(
                binding_id=payload["binding_id"],
                local_platform_id=payload["local_platform_id"],
                remote_platform_id=payload["remote_platform_id"],
                remote_core_identity_id=payload["remote_core_identity_id"],
                remote_core_generation=payload["remote_core_generation"],
                endpoint_id=payload["endpoint_id"],
                credential_ref=payload["credential_ref"],
                trust_anchor_ref=payload["trust_anchor_ref"],
                audience_id=payload["audience_id"],
                granted_scopes=tuple(scopes),
                protocol_version=ProtocolVersion.parse(payload["protocol_version"]),
                state=CoreLinkBindingState(payload["state"]),
                revision=payload["revision"],
                created_at=datetime.fromisoformat(payload["created_at"]),
                updated_at=datetime.fromisoformat(payload["updated_at"]),
                last_verified_contact_at=(
                    None if contact_raw is None
                    else datetime.fromisoformat(contact_raw)
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Core Link binding is invalid") from exc

    def redacted_status(self) -> dict[str, object]:
        return {
            "binding_id": self.binding_id,
            "remote_platform_id": self.remote_platform_id,
            "remote_core_identity_id": self.remote_core_identity_id,
            "remote_core_generation": self.remote_core_generation,
            "endpoint_id": self.endpoint_id,
            "state": self.state.value,
            "revision": self.revision,
            "protocol_version": str(self.protocol_version),
            "last_verified_contact_at": (
                None if self.last_verified_contact_at is None
                else _utc(self.last_verified_contact_at, "last_verified_contact_at").isoformat()
            ),
        }


@dataclass(frozen=True, slots=True)
class CoreLinkStoreSnapshot:
    revision: int
    selected_binding_id: str | None
    bindings: tuple[CoreLinkBinding, ...]

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("store revision must be nonnegative")
        if not isinstance(self.bindings, tuple) or any(
            not isinstance(binding, CoreLinkBinding) for binding in self.bindings
        ):
            raise TypeError("bindings must contain CoreLinkBinding values")
        ids = tuple(binding.binding_id for binding in self.bindings)
        if len(set(ids)) != len(ids):
            raise ValueError("binding IDs must be unique")
        if self.selected_binding_id is not None and self.selected_binding_id not in ids:
            raise ValueError("selected binding must exist")
        selected = self.selected()
        if selected is not None and selected.state not in {
            CoreLinkBindingState.ACTIVE, CoreLinkBindingState.OFFLINE,
        }:
            raise ValueError("selected binding must be active or explicitly offline")

    def selected(self) -> CoreLinkBinding | None:
        return next(
            (item for item in self.bindings if item.binding_id == self.selected_binding_id),
            None,
        )


class CoreLinkBindingStore:
    """Atomic local registry with whole-store and per-binding CAS."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if (
            not self.path.is_absolute()
            or self.path.name in {"", ".", ".."}
            or self.path.suffix.casefold() != ".json"
        ):
            raise ValueError("Core Link binding store must be an absolute JSON file path")
        self._lock = StateProcessLock(
            self.path, resource="core-link-bindings", owner_label="Core Link binding writer",
        )

    def _secure_parent(self) -> None:
        ensure_owner_private_directory(self.path.parent)

    def load(self) -> CoreLinkStoreSnapshot:
        if not self.path.exists():
            return CoreLinkStoreSnapshot(0, None, ())
        self._secure_parent()
        assert_owner_private_path(self.path, directory=False)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Core Link binding store is unreadable or corrupt") from exc
        keys = {"schema", "revision", "selected_binding_id", "bindings"}
        if not isinstance(payload, dict) or set(payload) != keys or payload["schema"] != _STORE_SCHEMA:
            raise ValueError("Core Link store has an unsupported or malformed schema")
        raw_bindings = payload["bindings"]
        if not isinstance(raw_bindings, list) or len(raw_bindings) > 128:
            raise ValueError("Core Link store bindings must be a bounded list")
        return CoreLinkStoreSnapshot(
            revision=payload["revision"],
            selected_binding_id=payload["selected_binding_id"],
            bindings=tuple(CoreLinkBinding.from_payload(item) for item in raw_bindings),
        )

    def _write(self, snapshot: CoreLinkStoreSnapshot) -> None:
        self._secure_parent()
        payload = {
            "schema": _STORE_SCHEMA,
            "revision": snapshot.revision,
            "selected_binding_id": snapshot.selected_binding_id,
            "bindings": [item.to_payload() for item in snapshot.bindings],
        }
        atomic_write_private_text(
            self.path, json.dumps(payload, sort_keys=True) + "\n"
        )

    @staticmethod
    def _require_store_revision(
        snapshot: CoreLinkStoreSnapshot, expected_store_revision: int,
    ) -> None:
        if type(expected_store_revision) is not int or expected_store_revision < 0:
            raise ValueError("expected_store_revision must be nonnegative")
        if snapshot.revision != expected_store_revision:
            raise RuntimeError("Core Link store revision conflict")

    def add_pending(
        self, binding: CoreLinkBinding, *, expected_store_revision: int,
    ) -> CoreLinkStoreSnapshot:
        if binding.state is not CoreLinkBindingState.PENDING_APPROVAL or binding.revision != 1:
            raise ValueError("new binding must be pending approval at revision 1")
        with self._lock:
            current = self.load()
            self._require_store_revision(current, expected_store_revision)
            if any(item.binding_id == binding.binding_id for item in current.bindings):
                raise RuntimeError("Core Link binding ID already exists")
            updated = CoreLinkStoreSnapshot(
                current.revision + 1, current.selected_binding_id,
                tuple(sorted((*current.bindings, binding), key=lambda item: item.binding_id)),
            )
            self._write(updated)
            return updated

    def transition(
        self, binding_id: str, *, expected_binding_revision: int,
        expected_store_revision: int, state: CoreLinkBindingState, at: datetime,
    ) -> CoreLinkStoreSnapshot:
        _identifier(binding_id, "binding_id")
        if not isinstance(state, CoreLinkBindingState):
            raise TypeError("state must be CoreLinkBindingState")
        moment = _utc(at, "at")
        allowed = {
            CoreLinkBindingState.PENDING_APPROVAL: {
                CoreLinkBindingState.VERIFYING, CoreLinkBindingState.REVOKED,
            },
            CoreLinkBindingState.VERIFYING: {
                CoreLinkBindingState.QUARANTINED, CoreLinkBindingState.REVOKED,
            },
            CoreLinkBindingState.ACTIVE: {
                CoreLinkBindingState.OFFLINE, CoreLinkBindingState.QUARANTINED,
                CoreLinkBindingState.REVOKED,
            },
            CoreLinkBindingState.OFFLINE: {
                CoreLinkBindingState.ACTIVE, CoreLinkBindingState.QUARANTINED,
                CoreLinkBindingState.REVOKED,
            },
            CoreLinkBindingState.QUARANTINED: {
                CoreLinkBindingState.VERIFYING, CoreLinkBindingState.REVOKED,
            },
            CoreLinkBindingState.REVOKED: set(),
        }
        with self._lock:
            current = self.load()
            self._require_store_revision(current, expected_store_revision)
            bindings = list(current.bindings)
            index = next((i for i, item in enumerate(bindings) if item.binding_id == binding_id), None)
            if index is None:
                raise KeyError(binding_id)
            binding = bindings[index]
            if binding.revision != expected_binding_revision:
                raise RuntimeError("Core Link binding revision conflict")
            if state not in allowed[binding.state]:
                raise ValueError(f"invalid Core Link transition {binding.state.value} -> {state.value}")
            if moment < _utc(binding.updated_at, "binding.updated_at"):
                raise ValueError("transition time cannot precede current binding revision")
            bindings[index] = replace(
                binding, state=state, revision=binding.revision + 1, updated_at=moment,
            )
            selected = current.selected_binding_id
            if state in {CoreLinkBindingState.QUARANTINED, CoreLinkBindingState.REVOKED} and selected == binding_id:
                selected = None
            updated = CoreLinkStoreSnapshot(current.revision + 1, selected, tuple(bindings))
            self._write(updated)
            return updated

    def select(
        self, binding_id: str, *, expected_store_revision: int,
    ) -> CoreLinkStoreSnapshot:
        _identifier(binding_id, "binding_id")
        with self._lock:
            current = self.load()
            self._require_store_revision(current, expected_store_revision)
            binding = next((item for item in current.bindings if item.binding_id == binding_id), None)
            if binding is None:
                raise KeyError(binding_id)
            if binding.state not in {CoreLinkBindingState.ACTIVE, CoreLinkBindingState.OFFLINE}:
                raise PermissionError("only an active or explicitly offline binding may be selected")
            updated = CoreLinkStoreSnapshot(
                current.revision + 1, binding_id, current.bindings,
            )
            self._write(updated)
            return updated

    def reconcile_contact(
        self, binding_id: str, *, expected_binding_revision: int,
        expected_store_revision: int, remote_platform_id: str,
        remote_core_identity_id: str, remote_core_generation: int,
        endpoint_id: str, trust_anchor_ref: str, at: datetime,
    ) -> CoreLinkStoreSnapshot:
        """Record exact authenticated contact or quarantine any identity drift."""
        moment = _utc(at, "at")
        with self._lock:
            current = self.load()
            self._require_store_revision(current, expected_store_revision)
            bindings = list(current.bindings)
            index = next((i for i, item in enumerate(bindings) if item.binding_id == binding_id), None)
            if index is None:
                raise KeyError(binding_id)
            binding = bindings[index]
            if binding.revision != expected_binding_revision:
                raise RuntimeError("Core Link binding revision conflict")
            if binding.state not in {
                CoreLinkBindingState.VERIFYING,
                CoreLinkBindingState.ACTIVE,
                CoreLinkBindingState.OFFLINE,
            }:
                raise PermissionError(
                    "binding must be verifying, active, or offline for contact reconciliation"
                )
            if moment < _utc(binding.updated_at, "binding.updated_at"):
                raise ValueError("contact time cannot precede current binding revision")
            exact = (
                binding.remote_platform_id == remote_platform_id
                and binding.remote_core_identity_id == remote_core_identity_id
                and binding.remote_core_generation == remote_core_generation
                and binding.endpoint_id == endpoint_id
                and binding.trust_anchor_ref == trust_anchor_ref
            )
            state = CoreLinkBindingState.ACTIVE if exact else CoreLinkBindingState.QUARANTINED
            bindings[index] = replace(
                binding,
                state=state,
                revision=binding.revision + 1,
                updated_at=moment,
                last_verified_contact_at=(moment if exact else binding.last_verified_contact_at),
            )
            selected = current.selected_binding_id if exact else (
                None if current.selected_binding_id == binding_id else current.selected_binding_id
            )
            updated = CoreLinkStoreSnapshot(current.revision + 1, selected, tuple(bindings))
            self._write(updated)
            return updated

