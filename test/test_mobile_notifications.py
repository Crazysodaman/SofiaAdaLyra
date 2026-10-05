"""Durable paired-phone notification delivery contracts."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.mobile.notifications import MobileNotificationStore


NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def _store(tmp_path):
    path = tmp_path / "state.db"
    path.touch()
    return MobileNotificationStore(path)


def test_notification_claim_ack_and_idempotency(tmp_path):
    store = _store(tmp_path)
    queued = store.enqueue(
        notification_id="act:idea-1",
        title="Sofía",
        content="I had an idea for us.",
        created_at=NOW,
    )
    duplicate = store.enqueue(
        notification_id="act:idea-1",
        title="Sofía",
        content="I had an idea for us.",
        created_at=NOW,
    )

    assert queued == duplicate
    claimed = store.claim_next(device_id="phone-a", now=NOW)
    assert claimed is not None
    assert claimed.content == "I had an idea for us."
    assert store.claim_next(device_id="phone-b", now=NOW) is None
    with pytest.raises(PermissionError):
        store.acknowledge(
            claimed.notification_id,
            device_id="phone-b",
            now=NOW,
        )
    store.acknowledge(
        claimed.notification_id,
        device_id="phone-a",
        now=NOW,
    )
    store.acknowledge(
        claimed.notification_id,
        device_id="phone-a",
        now=NOW,
    )
    assert store.claim_next(device_id="phone-a", now=NOW) is None


def test_unacknowledged_claim_is_redelivered_after_lease(tmp_path):
    store = _store(tmp_path)
    store.enqueue(
        notification_id="act:idea-2",
        title="Sofía",
        content="Still worth sharing.",
        created_at=NOW,
    )

    first = store.claim_next(device_id="phone-a", now=NOW)
    retried = store.claim_next(
        device_id="phone-b",
        now=NOW + timedelta(minutes=6),
    )

    assert first is not None
    assert retried is not None
    assert retried.notification_id == first.notification_id


def test_same_notification_id_cannot_change_content(tmp_path):
    store = _store(tmp_path)
    store.enqueue(
        notification_id="act:idea-3",
        title="Sofía",
        content="Original",
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="different content"):
        store.enqueue(
            notification_id="act:idea-3",
            title="Sofía",
            content="Replacement",
            created_at=NOW,
        )
