from types import SimpleNamespace

import pytest

from sofia.ops.activity import ActivityMode
from sofia.system.model import (
    ProcessInspection,
    SystemCapability,
    SystemCapabilityName,
    SystemCapabilityResultKind,
)
from sofia.ui.control_center import GameMode
from sofia.ui.tray_agent import TrayAgentApplication


def test_auto_mode_records_detected_steam_game_without_web_api():
    app = object.__new__(TrayAgentApplication)
    app.host_id = "venus"
    app._known_games = frozenset()
    app.settings_store = SimpleNamespace(
        load=lambda: SimpleNamespace(game_mode=GameMode.AUTO)
    )
    recorded = []
    app.activity_store = SimpleNamespace(record=recorded.append)
    app._process_capability = SystemCapability(
        SystemCapabilityName.PROCESS_INSPECT,
        "test process inspection",
    )
    app._system_backend = SimpleNamespace(
        execute=lambda request: SimpleNamespace(
            kind=SystemCapabilityResultKind.SUCCESS,
            evidence={
                "processes": [
                    ProcessInspection(
                        2,
                        "factorio.exe",
                        r"D:\SteamLibrary\steamapps\common\Factorio\bin\x64\factorio.exe",
                    )
                ]
            },
        )
    )

    app._observe_activity()

    assert len(recorded) == 1
    assert recorded[0].host_id == "venus"
    assert recorded[0].mode is ActivityMode.GAMING
    assert recorded[0].detail == "factorio.exe"


def test_manual_game_mode_skips_auto_process_sampling():
    app = object.__new__(TrayAgentApplication)
    app.settings_store = SimpleNamespace(
        load=lambda: SimpleNamespace(game_mode=GameMode.ON)
    )
    app._system_backend = SimpleNamespace(
        execute=lambda request: (_ for _ in ()).throw(
            AssertionError("should not inspect")
        )
    )

    app._observe_activity()


def test_auto_mode_surfaces_process_inspection_failure():
    app = object.__new__(TrayAgentApplication)
    app.settings_store = SimpleNamespace(
        load=lambda: SimpleNamespace(game_mode=GameMode.AUTO)
    )
    app._process_capability = SystemCapability(
        SystemCapabilityName.PROCESS_INSPECT,
        "test process inspection",
    )
    app._system_backend = SimpleNamespace(
        execute=lambda request: SimpleNamespace(
            kind=SystemCapabilityResultKind.FAILED,
            error="simulated live Windows inspection failure",
            evidence=None,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="process.inspect failed: simulated live Windows inspection failure",
    ):
        app._observe_activity()
