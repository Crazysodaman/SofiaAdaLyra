from sofia.platform.ops.activity import ActivityMode
from sofia.modules.ui.control_center import GameMode
from sofia.modules.ui.settings_window import _activity_override


def test_master_settings_game_mode_maps_to_ops_override():
    assert _activity_override(GameMode.AUTO) is ActivityMode.AUTO
    assert _activity_override(GameMode.ON) is ActivityMode.GAMING
    assert _activity_override(GameMode.OFF) is ActivityMode.NORMAL
