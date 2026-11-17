"""Read/registration/display adapter for independent multi-Core management.

The adapter projects *actual* Core definitions and states.  A definition is not
installation evidence, and neither is an active process.  The display therefore
reports ``installed`` and ``active`` only from explicit evidence and labels
missing, stale or unavailable evidence as unknown.

Owner-visible participation, notification and STOP controls are interfaces
only.  No control mutates state unless a caller-supplied owner authorizer and
the optional operator STOP gate permit this exact operation.  A Core-free
Platform is a valid state and does not require any Core to exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from threading import RLock
from typing import Protocol
from uuid import UUID

from sofia.core.multicore.contracts import EvidenceState, LifecycleState
from sofia.platform.inference import ModelIdentity

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _text(value: object, label: str, *, maximum: int = 160) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise ValueError(f"{label} must be bounded visible text")
    return value


class CoreManagementError(RuntimeError):
    """A management source is malformed or unavailable."""


class CoreManagementConflict(CoreManagementError):
    """A Core definition or control conflicts with existing evidence."""


class CoreManagementDenied(PermissionError):
    """An owner control operation is not authorized."""


class CoreDisplayState(str, Enum):
    NOT_REGISTERED = "not_registered"
    DEFINED = "defined"
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPED = "stopped"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CoreControlOperation(str, Enum):
    PARTICIPATION = "participation"
    NOTIFICATIONS = "notifications"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class ExpectedCoreIdentity:
    """Owner-facing expected identity; not evidence that a Core exists."""

    core_number: int
    full_name: str
    nickname: str
    slug: str

    def __post_init__(self) -> None:
        if type(self.core_number) is not int or self.core_number < 1:
            raise ValueError("expected core_number must be positive")
        _text(self.full_name, "expected full_name")
        _text(self.nickname, "expected nickname")
        if type(self.slug) is not str or _ID.fullmatch(self.slug) is None:
            raise ValueError("expected slug must be a bounded identifier")


EXPECTED_CORE_IDENTITIES: tuple[ExpectedCoreIdentity, ...] = (
    ExpectedCoreIdentity(1, "Sofía", "Sofía", "sofia"),
    ExpectedCoreIdentity(2, "Mack", "Mack", "mack"),
    ExpectedCoreIdentity(3, "Nova", "Nova", "nova"),
)


@dataclass(frozen=True, slots=True)
class CoreDefinitionView:
    """Inert definition projection; never installation or execution evidence."""

    core_id: UUID
    full_name: str
    core_number: int
    generation: int
    lifecycle: LifecycleState
    nickname: str | None = None
    identity_concept: str = ""
    model: ModelIdentity | None = None
    constitution_sha256: str | None = None
    definition_revision: int | None = None
    voice_available: bool = False
    avatar_available: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID) or self.core_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        _text(self.full_name, "full_name")
        if self.nickname is not None:
            _text(self.nickname, "nickname")
        if type(self.core_number) is not int or self.core_number < 1:
            raise ValueError("core_number must be a positive integer")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        if not isinstance(self.lifecycle, LifecycleState):
            raise TypeError("lifecycle must be LifecycleState")
        if type(self.identity_concept) is not str or len(
            self.identity_concept
        ) > 2000:
            raise ValueError("identity_concept must be bounded text")
        if self.model is not None and not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity or None")
        if self.constitution_sha256 is not None and (
            type(self.constitution_sha256) is not str
            or _SHA256.fullmatch(self.constitution_sha256) is None
        ):
            raise ValueError("constitution_sha256 must be lowercase SHA-256")
        if self.definition_revision is not None and (
            type(self.definition_revision) is not int
            or self.definition_revision < 1
        ):
            raise ValueError("definition_revision must be positive or None")
        if type(self.voice_available) is not bool or type(
            self.avatar_available
        ) is not bool:
            raise TypeError("voice/avatar availability flags must be bool")


@dataclass(frozen=True, slots=True)
class InstallationEvidence:
    core_id: UUID
    installed: bool
    evidence: EvidenceState
    artifact_sha256: str | None = None
    version: str | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID) or self.core_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        if type(self.installed) is not bool:
            raise TypeError("installed must be bool")
        if not isinstance(self.evidence, EvidenceState):
            raise TypeError("evidence must be EvidenceState")
        if self.artifact_sha256 is not None and (
            type(self.artifact_sha256) is not str
            or _SHA256.fullmatch(self.artifact_sha256) is None
        ):
            raise ValueError("artifact_sha256 must be lowercase SHA-256")
        if self.observed_at is not None and (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
        ):
            raise ValueError("observed_at must be timezone-aware or None")


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """Explicit runtime process observation for one Core generation."""

    core_id: UUID
    state: str
    generation: int
    observed_at: datetime
    evidence: EvidenceState

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID) or self.core_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        if type(self.state) is not str or _ID.fullmatch(self.state) is None:
            raise ValueError("runtime state must be a bounded identifier")
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("generation must be nonnegative")
        if not isinstance(self.observed_at, datetime) or (
            self.observed_at.tzinfo is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.evidence, EvidenceState):
            raise TypeError("evidence must be EvidenceState")


@dataclass(frozen=True, slots=True)
class CoreStopReceipt:
    core_id: UUID
    stopped: bool
    state: str
    evidence: EvidenceState
    observed_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CoreControlReceipt:
    operation: CoreControlOperation
    core_id: UUID
    allowed: bool
    reason: str | None = None
    participation_enabled: bool | None = None
    notifications_enabled: bool | None = None
    stop: CoreStopReceipt | None = None


@dataclass(frozen=True, slots=True)
class CoreDisplay:
    core_id: UUID
    full_name: str
    nickname: str | None
    core_number: int
    generation: int
    definition_lifecycle: LifecycleState
    installed: bool | None
    active: bool
    state: CoreDisplayState
    evidence: EvidenceState | None
    runtime_observed_at: datetime | None
    model_label: str | None
    voice_available: bool
    avatar_available: bool
    participation_enabled: bool
    notifications_enabled: bool
    stop_available: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ExpectedIdentityStatus:
    core_number: int
    full_name: str
    slug: str
    present: bool | None
    core_id: UUID | None
    state: CoreDisplayState | None


@dataclass(frozen=True, slots=True)
class ManagementSnapshot:
    platform_id: str
    generated_at: datetime
    operator_stopped: bool
    definitions_available: bool
    core_free: bool | None
    cores: tuple[CoreDisplay, ...]
    expected: tuple[ExpectedIdentityStatus, ...]

    @property
    def active_core_count(self) -> int:
        return sum(1 for core in self.cores if core.active)

    @property
    def installed_core_count(self) -> int:
        return sum(1 for core in self.cores if core.installed is True)


class CoreDefinitionSource(Protocol):
    def definitions(self) -> tuple[CoreDefinitionView, ...]:
        ...


class CoreInstallationEvidenceSource(Protocol):
    def installation(self, core_id: UUID) -> InstallationEvidence | None:
        ...


class CoreRuntimeEvidenceSource(Protocol):
    def observation(self, core_id: UUID) -> RuntimeObservation | None:
        ...


class CoreStopBackend(Protocol):
    def stop(self, *, core_id: UUID, generation: int) -> CoreStopReceipt:
        ...


class OwnerControlAuthorizer(Protocol):
    def authorize(
        self, *, owner_id: str, operation: str, core_id: UUID,
    ) -> bool:
        ...


class ManagementSafety(Protocol):
    def is_operator_stopped(self) -> bool:
        ...


class InMemoryCoreDefinitionSource:
    """Simple registration adapter for disposable fixtures and tests."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._definitions: dict[UUID, CoreDefinitionView] = {}

    def register(self, definition: CoreDefinitionView) -> None:
        if not isinstance(definition, CoreDefinitionView):
            raise TypeError("definition must be CoreDefinitionView")
        with self._lock:
            if definition.core_id in self._definitions:
                raise CoreManagementConflict(
                    "Core definition identity is already registered"
                )
            self._definitions[definition.core_id] = definition

    def replace(self, definition: CoreDefinitionView) -> None:
        if not isinstance(definition, CoreDefinitionView):
            raise TypeError("definition must be CoreDefinitionView")
        with self._lock:
            self._definitions[definition.core_id] = definition

    def remove(self, core_id: UUID) -> bool:
        with self._lock:
            return self._definitions.pop(core_id, None) is not None

    def definitions(self) -> tuple[CoreDefinitionView, ...]:
        with self._lock:
            return tuple(
                self._definitions[key]
                for key in sorted(
                    self._definitions,
                    key=lambda item: str(item),
                )
            )


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


_RUNTIME_STATES = {
    "active": CoreDisplayState.ACTIVE,
    "running": CoreDisplayState.ACTIVE,
    "stopped": CoreDisplayState.STOPPED,
    "starting": CoreDisplayState.STARTING,
    "failed": CoreDisplayState.FAILED,
}


class MultiCoreManagement:
    """Read/registration/display projection with explicit owner controls."""

    def __init__(
        self, *,
        platform_id: str,
        definitions: CoreDefinitionSource,
        installation: CoreInstallationEvidenceSource | None = None,
        runtime: CoreRuntimeEvidenceSource | None = None,
        stop_backend: CoreStopBackend | None = None,
        authorization: OwnerControlAuthorizer | None = None,
        safety: ManagementSafety | None = None,
        clock=None,
        expected: tuple[ExpectedCoreIdentity, ...] = EXPECTED_CORE_IDENTITIES,
        evidence_max_age_seconds: float = 120.0,
    ) -> None:
        self.platform_id = _identifier(platform_id, "platform_id")
        if not callable(getattr(definitions, "definitions", None)):
            raise TypeError("definitions must expose definitions()")
        for label, source, method in (
            ("installation", installation, "installation"),
            ("runtime", runtime, "observation"),
        ):
            if source is not None and not callable(getattr(source, method, None)):
                raise TypeError(f"{label} source must expose {method}()")
        if stop_backend is not None and not callable(
            getattr(stop_backend, "stop", None)
        ):
            raise TypeError("stop backend must expose stop()")
        if authorization is not None and not callable(
            getattr(authorization, "authorize", None)
        ):
            raise TypeError("authorization must expose authorize()")
        if safety is not None and not callable(
            getattr(safety, "is_operator_stopped", None)
        ):
            raise TypeError("safety must expose is_operator_stopped()")
        if type(expected) is not tuple or not expected or any(
            not isinstance(item, ExpectedCoreIdentity) for item in expected
        ):
            raise ValueError("expected identities must be a nonempty tuple")
        if type(evidence_max_age_seconds) not in (int, float) or not (
            float(evidence_max_age_seconds) > 0
        ):
            raise ValueError("evidence_max_age_seconds must be positive")
        self._definitions = definitions
        self._installation = installation
        self._runtime = runtime
        self._stop_backend = stop_backend
        self._authorization = authorization
        self._safety = safety
        self._clock = clock if callable(clock) else (
            lambda: datetime.now(timezone.utc)
        )
        self._expected = expected
        self._max_age = float(evidence_max_age_seconds)
        self._participation: dict[UUID, bool] = {}
        self._notifications: dict[UUID, bool] = {}
        self._lock = RLock()

    def _now(self) -> datetime:
        moment = self._clock()
        return _aware(moment, "management clock")

    def _operator_stopped(self) -> bool:
        if self._safety is None:
            return False
        try:
            return self._safety.is_operator_stopped() is True
        except Exception:
            return True

    def _fresh(self, observed_at: datetime, now: datetime) -> bool:
        delta = (now - observed_at).total_seconds()
        return -5.0 <= delta <= self._max_age

    def _definition_rows(
        self,
    ) -> tuple[tuple[CoreDefinitionView, ...], bool]:
        try:
            provided = self._definitions.definitions()
        except Exception:
            return (), False
        if not isinstance(provided, (tuple, list)):
            raise CoreManagementError(
                "definition source returned a non-sequence projection"
            )
        views: list[CoreDefinitionView] = []
        seen: set[UUID] = set()
        for definition in provided:
            if not isinstance(definition, CoreDefinitionView):
                raise CoreManagementError(
                    "definition source returned an invalid Core definition"
                )
            if definition.core_id in seen:
                raise CoreManagementError(
                    "definition source returned duplicate Core identities"
                )
            seen.add(definition.core_id)
            views.append(definition)
        return tuple(sorted(views, key=lambda item: (
            item.core_number, str(item.core_id),
        ))), True

    def _install_row(
        self, core_id: UUID,
    ) -> tuple[InstallationEvidence | None, str | None]:
        if self._installation is None:
            return None, "installation evidence source unavailable"
        try:
            return self._installation.installation(core_id), None
        except Exception:
            return None, "installation evidence unavailable"

    def _runtime_row(
        self, core_id: UUID,
    ) -> tuple[RuntimeObservation | None, str | None]:
        if self._runtime is None:
            return None, "runtime evidence source unavailable"
        try:
            return self._runtime.observation(core_id), None
        except Exception:
            return None, "runtime evidence unavailable"

    def _display(
        self, definition: CoreDefinitionView, now: datetime,
    ) -> CoreDisplay:
        install, install_error = self._install_row(definition.core_id)
        runtime, runtime_error = self._runtime_row(definition.core_id)
        installed: bool | None = None
        state = CoreDisplayState.DEFINED
        active = False
        evidence: EvidenceState | None = None
        observed_at: datetime | None = None
        detail = install_error or ""
        if install is not None and install.core_id == definition.core_id:
            if install.evidence is not EvidenceState.VERIFIED:
                installed = None
                state = CoreDisplayState.UNKNOWN
                detail = "installation evidence is not verified"
            elif install.installed:
                installed = True
                state = CoreDisplayState.INSTALLED
            else:
                installed = False
                state = CoreDisplayState.NOT_INSTALLED
            evidence = install.evidence
        if runtime is not None and runtime.core_id == definition.core_id:
            observed_at = runtime.observed_at.astimezone(timezone.utc)
            evidence = runtime.evidence
            if runtime.evidence is not EvidenceState.VERIFIED:
                state = CoreDisplayState.UNKNOWN
                detail = "runtime evidence is not verified"
            elif runtime.generation != definition.generation:
                state = CoreDisplayState.UNKNOWN
                detail = "runtime generation does not match the definition"
            elif not self._fresh(observed_at, now):
                state = CoreDisplayState.UNKNOWN
                detail = "runtime evidence is stale"
            else:
                state = _RUNTIME_STATES.get(
                    runtime.state.casefold(), CoreDisplayState.UNKNOWN,
                )
                active = state is CoreDisplayState.ACTIVE
        elif runtime_error:
            detail = runtime_error
        participation = self._participation.get(definition.core_id, True)
        notifications = self._notifications.get(definition.core_id, True)
        stop_available = (
            self._stop_backend is not None
            and not self._operator_stopped()
        )
        return CoreDisplay(
            core_id=definition.core_id,
            full_name=definition.full_name,
            nickname=definition.nickname,
            core_number=definition.core_number,
            generation=definition.generation,
            definition_lifecycle=definition.lifecycle,
            installed=installed,
            active=active,
            state=state,
            evidence=evidence,
            runtime_observed_at=observed_at,
            model_label=(
                None if definition.model is None else definition.model.label
            ),
            voice_available=definition.voice_available,
            avatar_available=definition.avatar_available,
            participation_enabled=participation,
            notifications_enabled=notifications,
            stop_available=stop_available,
            detail=detail,
        )

    def _expected_status(
        self, definitions: tuple[CoreDefinitionView, ...],
        available: bool, rows: tuple[CoreDisplay, ...],
    ) -> tuple[ExpectedIdentityStatus, ...]:
        by_id = {row.core_id: row for row in rows}
        statuses: list[ExpectedIdentityStatus] = []
        for item in self._expected:
            match = next(
                (
                    definition for definition in definitions
                    if definition.core_number == item.core_number
                    or definition.full_name.casefold() == item.full_name.casefold()
                    or (
                        definition.nickname is not None
                        and definition.nickname.casefold()
                        == item.nickname.casefold()
                    )
                ),
                None,
            )
            if match is None:
                statuses.append(ExpectedIdentityStatus(
                    item.core_number, item.full_name, item.slug,
                    None if not available else False, None, None,
                ))
                continue
            row = by_id[match.core_id]
            statuses.append(ExpectedIdentityStatus(
                item.core_number, item.full_name, item.slug,
                True, match.core_id, row.state,
            ))
        return tuple(statuses)

    def snapshot(self) -> ManagementSnapshot:
        now = self._now()
        definitions, available = self._definition_rows()
        rows = tuple(self._display(definition, now) for definition in definitions)
        core_free = None if not available else len(rows) == 0
        return ManagementSnapshot(
            platform_id=self.platform_id,
            generated_at=now,
            operator_stopped=self._operator_stopped(),
            definitions_available=available,
            core_free=core_free,
            cores=rows,
            expected=self._expected_status(definitions, available, rows),
        )

    def _require_definition(self, core_id: UUID) -> CoreDefinitionView:
        definitions, available = self._definition_rows()
        if not available:
            raise CoreManagementError(
                "Core definitions are unavailable; refusing control"
            )
        for definition in definitions:
            if definition.core_id == core_id:
                return definition
        raise CoreManagementConflict("Core definition is not registered")

    def _authorized(
        self, *, owner_id: str, operation: CoreControlOperation, core_id: UUID,
    ) -> tuple[bool, str | None]:
        _identifier(owner_id, "owner_id")
        if self._operator_stopped():
            return False, "operator STOP is active"
        if self._authorization is None:
            return False, "no owner control authorization is configured"
        try:
            allowed = self._authorization.authorize(
                owner_id=owner_id,
                operation=operation.value,
                core_id=core_id,
            )
        except Exception:
            return False, "owner control authorization failed closed"
        if allowed is not True:
            return False, "owner control authorization denied"
        return True, None

    def set_participation(
        self, core_id: UUID, *, owner_id: str, enabled: bool,
    ) -> CoreControlReceipt:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self._require_definition(core_id)
        allowed, reason = self._authorized(
            owner_id=owner_id,
            operation=CoreControlOperation.PARTICIPATION,
            core_id=core_id,
        )
        if not allowed:
            return CoreControlReceipt(
                CoreControlOperation.PARTICIPATION, core_id, False, reason,
                participation_enabled=self._participation.get(core_id, True),
            )
        with self._lock:
            self._participation[core_id] = enabled
        return CoreControlReceipt(
            CoreControlOperation.PARTICIPATION, core_id, True, None,
            participation_enabled=enabled,
        )

    def set_notifications(
        self, core_id: UUID, *, owner_id: str, enabled: bool,
    ) -> CoreControlReceipt:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self._require_definition(core_id)
        allowed, reason = self._authorized(
            owner_id=owner_id,
            operation=CoreControlOperation.NOTIFICATIONS,
            core_id=core_id,
        )
        if not allowed:
            return CoreControlReceipt(
                CoreControlOperation.NOTIFICATIONS, core_id, False, reason,
                notifications_enabled=self._notifications.get(core_id, True),
            )
        with self._lock:
            self._notifications[core_id] = enabled
        return CoreControlReceipt(
            CoreControlOperation.NOTIFICATIONS, core_id, True, None,
            notifications_enabled=enabled,
        )

    def request_stop(
        self, core_id: UUID, *, owner_id: str,
        expected_generation: int | None = None,
    ) -> CoreControlReceipt:
        definition = self._require_definition(core_id)
        allowed, reason = self._authorized(
            owner_id=owner_id,
            operation=CoreControlOperation.STOP,
            core_id=core_id,
        )
        if not allowed:
            return CoreControlReceipt(
                CoreControlOperation.STOP, core_id, False, reason,
            )
        if self._stop_backend is None:
            return CoreControlReceipt(
                CoreControlOperation.STOP, core_id, False,
                "Core stop backend is unavailable",
            )
        generation = (
            definition.generation
            if expected_generation is None else expected_generation
        )
        try:
            receipt = self._stop_backend.stop(
                core_id=core_id, generation=generation,
            )
        except Exception:
            return CoreControlReceipt(
                CoreControlOperation.STOP, core_id, False,
                "Core stop backend failed closed",
            )
        if not isinstance(receipt, CoreStopReceipt):
            return CoreControlReceipt(
                CoreControlOperation.STOP, core_id, False,
                "Core stop backend returned an invalid receipt",
            )
        return CoreControlReceipt(
            CoreControlOperation.STOP,
            core_id,
            receipt.stopped,
            None if receipt.stopped else (
                receipt.reason or "Core stop was not confirmed"
            ),
            stop=receipt,
        )
