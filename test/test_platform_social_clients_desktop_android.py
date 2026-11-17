from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.platform.chat_clients.android import AndroidRemoteChatSession
from sofia.platform.chat_clients.contracts import (
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MembershipStatus,
    MessagePage,
    RoomKind,
    RoomMembership,
    SendReceipt,
    SendStatus,
)
from sofia.platform.chat_clients.desktop import RemoteDesktopChatClient
from sofia.platform.chat_clients.drafts import ClientDraftStore
from sofia.platform.chat_clients.render import (
    render_chat_screen,
    shared_theme_tokens,
)
from sofia.platform.chat_clients.stage6_simulation import SyntheticStage6World
from sofia.platform.chat_clients.voice import (
    AudioEvidenceKind,
    AudioTestEvidence,
    SimultaneousCoreVoiceSeam,
)

pytestmark = pytest.mark.pkg_social

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "sofia" / "platform" / "chat_clients"


class _Backend:
    def __init__(self, statuses: list[SendStatus] | None = None) -> None:
        self._core = CoreIdentity(
            core_id="22222222-2222-4222-8222-222222222222",
            platform_id="platform.android.test",
            generation=1,
            display_name="Remote",
        )
        self._statuses = list(statuses or [])
        self._room = ChatRoom(
            room_id="room.general", kind=RoomKind.GENERAL,
            title="general", created_by_core_id=None,
            created_at=datetime.now(timezone.utc),
        )
        self._membership = RoomMembership(
            room_id="room.general", core_id=self._core.core_id, epoch=1,
            status=MembershipStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc),
            history_from_sequence=0,
        )

    def list_cores(self):
        return (self._core,)

    def connection_state(self, core_id):
        return ConnectionState.CONNECTED

    def list_rooms(self, core_id):
        return (self._room,)

    def memberships(self, core_id, room_id):
        return (self._membership,)

    def history_page(self, core_id, room_id, *, before_sequence=None, limit=50):
        return MessagePage(
            messages=(), before_sequence=before_sequence, has_more=False,
            oldest_sequence=None, newest_sequence=None,
        )

    def send_message(self, core_id, room_id, body, *, client_message_id,
                     reply_to=None, audience=None):
        return SendReceipt(
            client_message_id=client_message_id,
            room_id=room_id,
            status=self._statuses.pop(0),
        )

    def events(self, *, after_revision, core_id=None):
        return ()


def test_desktop_is_remote_only_and_never_opens_canonical_state():
    backend = _Backend()
    desktop = RemoteDesktopChatClient(
        backend=backend, client_id="desktop",
        drafts=ClientDraftStore(client_id="desktop"),
    )
    capabilities = desktop.capabilities()
    assert capabilities.remote_transport is True
    assert capabilities.local_core_cognition is False
    assert capabilities.canonical_database is False
    assert capabilities.private_core_state is False
    desktop.select_core(backend.list_cores()[0])
    assert "CORE: Remote" in desktop.render()

    with pytest.raises(ValueError, match="remote-only"):
        RemoteDesktopChatClient(
            backend=backend, client_id="desktop", transport_kind="local"
        )
    with pytest.raises(ValueError, match="canonical database"):
        RemoteDesktopChatClient(
            backend=backend, client_id="desktop",
            canonical_database_path="sofia.db",
        )
    with pytest.raises(ValueError, match="private Core workspace"):
        RemoteDesktopChatClient(
            backend=backend, client_id="desktop",
            core_workspace_path="core-state",
        )


def test_android_is_core_free_remote_and_bounded():
    backend = _Backend()
    session = AndroidRemoteChatSession(
        backend=backend, client_id="android", battery_percent=100,
    )
    capabilities = session.capabilities()
    assert capabilities.remote_transport is True
    assert capabilities.local_core_cognition is False
    assert capabilities.canonical_database is False
    assert capabilities.offline_private_state_share is False

    with pytest.raises(ValueError, match="canonical database"):
        AndroidRemoteChatSession(
            backend=backend, client_id="android",
            canonical_database_path="sofia.db",
        )
    with pytest.raises(ValueError, match="Core cognition"):
        AndroidRemoteChatSession(
            backend=backend, client_id="android",
            core_workspace_path="core-state",
        )

    session.select_core(backend.list_cores()[0])
    session.open_room("room.general")
    session.save_draft("bounded android draft")
    assert session.snapshot().draft.content == "bounded android draft"


def test_android_adaptive_polling_respects_battery_and_metering():
    backend = _Backend()
    session = AndroidRemoteChatSession(
        backend=backend, client_id="android",
        battery_percent=100, metered=False, foreground=True,
    )
    assert session.poll_interval_seconds() == 15
    session.update_environment(battery_percent=15)
    assert session.poll_interval_seconds() == 60
    session.update_environment(battery_percent=5)
    assert session.poll_interval_seconds() == 120
    session.update_environment(battery_percent=100, metered=True)
    assert session.poll_interval_seconds() == 30
    session.update_environment(foreground=False)
    assert session.poll_interval_seconds() == 180
    session.update_environment(metered=False)
    assert session.poll_interval_seconds() == 90
    assert session.poll_interval_seconds(connection_state="offline") == 300

    session.select_core(backend.list_cores()[0])
    now = datetime.now(timezone.utc)
    assert session.should_poll(now=now, last_poll=None) is True
    assert session.should_poll(
        now=now, last_poll=now - timedelta(seconds=30)
    ) is False
    assert session.should_poll(
        now=now, last_poll=now - timedelta(seconds=91)
    ) is True


def test_android_receipts_never_claim_delivery_without_confirmation():
    backend = _Backend([
        SendStatus.SENT_UNCONFIRMED,
        SendStatus.PENDING,
        SendStatus.SENT_CONFIRMED,
    ])
    session = AndroidRemoteChatSession(
        backend=backend, client_id="android",
        drafts=ClientDraftStore(client_id="android"),
    )
    session.select_core(backend.list_cores()[0])
    session.open_room("room.general")
    first = session.send("unconfirmed")
    second = session.send("pending")
    third = session.send("confirmed")
    receipts = {item.client_message_id: item for item in session.receipts()}
    assert receipts[first.client_message_id].delivered is False
    assert receipts[second.client_message_id].delivered is False
    assert receipts[third.client_message_id].delivered is True
    assert len(session.receipts()) <= 64


def test_android_authenticated_catch_up_after_offline():
    world = SyntheticStage6World()
    identities = world.identities()
    session = AndroidRemoteChatSession(
        backend=world, client_id="android",
        battery_percent=60, drafts=ClientDraftStore(client_id="android"),
    )
    session.select_core(identities[0])
    session.open_room("room.general")
    world.set_offline(identities[0].core_id)
    sender = world.identities()[1]
    world.send_message(
        sender.core_id, "room.general", "while the phone was offline",
        client_message_id="android.catchup.1",
    )
    world.reconnect_core(identities[0].core_id)
    result = session.catch_up()
    assert result.connection is ConnectionState.CONNECTED
    assert any(
        item.body == "while the phone was offline"
        for item in session.snapshot().messages
    )


def test_client_package_has_no_core_or_canonical_database_imports():
    forbidden = (
        "import sqlite3",
        "from sofia.core.cognition",
        "import sofia.core.cognition",
        "canonical_sqlite",
        "CanonicalSQLite",
        "sofia.core.social.store",
    )
    sources = sorted(PACKAGE.glob("*.py"))
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name} contains {token}"


def test_shared_theme_tokens_and_text_fallback_are_reused():
    tokens = shared_theme_tokens()
    assert tokens["primary"] == "#9400D3"
    assert tokens["accent"] == "#00C2FF"
    assert tokens["danger"] == "#9F0202"

    world = SyntheticStage6World()
    desktop = RemoteDesktopChatClient(
        backend=world, client_id="desktop",
        drafts=ClientDraftStore(client_id="desktop"),
    )
    desktop.select_core(world.identities()[0])
    text = render_chat_screen(desktop.snapshot(), no_color=True)
    assert "\x1b[" not in text
    assert "CONNECTION: CONNECTED" in text


def test_group_voice_is_not_claimed_without_real_audio_evidence():
    seam = SimultaneousCoreVoiceSeam()
    identities = SyntheticStage6World().identities()[:2]
    core_ids = tuple(item.core_id for item in identities)
    report = seam.report(core_ids)
    assert report.group_voice_claimed is False
    assert report.simultaneous_voice_supported is False
    assert report.evidence_kind is AudioEvidenceKind.NONE

    seam.record_evidence(
        core_ids[0],
        AudioTestEvidence(AudioEvidenceKind.DETERMINISTIC_SIMULATION),
    )
    seam.record_evidence(
        core_ids[1],
        AudioTestEvidence(AudioEvidenceKind.DETERMINISTIC_SIMULATION),
    )
    assert seam.report(core_ids).group_voice_claimed is False

    seam.record_evidence(
        core_ids[0],
        AudioTestEvidence(
            AudioEvidenceKind.REAL_AUDIO_SESSION, ("receipt.audio.core0",)
        ),
    )
    assert seam.report(core_ids).group_voice_claimed is False

    seam.record_evidence(
        core_ids[1],
        AudioTestEvidence(
            AudioEvidenceKind.REAL_AUDIO_SESSION, ("receipt.audio.core1",)
        ),
    )
    final = seam.report(core_ids)
    assert final.group_voice_claimed is True
    assert final.simultaneous_voice_supported is True
    assert final.evidence_kind is AudioEvidenceKind.REAL_AUDIO_SESSION
