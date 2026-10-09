"""Deterministic lifecycle management for configured cognitive model roles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import Event, RLock, Thread
from typing import Any, Callable, Mapping, Protocol

from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.cognition.runtime_state import CognitionRuntimeStateStore
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


class ModelResidencyMode(str, Enum):
    ON_DEMAND = "on_demand"
    FAST_ALWAYS_RESIDENT = "fast_always_resident"
    DUAL_RESIDENT = "dual_resident"
    RESOURCE_AWARE = "resource_aware"


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


@dataclass(frozen=True, slots=True)
class ModelResourceObservation:
    """Only resource facts actually observed by the host."""

    cpu_percent: float | None = None
    ram_available_bytes: int | None = None
    gpu_percent: float | None = None
    vram_available_bytes: int | None = None
    throttled: bool | None = None
    gaming: bool | None = None


@dataclass(frozen=True, slots=True)
class ModelResidencyDecision:
    mode: ModelResidencyMode
    desired_roles: tuple[CognitiveModelRole, ...]
    reasons: tuple[str, ...]
    loaded_models: tuple[str, ...] = ()
    unloaded_models: tuple[str, ...] = ()


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


def _model_sizes(payload: Any) -> dict[str, int]:
    if isinstance(payload, Mapping):
        items = payload.get("models", ())
    else:
        items = getattr(payload, "models", ())
    result: dict[str, int] = {}
    for item in items or ():
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("model")
            size = item.get("size")
        else:
            name = getattr(item, "name", None) or getattr(item, "model", None)
            size = getattr(item, "size", None)
        if (
            isinstance(name, str)
            and name.strip()
            and type(size) is int
            and size > 0
        ):
            result[name.strip()] = size
    return result


class ModelLifecycleManager:
    """Manage residency by role without embedding concrete model identities."""

    def __init__(
        self,
        *,
        selection: CognitiveModelSelection,
        policy: ModelLifecycleConfiguration,
        backend: ModelLifecycleBackend,
        managed_provider: str = "ollama",
        resource_observer: Callable[[], Any] | None = None,
        gaming_observer: Callable[[], bool | None] | None = None,
        runtime_state_store: CognitionRuntimeStateStore | None = None,
        local_host_id: str | None = None,
        policy_observer: Callable[[], ModelLifecycleConfiguration] | None = None,
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
        self.resource_observer = resource_observer
        self.gaming_observer = gaming_observer
        self.runtime_state_store = runtime_state_store
        self.local_host_id = local_host_id
        self.policy_observer = policy_observer
        self._lock = RLock()
        self._transient: dict[str, ModelResidency] = {}
        self._last_error: dict[str, str] = {}
        self._last_used: dict[str, datetime] = {}
        self._observed_ready_at: dict[str, datetime] = {}
        self._busy: dict[str, int] = {}
        self.last_decision: ModelResidencyDecision | None = None

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        moment = value or datetime.now(timezone.utc)
        if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("model lifecycle time must be timezone-aware")
        return moment.astimezone(timezone.utc)


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

    def _resource_observation(self) -> ModelResourceObservation:
        observed = self.resource_observer() if self.resource_observer else None
        total = getattr(observed, "ram_total_bytes", None)
        used = getattr(observed, "ram_used_bytes", None)
        available = (
            max(0, total - used)
            if type(total) is int and type(used) is int
            else None
        )
        vram_total = getattr(observed, "vram_total_bytes", None)
        vram_used = getattr(observed, "vram_used_bytes", None)
        vram_available = (
            max(0, vram_total - vram_used)
            if type(vram_total) is int and type(vram_used) is int
            else None
        )
        gaming = self.gaming_observer() if self.gaming_observer else None
        return ModelResourceObservation(
            cpu_percent=getattr(observed, "cpu_percent", None),
            ram_available_bytes=available,
            gpu_percent=getattr(observed, "gpu_percent", None),
            vram_available_bytes=vram_available,
            throttled=getattr(observed, "throttled", None),
            gaming=gaming,
        )

    def statuses(self, *, now: datetime | None = None) -> tuple[ModelLifecycleStatus, ...]:
        moment = self._now(now)
        with self._lock:
            try:
                installed, running = self._inventory()
            except ModelLifecycleError as exc:
                error = type(exc.__cause__ or exc).__name__
                result = tuple(
                    ModelLifecycleStatus(
                        role=role,
                        provider=provider.provider,
                        model=provider.model,
                        state=ModelResidency.ERROR,
                        last_error=error,
                    )
                    for role, provider in self._managed_providers()
                )
                self._publish_statuses(result, at=moment)
                return result

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
            statuses = tuple(result)
            self._publish_statuses(statuses, at=moment)
            return statuses

    def _publish_statuses(
        self,
        statuses: tuple[ModelLifecycleStatus, ...],
        *,
        at: datetime,
    ) -> None:
        if self.runtime_state_store is None:
            return
        for status in statuses:
            self.runtime_state_store.publish_lifecycle(
                role=status.role.value,
                model=status.model,
                host=(
                    self.local_host_id
                    if status.state in {ModelResidency.READY, ModelResidency.BUSY}
                    else None
                ),
                residency=status.state.value,
                installed=(
                    None if status.state is ModelResidency.ERROR
                    else status.state is not ModelResidency.UNAVAILABLE
                ),
                error=status.last_error,
                at=at,
            )

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
                confirmed, _ = self._inventory()
                if model not in confirmed:
                    raise ModelLifecycleError(
                        f"configured {role.value} model install was not confirmed"
                    )
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

    def ensure_available(
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
            self._last_error.pop(model, None)
            self._last_used[model] = moment
            if model in running:
                self._observed_ready_at.setdefault(model, moment)
                state = ModelResidency.READY
            else:
                state = ModelResidency.UNLOADED
            return ModelLifecycleStatus(
                role=role,
                provider=provider.provider,
                model=model,
                state=state,
            )

    def load(self, role: CognitiveModelRole) -> ModelLifecycleStatus:
        provider = self.provider_for(role)
        if provider.provider != self.managed_provider:
            raise ModelLifecycleError(
                f"provider {provider.provider!r} is not managed by this lifecycle backend"
            )
        model = provider.model
        with self._lock:
            installed, running = self._inventory()
            if model not in installed:
                raise ModelUnavailableError(
                    f"configured {role.value} model is not installed"
                )
            if model not in running:
                self._transient[model] = ModelResidency.LOADING
                try:
                    self.backend.load(model, keep_alive=self.policy.keep_alive)
                    _, confirmed = self._inventory()
                    if model not in confirmed:
                        raise ModelLifecycleError(
                            f"configured {role.value} model load was not confirmed"
                        )
                except Exception as exc:
                    self._last_error[model] = type(exc).__name__
                    raise ModelLifecycleError(
                        f"failed to load configured {role.value} model"
                    ) from exc
                finally:
                    self._transient.pop(model, None)
            moment = self._now(None)
            self._observed_ready_at[model] = moment
            self._last_error.pop(model, None)
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
                _, confirmed = self._inventory()
                if model in confirmed:
                    raise ModelLifecycleError(
                        f"configured {role.value} model unload was not confirmed"
                    )
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

    def _residency_plan(
        self,
        *,
        model_sizes: Mapping[str, int],
        observation: ModelResourceObservation,
    ) -> ModelResidencyDecision:
        mode = ModelResidencyMode(self.policy.residency_mode)
        roles = self.configured_roles
        fast = (
            CognitiveModelRole.SECONDARY
            if CognitiveModelRole.SECONDARY in roles
            else CognitiveModelRole.PRIMARY
        )
        if mode is ModelResidencyMode.ON_DEMAND:
            return ModelResidencyDecision(mode, (), ("models wake on demand",))
        if mode is ModelResidencyMode.FAST_ALWAYS_RESIDENT:
            return ModelResidencyDecision(mode, (fast,), ("fast role kept resident",))
        if mode is ModelResidencyMode.DUAL_RESIDENT:
            return ModelResidencyDecision(mode, roles, ("operator selected dual residency",))

        if observation.gaming is True:
            return ModelResidencyDecision(
                mode, (fast,), ("gaming activity observed; primary stays on demand",)
            )
        if observation.throttled is True:
            return ModelResidencyDecision(
                mode, (fast,), ("host throttling observed; primary stays on demand",)
            )
        if observation.cpu_percent is not None and observation.cpu_percent >= 90:
            return ModelResidencyDecision(
                mode, (fast,), ("CPU pressure is at least 90%; primary stays on demand",)
            )
        if observation.gpu_percent is not None and observation.gpu_percent >= 95:
            return ModelResidencyDecision(
                mode, (fast,), ("GPU pressure is at least 95%; primary stays on demand",)
            )
        if observation.vram_available_bytes == 0:
            return ModelResidencyDecision(
                mode, (fast,), ("observed available VRAM is zero; primary stays on demand",)
            )
        if len(roles) < 2:
            return ModelResidencyDecision(mode, roles, ("only one role is configured",))
        names = tuple(self.provider_for(role).model for role in roles)
        if observation.ram_available_bytes is None:
            return ModelResidencyDecision(
                mode, (fast,), ("available RAM is unobserved; dual capacity is unknown",)
            )
        if any(name not in model_sizes for name in names):
            return ModelResidencyDecision(
                mode, (fast,), ("installed model size is unobserved; dual capacity is unknown",)
            )
        required = sum(model_sizes[name] for name in names)
        if required > observation.ram_available_bytes:
            return ModelResidencyDecision(
                mode,
                (fast,),
                (f"observed available RAM {observation.ram_available_bytes} is below model bytes {required}",),
            )
        return ModelResidencyDecision(
            mode,
            roles,
            (f"observed available RAM {observation.ram_available_bytes} covers model bytes {required}",),
        )

    def reconcile_residency(
        self,
        *,
        now: datetime | None = None,
    ) -> ModelResidencyDecision:
        if self.policy_observer is not None:
            observed_policy = self.policy_observer()
            if not isinstance(observed_policy, ModelLifecycleConfiguration):
                raise TypeError("policy observer returned invalid lifecycle policy")
            self.policy = observed_policy
        if not self.policy.enabled:
            decision = ModelResidencyDecision(
                ModelResidencyMode(self.policy.residency_mode),
                (),
                ("automatic lifecycle management is disabled",),
            )
            self.last_decision = decision
            if self.runtime_state_store is not None:
                self.runtime_state_store.publish_decision(
                    residency_mode=decision.mode.value,
                    constraints=decision.reasons,
                    at=now,
                )
            return decision
        with self._lock:
            inventory = self.backend.models()
            installed = _model_names(inventory)
            sizes = _model_sizes(inventory)
            observation = self._resource_observation()
            plan = self._residency_plan(
                model_sizes=sizes,
                observation=observation,
            )
            desired = set(plan.desired_roles)
            loaded: list[str] = []
            reasons = list(plan.reasons)
            for role in plan.desired_roles:
                model = self.provider_for(role).model
                if model not in installed:
                    reasons.append(f"{role.value} model is not installed")
                    continue
                try:
                    if self.status(role, now=now).state is ModelResidency.UNLOADED:
                        loaded.append(self.load(role).model)
                except ModelLifecycleError as exc:
                    reasons.append(f"{role.value} load failed: {type(exc).__name__}")

            unloaded: list[str] = []
            # Pressure decisions reclaim an idle nonpreferred role immediately;
            # ordinary on-demand/unknown-capacity decisions retain the idle timer.
            pressure = any(
                marker in " ".join(reasons)
                for marker in (
                    "gaming",
                    "throttling",
                    "CPU pressure",
                    "GPU pressure",
                    "available VRAM is zero",
                    "below model bytes",
                )
            )
            if pressure:
                for role in self.configured_roles:
                    if role in desired:
                        continue
                    model = self.provider_for(role).model
                    if self._busy.get(model, 0) > 0:
                        reasons.append(f"{role.value} is active and was not unloaded")
                        continue
                    if model in _model_names(self.backend.running()):
                        try:
                            unloaded.append(self.unload(role).model)
                        except ModelLifecycleError as exc:
                            reasons.append(f"{role.value} unload failed: {type(exc).__name__}")
            else:
                idle_unloaded = self.sweep_idle(now=now, protected_roles=desired)
                unloaded.extend(idle_unloaded)
            decision = ModelResidencyDecision(
                plan.mode,
                plan.desired_roles,
                tuple(reasons),
                tuple(loaded),
                tuple(unloaded),
            )
            self.last_decision = decision
            if self.runtime_state_store is not None:
                self.runtime_state_store.publish_decision(
                    residency_mode=decision.mode.value,
                    constraints=decision.reasons,
                    at=now,
                )
                self.statuses(now=now)
            return decision


    def sweep_idle(
        self,
        *,
        now: datetime | None = None,
        protected_roles: set[CognitiveModelRole] | None = None,
    ) -> tuple[str, ...]:
        if not self.policy.enabled:
            return ()
        moment = self._now(now)
        with self._lock:
            _, running = self._inventory()
            unloaded: list[str] = []
            seen: set[str] = set()
            protected = protected_roles or set()
            for role, provider in self._managed_providers():
                if role in protected:
                    continue
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
                    _, confirmed = self._inventory()
                    if model in confirmed:
                        raise ModelLifecycleError(
                            f"configured {role.value} model unload was not confirmed"
                        )
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
            # Ollama chat is itself the wake/load operation. Pre-loading through
            # /api/generate adds a second heavyweight request and can time out
            # before the real cognitive request starts.
            self.lifecycle.ensure_available(self.role)
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
        decision = self.manager.reconcile_residency(now=now)
        return decision.loaded_models + decision.unloaded_models

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
