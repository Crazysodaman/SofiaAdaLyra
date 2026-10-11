"""CA-5307: host truth for this phone's current visible conversation."""
from test.test_mobile_gateway import _gateway


def test_mobile_state_does_not_imply_other_audience_or_mirroring(tmp_path):
    app, gateway = _gateway(tmp_path)
    gateway.credentials.enroll("android-owner")
    shared = gateway.state(device_id="android-owner", private_mode=False)
    assert shared["session_id"]
    assert shared["audience_kind"] == "shared"
    assert shared["audience_id"].startswith("mobile:standard:")
    assert shared["cross_channel_mirroring"] is False
    assert "thread_id" not in shared
    assert "discord" not in shared["audience_id"]

    private = gateway.state(device_id="android-owner", private_mode=True)
    assert private["session_id"] != shared["session_id"]
    assert private["audience_id"] != shared["audience_id"]
    assert private["audience_kind"] == "private"
    assert private["cross_channel_mirroring"] is False


def test_mobile_history_reports_exact_current_audience_without_cross_channel_echo(tmp_path):
    from test.test_mobile_main_history import _setup
    _, source, _, _, gateway = _setup(tmp_path)
    gateway.credentials.enroll("android-owner")
    page = gateway.main_history(
        device_id="android-owner", private_mode=False,
    )
    assert page["audience_kind"] == "shared"
    assert page["audience_id"].startswith("mobile:standard:")
    assert page["cross_channel_mirroring"] is False
    source.close()
