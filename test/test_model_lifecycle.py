from datetime import datetime, timedelta, timezone

import pytest

from sofia.cognition.model_lifecycle import (
    CognitiveModelRole,
    ModelLifecycleManager,
    ModelResidency,
    ModelUnavailableError,
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


def test_background_role_prefers_secondary_when_configured():
    manager=ModelLifecycleManager(
        selection=_selection(),
        policy=ModelLifecycleConfiguration(),
        backend=Backend(),
    )
    assert manager.background_role is CognitiveModelRole.SECONDARY


def test_background_role_falls_back_to_primary_for_single_model():
    manager=ModelLifecycleManager(
        selection=_selection(secondary=None),
        policy=ModelLifecycleConfiguration(),
        backend=Backend(),
    )
    assert manager.background_role is CognitiveModelRole.PRIMARY


def test_both_models_can_be_unloaded_then_primary_can_wake_again():
    names=("vendor/primary:any","vendor/secondary:any")
    backend=Backend(installed=names, running=names)
    manager=ModelLifecycleManager(
        selection=_selection(*names),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=backend,
    )

    assert manager.unload_all() == names
    assert backend.resident == set()

    status=manager.ensure_loaded(CognitiveModelRole.PRIMARY, now=NOW)

    assert status.state is ModelResidency.READY
    assert backend.resident == {"vendor/primary:any"}
    assert backend.loads == [("vendor/primary:any","10m")]


def test_unavailable_model_is_not_pulled_or_invented():
    manager=ModelLifecycleManager(
        selection=_selection(),
        policy=ModelLifecycleConfiguration(enabled=True),
        backend=Backend(installed=("vendor/secondary:any",)),
    )
    with pytest.raises(ModelUnavailableError):
        manager.ensure_loaded(CognitiveModelRole.PRIMARY, now=NOW)


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
    manager.note_used(CognitiveModelRole.PRIMARY, now=NOW)
    manager.note_used(CognitiveModelRole.SECONDARY, now=NOW)

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
    manager.note_used(CognitiveModelRole.PRIMARY, now=NOW)
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
