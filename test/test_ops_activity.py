from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.ops import (
    ActivityMode,
    FleetHost,
    HostActivityObservation,
    HostActivityState,
    HostActivityStore,
    HostLifecycle,
    HostTelemetry,
    PlacementEngine,
    WorkloadContract,
    detect_windows_game,
)
from sofia.system.model import ProcessInspection


NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return path


def test_manual_game_mode_override_wins_over_auto_observation(state):
    store = HostActivityStore(state)
    store.record(
        HostActivityObservation(
            "venus",
            ActivityMode.NORMAL,
            NOW,
            "process-inspection",
        )
    )
    assert store.state("venus").effective is ActivityMode.NORMAL

    store.set_override("venus", ActivityMode.GAMING, at=NOW + timedelta(seconds=1))
    forced = store.state("venus")
    assert forced.override is ActivityMode.GAMING
    assert forced.effective is ActivityMode.GAMING
    assert forced.source == "operator-override"

    store.set_override("venus", ActivityMode.AUTO, at=NOW + timedelta(seconds=2))
    assert store.state("venus").effective is ActivityMode.NORMAL


def test_activity_store_refuses_stale_observation(state):
    store = HostActivityStore(state)
    store.record(HostActivityObservation("venus", ActivityMode.GAMING, NOW, "first"))
    with pytest.raises(ValueError, match="stale"):
        store.record(
            HostActivityObservation(
                "venus",
                ActivityMode.NORMAL,
                NOW - timedelta(seconds=1),
                "older",
            )
        )


def test_steam_library_process_is_detected_without_steam_web_api():
    processes = (
        ProcessInspection(100, "steam.exe", r"C:\Program Files (x86)\Steam\steam.exe"),
        ProcessInspection(
            200,
            "factorio.exe",
            r"D:\SteamLibrary\steamapps\common\Factorio\bin\x64\factorio.exe",
        ),
    )
    gaming, game = detect_windows_game(processes)
    assert gaming is True
    assert game == "factorio.exe"


def test_steam_helper_alone_is_not_a_game():
    gaming, game = detect_windows_game(
        (
            ProcessInspection(
                100,
                "steamwebhelper.exe",
                r"C:\Program Files (x86)\Steam\bin\cef\steamwebhelper.exe",
            ),
        )
    )
    assert gaming is False
    assert game is None


def _host(host_id, cpu):
    return FleetHost(
        host_id,
        "windows",
        "x86_64",
        HostLifecycle.HEALTHY,
        True,
        HostTelemetry(NOW, cpu_percent=cpu, ram_used_bytes=1, ram_total_bytes=100),
    )


def test_placement_prefers_non_gaming_host_before_lower_cpu_gaming_host():
    workload = WorkloadContract("background", "1", ("windows",), ("x86_64",))
    decision = PlacementEngine().choose(
        workload,
        (_host("venus", 5), _host("artemis", 30)),
        activities={
            "venus": HostActivityState(
                "venus", ActivityMode.GAMING, ActivityMode.GAMING, NOW, "operator-override"
            ),
            "artemis": HostActivityState(
                "artemis", ActivityMode.AUTO, ActivityMode.NORMAL, NOW, "telemetry"
            ),
        },
    )
    assert decision.host_id == "artemis"


def test_explicit_interactive_compatible_workload_can_use_gaming_host():
    workload = WorkloadContract(
        "ui-client",
        "1",
        ("windows",),
        ("x86_64",),
        allow_interactive_host=True,
    )
    decision = PlacementEngine().choose(
        workload,
        (_host("venus", 5), _host("artemis", 30)),
        activities={
            "venus": HostActivityState(
                "venus", ActivityMode.GAMING, ActivityMode.GAMING, NOW, "manual"
            ),
        },
    )
    assert decision.host_id == "venus"


def test_wallpaper_engine_and_steamvr_do_not_trigger_game_mode():
    gaming, game = detect_windows_game(
        (
            ProcessInspection(
                100,
                "wallpaper32.exe",
                r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\wallpaper32.exe",
            ),
            ProcessInspection(
                101,
                "vrserver.exe",
                r"D:\SteamLibrary\steamapps\common\SteamVR\bin\win64\vrserver.exe",
            ),
        )
    )
    assert gaming is False
    assert game is None


def test_real_game_wins_when_steam_utilities_are_also_running():
    gaming, game = detect_windows_game(
        (
            ProcessInspection(
                100,
                "wallpaper32.exe",
                r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\wallpaper32.exe",
            ),
            ProcessInspection(
                200,
                "Spyro-Win64-Shipping.exe",
                r"E:\SteamLibrary\steamapps\common\Spyro Reignited Trilogy\Falcon\Binaries\Win64\Spyro-Win64-Shipping.exe",
            ),
            ProcessInspection(
                300,
                "vrserver.exe",
                r"D:\SteamLibrary\steamapps\common\SteamVR\bin\win64\vrserver.exe",
            ),
        )
    )
    assert gaming is True
    assert game == "Spyro-Win64-Shipping.exe"



def test_stale_venus_auto_activity_never_outranks_fresh_windows_gpu_worker():
    """Deferred Phase 11 gaming-first Fleet ranking with frozen clocks."""
    workload = WorkloadContract(
        "small-fleet-llm", "1", ("windows",), ("x86_64",),
    )
    stale_venus = HostActivityState(
        "venus", ActivityMode.AUTO, ActivityMode.NORMAL,
        NOW - timedelta(minutes=8), "old-process-inspection",
    )
    fresh_worker = HostActivityState(
        "gpu-windows", ActivityMode.AUTO, ActivityMode.NORMAL,
        NOW, "current-process-inspection",
    )
    decision = PlacementEngine().choose(
        workload, (_host("venus", 5), _host("gpu-windows", 30)),
        activities={"venus": stale_venus, "gpu-windows": fresh_worker},
        now=NOW,
    )
    assert decision.host_id == "gpu-windows"


def test_missing_activity_does_not_outrank_fresh_non_gaming_worker():
    workload = WorkloadContract(
        "small-fleet-llm", "1", ("windows",), ("x86_64"),
    )
    decision = PlacementEngine().choose(
        workload, (_host("venus", 1), _host("gpu-windows", 70)),
        activities={
            "gpu-windows": HostActivityState(
                "gpu-windows", ActivityMode.AUTO, ActivityMode.NORMAL,
                NOW, "current-process-inspection",
            ),
        },
        now=NOW,
    )
    assert decision.host_id == "gpu-windows"


def test_explicit_manual_normal_override_remains_owner_authority():
    workload = WorkloadContract(
        "small-fleet-llm", "1", ("windows",), ("x86_64"),
    )
    decision = PlacementEngine().choose(
        workload, (_host("venus", 5), _host("gpu-windows", 30)),
        activities={
            "venus": HostActivityState(
                "venus", ActivityMode.NORMAL, ActivityMode.NORMAL,
                NOW - timedelta(days=1), "operator-override",
            ),
            "gpu-windows": HostActivityState(
                "gpu-windows", ActivityMode.AUTO, ActivityMode.NORMAL,
                NOW, "process-inspection",
            ),
        },
        now=NOW,
    )
    assert decision.host_id == "venus"
