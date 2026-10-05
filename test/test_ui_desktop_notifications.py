from datetime import datetime, timedelta, timezone

import pytest

from sofia.ui.notifications import DesktopNotificationStore


NOW = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)


def store(tmp_path):
    path = tmp_path / "state.db"
    path.touch()
    return DesktopNotificationStore(path)


def test_notification_is_durable_claimed_and_acknowledged_once(tmp_path):
    notifications = store(tmp_path)
    queued = notifications.enqueue(
        notification_id="reflection:one",
        title="Sofía",
        content="Hey, I had an idea.",
        created_at=NOW,
    )
    assert queued.status == "queued"

    claimed = notifications.claim_next(now=NOW + timedelta(seconds=1))
    assert claimed is not None
    assert claimed.status == "outcome_unknown"
    notifications.mark_displayed(
        claimed.notification_id,
        now=NOW + timedelta(seconds=2),
    )
    assert notifications.claim_next(now=NOW + timedelta(seconds=3)) is None


def test_notification_id_cannot_be_reused_for_other_content(tmp_path):
    notifications = store(tmp_path)
    notifications.enqueue(
        notification_id="notice:one",
        title="Sofía",
        content="First",
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="different content"):
        notifications.enqueue(
            notification_id="notice:one",
            title="Sofía",
            content="Changed",
            created_at=NOW,
        )
