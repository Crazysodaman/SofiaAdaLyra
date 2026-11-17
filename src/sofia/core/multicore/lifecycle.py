"""Governed adapter for independent Core definition and synthetic lifecycle.

This module deliberately owns no second signature verifier.  Definition bytes
are checked by :class:`sofia.platform.ops.core_definition.CoreDefinitionVerifier`;
process and component lifecycle evidence belongs to
:class:`sofia.platform.ops.synthetic_core_lifecycle.SyntheticCoreLifecycle`.
The adapter adds profile/definition registration and requires an injected
authorization callback for every source-level operation.  A status response
only claims what was observed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Callable, Protocol
from uuid import UUID

from sofia.core.multicore.profiles import CoreProfile
from sofia.platform.ops.core_definition import CoreDefinitionVerifier
from sofia.platform.ops.platform_install import InstallAuthority
from sofia.platform.ops.synthetic_core_lifecycle import (
    CoreProcessObservation,
    SyntheticCoreLifecycle,
    SyntheticCoreLifecycleReceipt,
    SyntheticCoreOutcome,
    SyntheticCoreState,
)
from sofia.sdk.core_definition import CoreDefinition


class MulticoreLifecycleError(RuntimeError):
    """A source-level multicore lifecycle contract was violated."""


class LifecycleRegistrationRequired(MulticoreLifecycleError):
    """The Core definition was not verified and registered in this process."""


class LifecycleRegistrationConflict(MulticoreLifecycleError):
    """A different verified definition already occupies this Core UUID."""


class LifecycleAuthorizationDenied(PermissionError):
    """The injected authority callback refused the exact operation."""


class LifecycleEvidenceError(MulticoreLifecycleError):
    """The delegated lifecycle did not produce evidence for the claimed state."""


class LifecycleOperation(str, Enum):
    INSTALL = "install"
    ACTIVATE = "activate"
    STATUS = "status"
    DEACTIVATE = "deactivate"
    RECOVER = "recover"
    REMOVE = "remove"


class LifecycleAuthorizer(Protocol):
    def __call__(
        self,
        operation: str,
        core_id: str,
        fingerprint: str,
        expected_generation: int,
    ) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class CoreDefinitionRegistration:
    """Verified definition paired with its canonical profile; no permit."""

    profile: CoreProfile
    definition: CoreDefinition
    registered_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.profile, CoreProfile):
            raise TypeError("profile must be a CoreProfile")
        if not isinstance(self.definition, CoreDefinition):
            raise TypeError("definition must be a CoreDefinition")
        core_id = self.profile.descriptor.core_id
        if core_id is None or self.definition.identity.identity_id != core_id:
            raise MulticoreLifecycleError(
                "registration definition does not belong to the profile Core UUID"
            )
        if self.registered_at.tzinfo is None or self.registered_at.utcoffset() is None:
            raise MulticoreLifecycleError("registration time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CoreLifecycleStatus:
    """Observed lifecycle evidence; absence of evidence is not a state claim."""

    core_id: str
    installed: bool
    active: bool
    state: SyntheticCoreState | None
    generation: int | None
    artifact_sha256: str | None
    evidence: tuple[str, ...]
    uncertainties: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.active and not self.installed:
            raise MulticoreLifecycleError(
                "active status requires installed component evidence"
            )


def _canonical_uuid(value: object, label: str) -> str:
    if isinstance(value, UUID):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a canonical UUID") from exc
    else:
        raise ValueError(f"{label} must be a canonical UUID")
    if parsed.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return str(parsed)


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


class MulticoreCoreLifecycle:
    """One-writer adapter over verified definitions and synthetic lifecycle."""

    def __init__(
        self,
        *,
        synthetic: SyntheticCoreLifecycle,
        authorization: LifecycleAuthorizer,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        for method in ("install", "activate", "stop", "remove", "reconcile"):
            if not callable(getattr(synthetic, method, None)):
                raise TypeError(
                    "synthetic lifecycle must implement install, activate, stop, "
                    "remove and reconcile"
                )
        for attribute in ("store", "installer", "backend"):
            if getattr(synthetic, attribute, None) is None:
                raise TypeError(f"synthetic lifecycle must expose {attribute}")
        if not callable(authorization):
            raise TypeError("authorization callback must be callable")
        self.synthetic = synthetic
        self._authorization = authorization
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._registrations: dict[str, CoreDefinitionRegistration] = {}
        self._lock = RLock()

    def _now(self) -> datetime:
        return _aware(self._clock(), "clock")

    def _authorize(
        self,
        operation: LifecycleOperation,
        core_id: str,
        fingerprint: str,
        generation: int,
    ) -> None:
        try:
            decision = self._authorization(
                operation.value, core_id, fingerprint, generation,
            )
        except Exception as exc:
            raise LifecycleAuthorizationDenied(
                f"{operation.value} authorization failed"
            ) from exc
        if decision is not True:
            raise LifecycleAuthorizationDenied(
                f"{operation.value} authorization denied for Core {core_id}"
            )

    def register_definition(
        self,
        profile: CoreProfile,
        definition: CoreDefinition,
        *,
        verifier: CoreDefinitionVerifier,
        signature_b64: str,
        signer_key_id: str,
        assets_root,
        runtime_release_sha256: str,
        minimum_revision: int,
    ) -> CoreDefinitionRegistration:
        """Verify through the existing verifier and remember the inert result."""
        if not isinstance(profile, CoreProfile):
            raise TypeError("profile must be a CoreProfile")
        if not isinstance(verifier, CoreDefinitionVerifier):
            raise TypeError("verifier must be the existing CoreDefinitionVerifier")
        core_id = profile.descriptor.core_id
        if core_id is None:
            raise ValueError("profile requires an externally supplied Core UUID")
        expected_core_id = str(core_id)
        try:
            verified = verifier.verify(
                definition.to_payload(),
                signature_b64=signature_b64,
                signer_key_id=signer_key_id,
                assets_root=assets_root,
                expected_core_id=expected_core_id,
                expected_runtime_sha256=runtime_release_sha256,
                minimum_revision=minimum_revision,
            )
        except (PermissionError, ValueError, TypeError, KeyError) as exc:
            raise MulticoreLifecycleError("Core definition verification failed") from exc
        if verified.identity.identity_id != core_id:
            raise MulticoreLifecycleError("verified definition Core UUID differs")
        if verified.name != profile.descriptor.full_name:
            raise MulticoreLifecycleError("verified definition name differs from profile")
        if (
            verified.constitution.sha256 != profile.constitution_sha256
            or verified.constitution.size_bytes != profile.constitution_size
            or verified.personality.sha256 != profile.personality_sha256
            or verified.personality.size_bytes != profile.personality_size
        ):
            raise MulticoreLifecycleError(
                "verified definition personal assets differ from the profile"
            )
        registration = CoreDefinitionRegistration(
            profile=profile,
            definition=verified,
            registered_at=self._now(),
        )
        with self._lock:
            existing = self._registrations.get(expected_core_id)
            if existing is not None:
                if existing.definition.digest != verified.digest:
                    raise LifecycleRegistrationConflict(
                        "a different verified definition is already registered"
                    )
                return existing
            self._registrations[expected_core_id] = registration
        return registration

    def registration(self, core_id: UUID | str) -> CoreDefinitionRegistration:
        canonical = _canonical_uuid(core_id, "core_id")
        with self._lock:
            registration = self._registrations.get(canonical)
        if registration is None:
            raise LifecycleRegistrationRequired(
                "Core definition must be verified and registered before this operation"
            )
        return registration

    def _binding(self, owner_id: str, core_id: str):
        return self.synthetic.store.binding(owner_id, core_id)

    def install(
        self,
        *,
        owner_id: str,
        core_id: UUID | str,
        lineage_id: UUID | str,
        artifact,
        wheel_path,
        authority: InstallAuthority,
        approval_id: str | None = None,
        expected_generation: int = 0,
    ) -> SyntheticCoreLifecycleReceipt:
        core = _canonical_uuid(core_id, "core_id")
        lineage = _canonical_uuid(lineage_id, "lineage_id")
        registration = self.registration(core)
        self._authorize(
            LifecycleOperation.INSTALL, core, artifact.sha256, expected_generation,
        )
        receipt = self.synthetic.install(
            owner_id=owner_id,
            core_id=core,
            lineage_id=lineage,
            artifact=artifact,
            wheel_path=wheel_path,
            authority=authority,
            approval_id=approval_id,
            expected_generation=expected_generation,
            synthetic=True,
        )
        if (
            receipt.outcome is not SyntheticCoreOutcome.SUCCEEDED
            or receipt.state is not SyntheticCoreState.INSTALLED
            or receipt.core_id != core
        ):
            raise LifecycleEvidenceError(
                "install receipt does not prove an installed synthetic Core"
            )
        if registration.definition.identity.identity_id != UUID(core):
            raise LifecycleEvidenceError("registration identity changed during install")
        return receipt

    def activate(
        self,
        *,
        owner_id: str,
        core_id: UUID | str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        core = _canonical_uuid(core_id, "core_id")
        registration = self.registration(core)
        binding = self._binding(owner_id, core)
        fingerprint = (
            registration.definition.digest if binding is None
            else binding.artifact_sha256
        )
        self._authorize(
            LifecycleOperation.ACTIVATE, core, fingerprint, expected_generation,
        )
        receipt = self.synthetic.activate(
            owner_id=owner_id,
            core_id=core,
            expected_generation=expected_generation,
        )
        if (
            receipt.outcome is not SyntheticCoreOutcome.SUCCEEDED
            or receipt.state is not SyntheticCoreState.ACTIVE
        ):
            raise LifecycleEvidenceError(
                "activation receipt does not prove an active synthetic Core"
            )
        return receipt

    def deactivate(
        self,
        *,
        owner_id: str,
        core_id: UUID | str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        core = _canonical_uuid(core_id, "core_id")
        registration = self.registration(core)
        binding = self._binding(owner_id, core)
        fingerprint = (
            registration.definition.digest if binding is None
            else binding.artifact_sha256
        )
        self._authorize(
            LifecycleOperation.DEACTIVATE, core, fingerprint, expected_generation,
        )
        receipt = self.synthetic.stop(
            owner_id=owner_id,
            core_id=core,
            expected_generation=expected_generation,
        )
        if receipt.state is SyntheticCoreState.ACTIVE:
            raise LifecycleEvidenceError(
                "deactivation receipt still claims an active synthetic Core"
            )
        if (
            receipt.outcome not in {
                SyntheticCoreOutcome.SUCCEEDED,
                SyntheticCoreOutcome.ALREADY_STOPPED,
            }
        ):
            raise LifecycleEvidenceError(
                "deactivation receipt does not prove a stopped synthetic Core"
            )
        return receipt

    def status(self, *, owner_id: str, core_id: UUID | str) -> CoreLifecycleStatus:
        core = _canonical_uuid(core_id, "core_id")
        with self._lock:
            registration = self._registrations.get(core)
        binding = self._binding(owner_id, core)
        fingerprint = (
            registration.definition.digest if registration is not None
            else ("-" if binding is None else binding.artifact_sha256)
        )
        generation = 0 if binding is None else binding.generation
        self._authorize(LifecycleOperation.STATUS, core, fingerprint, generation)
        if binding is None:
            return CoreLifecycleStatus(
                core_id=core,
                installed=False,
                active=False,
                state=None,
                generation=None,
                artifact_sha256=None,
                evidence=("no lifecycle binding observed",),
            )
        evidence = [f"binding state={binding.state.value}"]
        uncertainties: list[str] = []
        try:
            root = self.synthetic.installer.installed_component_root(
                binding.version, binding.artifact_sha256,
            )
        except Exception:
            root = None
            uncertainties.append("installed component root could not be verified")
        installed = root is not None
        evidence.append(
            "installed component root present" if installed
            else "installed component root absent"
        )
        active = False
        if binding.state is SyntheticCoreState.ACTIVE:
            try:
                observed = self.synthetic.backend.observe(
                    core_id=binding.core_id,
                    lineage_id=binding.lineage_id,
                    generation=binding.generation,
                )
            except Exception:
                observed = CoreProcessObservation.UNKNOWN
            if observed is CoreProcessObservation.RUNNING:
                evidence.append("process observed running")
                active = installed
                if not installed:
                    uncertainties.append(
                        "process running without installed component evidence"
                    )
            elif observed is CoreProcessObservation.STOPPED:
                evidence.append("process observed stopped")
            else:
                evidence.append("process observation unknown")
                uncertainties.append("process state is unknown")
        else:
            evidence.append("binding is not active")
        return CoreLifecycleStatus(
            core_id=core,
            installed=installed,
            active=active,
            state=binding.state,
            generation=binding.generation,
            artifact_sha256=binding.artifact_sha256,
            evidence=tuple(evidence),
            uncertainties=tuple(uncertainties),
        )

    def recover(
        self,
        *,
        core_id: UUID | str | None = None,
    ) -> tuple[SyntheticCoreLifecycleReceipt, ...]:
        core = None if core_id is None else _canonical_uuid(core_id, "core_id")
        pending = self.synthetic.store.unresolved_operations(core)
        if core is None:
            self._authorize(LifecycleOperation.RECOVER, "*", "-", 0)
        seen: set[tuple[str, str, int]] = set()
        for operation in pending:
            key = (
                operation.core_id,
                operation.artifact_sha256,
                operation.expected_generation,
            )
            if key in seen:
                continue
            seen.add(key)
            self._authorize(
                LifecycleOperation.RECOVER,
                operation.core_id,
                operation.artifact_sha256,
                operation.expected_generation,
            )
        if core is not None and not pending:
            self._authorize(LifecycleOperation.RECOVER, core, "-", 0)
        return self.synthetic.reconcile()

    def remove(
        self,
        *,
        owner_id: str,
        core_id: UUID | str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        core = _canonical_uuid(core_id, "core_id")
        registration = self.registration(core)
        binding = self._binding(owner_id, core)
        fingerprint = (
            registration.definition.digest if binding is None
            else binding.artifact_sha256
        )
        self._authorize(
            LifecycleOperation.REMOVE, core, fingerprint, expected_generation,
        )
        receipt = self.synthetic.remove(
            owner_id=owner_id,
            core_id=core,
            expected_generation=expected_generation,
        )
        if receipt.outcome is SyntheticCoreOutcome.COMPONENT_RETAINED:
            raise LifecycleEvidenceError(
                "removal retained the installed component; removal is not proven"
            )
        if (
            receipt.outcome is SyntheticCoreOutcome.SUCCEEDED
            and receipt.state is not SyntheticCoreState.REMOVED
        ):
            raise LifecycleEvidenceError(
                "removal receipt does not prove a removed synthetic Core"
            )
        if receipt.outcome not in {
            SyntheticCoreOutcome.SUCCEEDED,
            SyntheticCoreOutcome.ALREADY_REMOVED,
        }:
            raise LifecycleEvidenceError(
                "removal receipt does not prove component removal"
            )
        return receipt


__all__ = [
    "CoreDefinitionRegistration",
    "CoreLifecycleStatus",
    "LifecycleAuthorizationDenied",
    "LifecycleAuthorizer",
    "LifecycleEvidenceError",
    "LifecycleOperation",
    "LifecycleRegistrationConflict",
    "LifecycleRegistrationRequired",
    "MulticoreCoreLifecycle",
    "MulticoreLifecycleError",
]
