from datetime import datetime, timezone
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.run.active_release import ActiveRelease
from sofia.run.update_restart import (
    ActiveReleaseChangeMonitor,
    UpdateRestartAction,
    configured_update_restart_mode,
    queue_update_restart_request,
)
from sofia.ui.notifications import DesktopNotificationStore


NOW = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)


def release(tmp_path, release_id, digest):
    return ActiveRelease(
        release_id=release_id,
        manifest_sha256=digest,
        artifact_sha256="b" * 64,
        application_version="1.0",
        artifact_path=tmp_path,
        wheel_path=tmp_path / "sofia.whl",
        dependency_lock_path=tmp_path / "requirements.lock",
    )


def test_activated_release_change_restarts_automatically(tmp_path):
    old = release(tmp_path, "release-1", "a" * 64)
    new = release(tmp_path, "release-2", "c" * 64)
    monitor = ActiveReleaseChangeMonitor(old)

    assert monitor.evaluate(old, mode="automatic") is UpdateRestartAction.NONE
    assert (
        monitor.evaluate(new, mode="automatic")
        is UpdateRestartAction.AUTOMATIC_RESTART
    )


def test_ask_mode_notifies_once_and_persists_setting(tmp_path):
    state_path = tmp_path / "state.db"
    state_path.touch()
    RuntimeUserSettingsStore(state_path).save(
        RuntimeUserSettings(update_restart_mode="ask")
    )
    assert configured_update_restart_mode(state_path) == "ask"

    new = release(tmp_path, "release-2", "c" * 64)
    monitor = ActiveReleaseChangeMonitor(None)
    assert monitor.evaluate(new, mode="ask") is UpdateRestartAction.ASK_OWNER
    assert monitor.evaluate(new, mode="ask") is UpdateRestartAction.NONE

    queue_update_restart_request(state_path, new, now=NOW)
    notification = DesktopNotificationStore(state_path).claim_next(now=NOW)
    assert notification is not None
    assert "release-2" in notification.content
