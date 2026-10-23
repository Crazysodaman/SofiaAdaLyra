"""Deferred Phase 11 hybrid residency acceptance boundaries.

Synthetic resource observations only. No local/remote Ollama, no GPU probe,
no service start, no platform idle polling, and no host changes in coding phase.
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from sofia.platform.config.model import ModelLifecycleConfiguration
from sofia.platform.config.user_settings import RuntimeUserSettings
from sofia.cognition.model_lifecycle import (
    CognitiveModelRole, ModelLifecycleManager, ModelResidencyMode,
)
from sofia.platform.ops.activity import (
    ActivityMode, observed_desktop_activity,
)
from test.test_model_lifecycle import Backend, _selection, NOW


NAMES=("vendor/primary:any", "vendor/secondary:any")


def resources(*, ram=14000, vram=12000, cpu=8.0, gpu=8.0):
    return SimpleNamespace(
        ram_total_bytes=ram+512,
        ram_used_bytes=512,
        vram_total_bytes=None if vram is None else vram+512,
        vram_used_bytes=None if vram is None else 512,
        cpu_percent=cpu,
        gpu_percent=gpu,
        throttled=False,
    )


def manager(backend, *, gaming, idle, ram=14000, vram=12000):
    return ModelLifecycleManager(
        selection=_selection(*NAMES),
        policy=ModelLifecycleConfiguration(
            enabled=True, residency_mode="hybrid_gaming_idle",
            idle_preload_seconds=1800,
        ),
        backend=backend,
        resource_observer=lambda: resources(ram=ram,vram=vram),
        gaming_observer=lambda: gaming,
        idle_observer=lambda: idle,
    )


def test_gaming_evicts_idle_models_even_with_desktop_idle_claim():
    backend=Backend(
        installed=NAMES,running=NAMES,
        sizes={x:2000 for x in NAMES},
    )
    result=manager(backend,gaming=True,idle=True).reconcile_residency(now=NOW)
    assert result.mode is ModelResidencyMode.HYBRID_GAMING_IDLE
    assert result.desired_roles == ()
    assert backend.resident == set()
    assert set(result.unloaded_models)==set(NAMES)


def test_gaming_never_interrupts_a_model_serving_an_active_turn():
    backend=Backend(
        installed=NAMES,running=NAMES,
        sizes={x:2000 for x in NAMES},
    )
    managed=manager(backend,gaming=True,idle=False)
    managed.begin_use(CognitiveModelRole.PRIMARY,now=NOW)
    decision=managed.reconcile_residency(now=NOW)
    assert NAMES[0] in backend.resident
    assert NAMES[1] not in backend.resident
    assert "active" in " ".join(decision.reasons)


@pytest.mark.parametrize("gaming,idle", [
    (None,True), (False,None), (False,False), (True,True),
])
def test_unverified_desktop_idle_never_preloads(gaming,idle):
    backend=Backend(installed=NAMES,sizes={x:2000 for x in NAMES})
    decision=manager(
        backend,gaming=gaming,idle=idle,
    ).reconcile_residency(now=NOW)
    assert decision.desired_roles == ()
    assert backend.loads == []


def test_verified_30min_idle_preloads_only_installed_fitting_models():
    backend=Backend(installed=NAMES,sizes={x:2000 for x in NAMES})
    decision=manager(
        backend,gaming=False,idle=True,
    ).reconcile_residency(now=NOW)
    assert decision.desired_roles == (
        CognitiveModelRole.PRIMARY,CognitiveModelRole.SECONDARY,
    )
    assert set(decision.loaded_models)==set(NAMES)
    assert backend.resident==set(NAMES)


@pytest.mark.parametrize("ram,vram", [(1500,12000),(14000,3000),(14000,None)])
def test_insufficient_or_unknown_headroom_does_not_preload(ram,vram):
    backend=Backend(installed=NAMES,sizes={x:2000 for x in NAMES})
    decision=manager(
        backend,gaming=False,idle=True,ram=ram,vram=vram,
    ).reconcile_residency(now=NOW)
    assert decision.desired_roles == ()
    assert backend.loads == []


@pytest.mark.parametrize("seconds,expected", [
    (0,ActivityMode.NORMAL),
    (1799.5,ActivityMode.NORMAL),
    (1800,ActivityMode.IDLE),
    (1899,ActivityMode.IDLE),
    (None,ActivityMode.UNKNOWN),
    (-1,ActivityMode.UNKNOWN),
    (float("nan"),ActivityMode.UNKNOWN),
])
def test_real_desktop_idle_threshold_is_exact(seconds,expected):
    assert observed_desktop_activity(
        gaming=False,idle_seconds=seconds,idle_threshold_seconds=1800,
    ) is expected


def test_game_process_outweighs_a_paused_desktop():
    assert observed_desktop_activity(
        gaming=True,idle_seconds=3600,idle_threshold_seconds=1800,
    ) is ActivityMode.GAMING


def test_hybrid_settings_are_explicit_and_threshold_is_bounded():
    settings=RuntimeUserSettings(
        cognitive_model_residency_mode="hybrid_gaming_idle",
        cognitive_model_idle_preload_seconds=1800,
    )
    assert settings.cognitive_model_idle_preload_seconds == 1800
    with pytest.raises(ValueError,match="idle preload"):
        RuntimeUserSettings(
            cognitive_model_residency_mode="hybrid_gaming_idle",
            cognitive_model_idle_preload_seconds=0,
        )
    with pytest.raises(ValueError,match="threshold"):
        ModelLifecycleConfiguration(
            enabled=True,residency_mode="hybrid_gaming_idle",
            idle_preload_seconds=86401,
        )
