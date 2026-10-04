from datetime import datetime, timedelta, timezone

import pytest

from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.model_lifecycle import (
    CognitiveModelRole,
    LifecycleManagedCognitiveEngine,
    ModelLifecycleManager,
    ModelResidency,
    ModelUnavailableError,
)
from sofia.cognition.routing import (
    CognitiveEngineRegistry,
    CognitiveRoute,
    RoutingCognitiveEngine,
)
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import (
    ModelLifecycleConfiguration,
    ProviderConfiguration,
)


NOW = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)


class Backend:
    def __init__(self, *, installed=(), running=()):
        self.installed=set(installed)
        self.resident=set(running)
        self.loads=[]
        self.unloads=[]

    def models(self):
        return {"models":[{"name":name} for name in sorted(self.installed)]}

    def running(self):
        return {"models":[{"name":name} for name in sorted(self.resident)]}

    def pull(self, name):
        self.installed.add(name)
        return {"done":True}

    def load(self, name, *, keep_alive):
        if name not in self.installed:
            raise RuntimeError("not installed")
        self.loads.append((name, keep_alive))
        self.resident.add(name)
        return {"done":True}

    def unload(self, name):
        self.unloads.append(name)
        self.resident.discard(name)
        return {"done":True}


def _selection(primary="vendor/primary:any", secondary="vendor/secondary:any"):
    return CognitiveModelSelection(
        routing_enabled=secondary is not None,
        primary=ProviderConfiguration(provider="ollama", model=primary),
        secondary=(
            None
            if secondary is None
            else ProviderConfiguration(provider="ollama", model=secondary)
        ),
    )


def test_unavailable_model_is_not_pulled_or_invented():
    manager=ModelLifecycleManager(
        selection=_selection(),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=Backend(installed=("vendor/secondary:any",)),
    )
    with pytest.raises(ModelUnavailableError):
        manager.ensure_available(CognitiveModelRole.PRIMARY, now=NOW)


def test_idle_sweep_unloads_only_after_policy_timeout():
    names=("vendor/primary:any","vendor/secondary:any")
    backend=Backend(installed=names, running=names)
    manager=ModelLifecycleManager(
        selection=_selection(*names),
        policy=ModelLifecycleConfiguration(
            enabled=True,
            idle_unload_seconds=60,
            keep_alive="3m",
        ),
        backend=backend,
    )
    manager.begin_use(CognitiveModelRole.PRIMARY, now=NOW)
    manager.end_use(CognitiveModelRole.PRIMARY, now=NOW)
    manager.begin_use(CognitiveModelRole.SECONDARY, now=NOW)
    manager.end_use(CognitiveModelRole.SECONDARY, now=NOW)

    assert manager.sweep_idle(now=NOW+timedelta(seconds=59)) == ()
    assert manager.sweep_idle(now=NOW+timedelta(seconds=61)) == names
    assert backend.resident == set()


def test_disabled_policy_never_performs_automatic_unload():
    backend=Backend(
        installed=("vendor/primary:any",),
        running=("vendor/primary:any",),
    )
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(
            enabled=False,
            idle_unload_seconds=1,
        ),
        backend=backend,
    )
    manager.begin_use(CognitiveModelRole.PRIMARY, now=NOW)
    manager.end_use(CognitiveModelRole.PRIMARY, now=NOW)
    assert manager.sweep_idle(now=NOW+timedelta(hours=1)) == ()
    assert backend.unloads == []


def test_statuses_are_role_based_and_model_name_agnostic():
    backend=Backend(
        installed=("vendor/primary:any","vendor/secondary:any"),
        running=("vendor/secondary:any",),
    )
    manager=ModelLifecycleManager(
        selection=_selection(),
        policy=ModelLifecycleConfiguration(),
        backend=backend,
    )
    states={item.role:item.state for item in manager.statuses(now=NOW)}
    assert states=={
        CognitiveModelRole.PRIMARY:ModelResidency.UNLOADED,
        CognitiveModelRole.SECONDARY:ModelResidency.READY,
    }


class Delegate(CognitiveEngine):
    def __init__(self):
        self.calls=0

    def respond(self, request):
        self.calls+=1
        return CognitiveResponse(content="awake")


def test_lifecycle_engine_lets_cognition_wake_unloaded_model_without_preload():
    backend=Backend(
        installed=("vendor/primary:any",),
        running=(),
    )
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=backend,
    )
    delegate=Delegate()
    engine=LifecycleManagedCognitiveEngine(
        delegate=delegate,
        lifecycle=manager,
        role=CognitiveModelRole.PRIMARY,
    )

    response=engine.respond(CognitiveRequest(messages=()))

    assert response.content=="awake"
    assert delegate.calls==1
    assert backend.loads==[]
    assert backend.resident==set()


def test_idle_sweep_never_unloads_busy_model():
    backend=Backend(
        installed=("vendor/primary:any",),
        running=("vendor/primary:any",),
    )
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(
            enabled=True,
            idle_unload_seconds=60,
        ),
        backend=backend,
    )
    manager.begin_use(CognitiveModelRole.PRIMARY, now=NOW)

    assert manager.sweep_idle(now=NOW+timedelta(hours=1))==()
    assert backend.resident=={"vendor/primary:any"}

    manager.end_use(CognitiveModelRole.PRIMARY, now=NOW+timedelta(hours=1))
    assert manager.sweep_idle(
        now=NOW+timedelta(hours=1, seconds=61)
    )==("vendor/primary:any",)


def test_install_pulls_missing_configured_role_without_loading_it():
    backend=Backend()
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(),
        backend=backend,
    )
    status=manager.install(CognitiveModelRole.PRIMARY)
    assert status.state is ModelResidency.UNLOADED
    assert backend.installed=={"vendor/primary:any"}
    assert backend.resident==set()


def test_install_missing_provisions_all_configured_roles_without_loading():
    names=("vendor/primary:any","vendor/secondary:any")
    backend=Backend()
    manager=ModelLifecycleManager(
        selection=_selection(*names),
        policy=ModelLifecycleConfiguration(
            enabled=True,
            auto_install_missing=True,
        ),
        backend=backend,
    )

    installed=manager.install_missing()

    assert installed==names
    assert backend.installed==set(names)
    assert backend.resident==set()


def test_install_missing_is_disabled_by_policy():
    backend=Backend()
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(
            enabled=True,
            auto_install_missing=False,
        ),
        backend=backend,
    )

    assert manager.install_missing()==()
    assert backend.installed==set()


def test_ensure_available_rejects_missing_model_without_loading_or_pulling():
    backend=Backend(installed=("vendor/secondary:any",))
    manager=ModelLifecycleManager(
        selection=_selection(),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=backend,
    )

    with pytest.raises(ModelUnavailableError):
        manager.ensure_available(CognitiveModelRole.PRIMARY, now=NOW)

    assert backend.loads==[]
    assert backend.installed=={"vendor/secondary:any"}


def test_ensure_available_accepts_installed_unloaded_model_without_preload():
    backend=Backend(installed=("vendor/primary:any",))
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=backend,
    )

    status=manager.ensure_available(CognitiveModelRole.PRIMARY, now=NOW)

    assert status.state is ModelResidency.UNLOADED
    assert backend.loads==[]
    assert backend.resident==set()


class ChatWakeDelegate(CognitiveEngine):
    """Test double for Ollama chat, which wakes the addressed model."""

    def __init__(self, *, backend: Backend, model: str, content: str):
        self.backend = backend
        self.configuration = ProviderConfiguration(
            provider="ollama",
            model=model,
        )
        self.content = content
        self.calls = 0

    def respond(self, request):
        self.calls += 1
        self.backend.resident.add(self.configuration.model)
        return CognitiveResponse(content=self.content)


def test_verify_route_wakes_and_uses_both_lifecycle_managed_models():
    primary_name = "vendor/primary:any"
    secondary_name = "vendor/secondary:any"
    backend = Backend(
        installed=(primary_name, secondary_name),
        running=(),
    )
    manager = ModelLifecycleManager(
        selection=_selection(primary_name, secondary_name),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=backend,
    )
    primary_delegate = ChatWakeDelegate(
        backend=backend,
        model=primary_name,
        content="primary",
    )
    secondary_delegate = ChatWakeDelegate(
        backend=backend,
        model=secondary_name,
        content="secondary critique",
    )
    primary = LifecycleManagedCognitiveEngine(
        delegate=primary_delegate,
        lifecycle=manager,
        role=CognitiveModelRole.PRIMARY,
    )
    secondary = LifecycleManagedCognitiveEngine(
        delegate=secondary_delegate,
        lifecycle=manager,
        role=CognitiveModelRole.SECONDARY,
    )
    router = RoutingCognitiveEngine(
        CognitiveEngineRegistry(
            primary=primary,
            secondary=secondary,
        )
    )

    response = router.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="verify this",
                ),
            ),
            allow_tools=False,
            route_hint="verify",
        )
    )

    assert response.content == "primary"
    assert router.last_decision is not None
    assert router.last_decision.route is CognitiveRoute.VERIFY
    assert primary_delegate.calls == 2
    assert secondary_delegate.calls == 1
    assert backend.resident == {primary_name, secondary_name}
    assert router.last_execution is not None
    assert tuple(
        step.role for step in router.last_execution.successful_steps
    ) == ("primary", "secondary", "primary")
    assert tuple(
        step.model for step in router.last_execution.successful_steps
    ) == (primary_name, secondary_name, primary_name)
    assert router.last_execution.verification_passes == 2
