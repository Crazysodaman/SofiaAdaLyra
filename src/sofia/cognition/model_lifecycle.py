"""Deterministic lifecycle management for configured cognitive model roles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Event, RLock, Thread
from typing import Any, Mapping, Protocol

from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import ModelLifecycleConfiguration, ProviderConfiguration


class CognitiveModelRole(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ModelResidency(str, Enum):
    UNAVAILABLE = "unavailable"
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"


class ModelLifecycleError(RuntimeError):
    """The configured model lifecycle could not complete safely."""


class ModelUnavailableError(ModelLifecycleError):
    """The requested configured model is not installed on this backend."""


class ModelLifecycleBackend(Protocol):
    def models(self) -> Any: ...
    def running(self) -> Any: ...
    def pull(self, name: str) -> Any: ...
    def load(self, name: str, *, keep_alive: str) -> Any: ...
    def unload(self, name: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class ModelLifecycleStatus:
    role: CognitiveModelRole
    provider: str
    model: str
    state: ModelResidency
    last_error: str | None = None


def _model_names(payload: Any) -> frozenset[str]:
    if payload is None:
        return frozenset()
    if isinstance(payload, Mapping):
        items = payload.get("models", ())
    else:
        items = getattr(payload, "models", ())
    if items is None:
        items = ()
    names: set[str] = set()
    for item in items:
        if isinstance(item, Mapping):
            value = item.get("name") or item.get("model")
        else:
            value = getattr(item, "name", None) or getattr(item, "model", None)
        if isinstance(value, str) and value.strip():
            names.add(value.strip())
    return frozenset(names)


class ModelLifecycleManager:
    """Manage residency by role without embedding concrete model identities."""

    def __init__(
        self,
        *,
        selection: CognitiveModelSelection,
        policy: ModelLifecycleConfiguration,
        backend: ModelLifecycleBackend,
        managed_provider: str = "ollama",
    ) -> None:
        if not isinstance(selection, CognitiveModelSelection):
            raise TypeError("selection must be CognitiveModelSelection")
        if not isinstance(policy, ModelLifecycleConfiguration):
            raise TypeError("policy must be ModelLifecycleConfiguration")
        if not isinstance(managed_provider, str) or not managed_provider.strip():
            raise ValueError("managed_provider required")
        self.selection = selection
        self.policy = policy
        self.backend = backend
        self.managed_provider = managed_provider.strip()
        self._lock = RLock()
        self._transient: dict[str, ModelResidency] = {}
        self._last_error: dict[str, str] = {}
        self._last_used: dict[str, datetime] = {}
        self._observed_ready_at: dict[str, datetime] = {}
        self._busy: dict[str, int] = {}

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        moment = value or datetime.now(timezone.utc)
        if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("model lifecycle time must be timezone-aware")
        return moment.astimezone(timezone.utc)

    def update_selection(self, selection: CognitiveModelSelection) -> None:
        if not isinstance(selection, CognitiveModelSelection):
            raise TypeError("selection must be CognitiveModelSelection")
        with self._lock:
            self.selection = selection

    def provider_for(self, role: CognitiveModelRole) -> ProviderConfiguration:
        if not isinstance(role, CognitiveModelRole):
            raise TypeError("role must be CognitiveModelRole")
        if role is CognitiveModelRole.PRIMARY:
            return self.selection.primary
        if self.selection.secondary is None:
            raise ValueError("secondary cognitive model is not configured")
        return self.selection.secondary

    @property
    def configured_roles(self) -> tuple[CognitiveModelRole, ...]:
        return (
            (CognitiveModelRole.PRIMARY, CognitiveModelRole.SECONDARY)
            if self.selection.secondary is not None
            else (CognitiveModelRole.PRIMARY,)
        )

    @property
    def background_role(self) -> CognitiveModelRole:
        return (
            CognitiveModelRole.SECONDARY
            if self.selection.secondary is not None
            else CognitiveModelRole.PRIMARY
        )

    def _managed_providers(self) -> tuple[tuple[CognitiveModelRole, ProviderConfiguration], ...]:
        values: list[tuple[CognitiveModelRole, ProviderConfiguration]] = [
            (CognitiveModelRole.PRIMARY, self.selection.primary)
        ]
        if self.selection.secondary is not None:
            values.append((CognitiveModelRole.SECONDARY, self.selection.secondary))
        return tuple(
            (role, provider)
            for role, provider in values
            if provider.provider == self.managed_provider
        )

    def _inventory(self) -> tuple[frozenset[str], frozenset[str]]:
        try:
            return _model_names(self.backend.models()), _model_names(self.backend.running())
        except Exception as exc:
            raise ModelLifecycleError(
                f"{self.managed_provider} model inventory failed"
            ) from exc

    def statuses(self, *, now: datetime | None = None) -> tuple[ModelLifecycleStatus, ...]:
        moment = self._now(now)
        with self._lock:
            try:
                installed, running = self._inventory()
            except ModelLifecycleError as exc:
                error = type(exc.__cause__ or exc).__name__
                return tuple(
                    ModelLifecycleStatus(
                        role=role,
                        provider=provider.provider,
                        model=provider.model,
                        state=ModelResidency.ERROR,
                        last_error=error,
                    )
                    for role, provider in self._managed_providers()
                )

            result: list[ModelLifecycleStatus] = []
            for role, provider in self._managed_providers():
                model = provider.model
                transient = self._transient.get(model)
                if transient is not None:
                    state = transient
                elif self._busy.get(model, 0) > 0:
                    state = ModelResidency.BUSY
                    self._observed_ready_at.setdefault(model, moment)
                elif model in running:
                    state = ModelResidency.READY
                    self._observed_ready_at.setdefault(model, moment)
                elif model in installed:
                    state = ModelResidency.UNLOADED
                    self._observed_ready_at.pop(model, None)
                else:
                    state = ModelResidency.UNAVAILABLE
                    self._observed_ready_at.pop(model, None)
                result.append(
                    ModelLifecycleStatus(
                        role=role,
                        provider=provider.provider,
                        model=model,
                        state=state,
                        last_error=self._last_error.get(model),
                    )
                )
            return tuple(result)

    def status(
        self,
        role: CognitiveModelRole,
        *,
        now: datetime | None = None,
    ) -> ModelLifecycleStatus:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            return ModelLifecycleStatus(
                role=role,
                provider=provider.provider,
                model=provider.model,
                state=ModelResidency.UNAVAILABLE,
                last_error="provider_not_managed_here",
            )
        return next(item for item in self.statuses(now=now) if item.role is role)

    def note_used(
        self,
        role: CognitiveModelRole,
        *,
        now: datetime | None = None,
    ) -> None:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            return
        moment = self._now(now)
        with self._lock:
            self._last_used[provider.model] = moment
            self._observed_ready_at.setdefault(provider.model, moment)

    def begin_use(
        self,
        role: CognitiveModelRole,
        *,
        now: datetime | None = None,
    ) -> None:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            return
        moment = self._now(now)
        with self._lock:
            model = provider.model
            self._busy[model] = self._busy.get(model, 0) + 1
            self._last_used[model] = moment
            self._observed_ready_at.setdefault(model, moment)

    def end_use(
        self,
        role: CognitiveModelRole,
        *,
        now: datetime | None = None,
    ) -> None:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            return
        moment = self._now(now)
        with self._lock:
            model = provider.model
            count = self._busy.get(model, 0)
            if count <= 1:
                self._busy.pop(model, None)
            else:
                self._busy[model] = count - 1
            self._last_used[model] = moment

    def install(
        self,
        role: CognitiveModelRole,
    ) -> ModelLifecycleStatus:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            raise ModelLifecycleError(
                f"provider {provider.provider!r} is not managed by this lifecycle backend"
            )
        model = provider.model
        with self._lock:
            installed, running = self._inventory()
            if model in installed:
                return ModelLifecycleStatus(
                    role=role,
                    provider=provider.provider,
                    model=model,
                    state=(
                        ModelResidency.READY
                        if model in running
                        else ModelResidency.UNLOADED
                    ),
                )
            self._transient[model] = ModelResidency.LOADING
            try:
                self.backend.pull(model)
            except Exception as exc:
                self._last_error[model] = type(exc).__name__
                self._transient.pop(model, None)
                raise ModelLifecycleError(
                    f"failed to install configured {role.value} model"
                ) from exc
            self._transient.pop(model, None)
            self._last_error.pop(model, None)
            return ModelLifecycleStatus(
                role=role,
                provider=provider.provider,
                model=model,
                state=ModelResidency.UNLOADED,
            )

    def install_missing(self) -> tuple[str, ...]:
        if not self.policy.auto_install_missing:
            return ()
        installed_names: list[str] = []
        for role in self.configured_roles:
            status = self.status(role)
            if status.state is not ModelResidency.UNAVAILABLE:
                continue
            installed_names.append(self.install(role).model)
        return tuple(installed_names)

    def ensure_loaded(
        self,
        role: CognitiveModelRole,
        *,
        now: datetime | None = None,
    ) -> ModelLifecycleStatus:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            raise ModelLifecycleError(
                f"provider {provider.provider!r} is not managed by this lifecycle backend"
            )
        moment = self._now(now)
        with self._lock:
            installed, running = self._inventory()
            model = provider.model
            if model not in installed:
                raise ModelUnavailableError(
                    f"configured {role.value} model is not installed"
                )
            if model not in running:
                self._transient[model] = ModelResidency.LOADING
                try:
                    self.backend.load(model, keep_alive=self.policy.keep_alive)
                except Exception as exc:
                    self._last_error[model] = type(exc).__name__
                    self._transient.pop(model, None)
                    raise ModelLifecycleError(
                        f"failed to load configured {role.value} model"
                    ) from exc
                self._transient.pop(model, None)
            self._last_error.pop(model, None)
            self._last_used[model] = moment
            self._observed_ready_at.setdefault(model, moment)
            return ModelLifecycleStatus(
                role=role,
                provider=provider.provider,
                model=model,
                state=ModelResidency.READY,
            )

    def unload(
        self,
        role: CognitiveModelRole,
    ) -> ModelLifecycleStatus:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            raise ModelLifecycleError(
                f"provider {provider.provider!r} is not managed by this lifecycle backend"
            )
        model = provider.model
        with self._lock:
            if self._busy.get(model, 0) > 0:
                raise ModelLifecycleError(
                    f"configured {role.value} model is currently busy"
                )
            try:
                self.backend.unload(model)
            except Exception as exc:
                self._last_error[model] = type(exc).__name__
                raise ModelLifecycleError(
                    f"failed to unload configured {role.value} model"
                ) from exc
            self._last_used.pop(model, None)
            self._observed_ready_at.pop(model, None)
            self._transient.pop(model, None)
            self._last_error.pop(model, None)
            return ModelLifecycleStatus(
                role=role,
                provider=provider.provider,
                model=model,
                state=ModelResidency.UNLOADED,
            )

    def unload_all(self) -> tuple[str, ...]:
        unloaded: list[str] = []
        seen: set[str] = set()
        for role, provider in self._managed_providers():
            if provider.model in seen:
                continue
            seen.add(provider.model)
            self.unload(role)
            unloaded.append(provider.model)
        return tuple(unloaded)

    def sweep_idle(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        if not self.policy.enabled:
            return ()
        moment = self._now(now)
        with self._lock:
            _, running = self._inventory()
            unloaded: list[str] = []
            seen: set[str] = set()
            for _, provider in self._managed_providers():
                model = provider.model
                if model in seen:
                    continue
                seen.add(model)
                if model not in running or self._busy.get(model, 0) > 0:
                    continue
                observed = self._observed_ready_at.setdefault(model, moment)
                last = self._last_used.get(model, observed)
                if (moment - last).total_seconds() < self.policy.idle_unload_seconds:
                    continue
                try:
                    self.backend.unload(model)
                except Exception as exc:
                    self._last_error[model] = type(exc).__name__
                    continue
                self._last_used.pop(model, None)
                self._observed_ready_at.pop(model, None)
                self._last_error.pop(model, None)
                unloaded.append(model)
            return tuple(unloaded)


class LifecycleManagedCognitiveEngine(CognitiveEngine):
    """Wake one configured model role immediately before delegated cognition."""

    def __init__(
        self,
        *,
        delegate: CognitiveEngine,
        lifecycle: ModelLifecycleManager,
        role: CognitiveModelRole,
    ) -> None:
        if not isinstance(delegate, CognitiveEngine):
            raise TypeError("delegate must be CognitiveEngine")
        if not isinstance(lifecycle, ModelLifecycleManager):
            raise TypeError("lifecycle must be ModelLifecycleManager")
        if not isinstance(role, CognitiveModelRole):
            raise TypeError("role must be CognitiveModelRole")
        self.delegate = delegate
        self.lifecycle = lifecycle
        self.role = role

    @property
    def provider(self):
        return getattr(self.delegate, "provider", None)

    @property
    def configuration(self):
        return getattr(self.delegate, "configuration", None)

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        try:
            self.lifecycle.ensure_loaded(self.role)
            self.lifecycle.begin_use(self.role)
        except ModelLifecycleError as exc:
            raise CognitiveEngineError(
                f"configured {self.role.value} model could not be made ready"
            ) from exc
        try:
            return self.delegate.respond(request)
        finally:
            self.lifecycle.end_use(self.role)


class ModelLifecycleWorker:
    """Tiny non-LLM worker that reclaims idle model residency."""

    def __init__(
        self,
        *,
        manager: ModelLifecycleManager,
        interval_seconds: float = 60.0,
    ) -> None:
        if not isinstance(manager, ModelLifecycleManager):
            raise TypeError("manager must be ModelLifecycleManager")
        if (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, (int, float))
            or not 1 <= interval_seconds <= 3600
        ):
            raise ValueError("interval_seconds must be in 1..3600")
        self.manager = manager
        self.interval_seconds = float(interval_seconds)
        self._stop = Event()
        self._thread: Thread | None = None
        self.last_error: str | None = None

    def run_once(self, *, now: datetime | None = None) -> tuple[str, ...]:
        return self.manager.sweep_idle(now=now)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.run_once()
                self.last_error = None
            except Exception as exc:
                self.last_error = type(exc).__name__

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("model lifecycle worker already started")
        self._stop.clear()
        thread = Thread(
            target=self._loop,
            name="sofia-model-lifecycle",
            daemon=True,
        )
        thread.start()
        self._thread = thread

    def stop(self, *, timeout_seconds: float = 30.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is None:
            return
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            raise RuntimeError("model lifecycle worker did not stop safely")
        self._thread = None
