from dataclasses import replace
from pathlib import Path
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from queue import Queue
import sqlite3

from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.discord.provisioning import DiscordProvisioning
from sofia.mobile.notifications import MobileNotificationStore
from sofia.ui.desktop_worker import (
    DesktopApplicationWorker,
)


PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"
)


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
        (
            '{"name": "Sofía", '
            '"traits": ["rigorous", "curious", "direct"], '
            '"communication_style": "Clear and direct."}'
        ),
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="desktop-worker-test",
        ),
        filesystem_root=tmp_path,
    )


def test_worker_owns_real_application_for_full_lifecycle(
    tmp_path: Path,
):
    events: Queue[tuple[str, object]] = Queue()
    worker = DesktopApplicationWorker(
        configuration=_configuration(tmp_path),
        session_id=None,
        events=events,
        discord_provisioning=DiscordProvisioning(enabled=False),
    )

    worker.start()

    kind, payload = events.get(timeout=30)
    assert kind == "started"
    history, draft, palette = payload
    assert isinstance(history, tuple)
    assert isinstance(draft, str)
    assert palette.background.startswith("#")

    kind, payload = events.get(timeout=30)
    assert kind == "persistence"
    assert "CANONICAL DB:" in payload
    assert str(tmp_path / "sofia.db") in payload

    kind, payload = events.get(timeout=30)
    assert kind == "discord_disabled"
    assert payload is None

    worker.send("Hello from one worker thread.")

    kind, payload = events.get(timeout=30)
    assert kind == "persistence"
    assert "last send durable: 2 messages" in payload
    assert str(tmp_path / "sofia.db") in payload

    kind, payload = events.get(timeout=30)
    assert kind == "sent"
    history, palette, matrix_status = payload
    assert history[-2].actor == "user"
    assert history[-2].content == (
        "Hello from one worker thread."
    )
    assert history[-1].actor == "sofia"
    assert palette.background.startswith("#")
    assert matrix_status.startswith("MATRIX ")
    assert "req=" in matrix_status
    assert "validation=" in matrix_status

    worker.shutdown("")

    kind, payload = events.get(timeout=30)
    assert kind == "shutdown_complete"
    assert payload is None

    with sqlite3.connect(tmp_path / "sofia.db") as db:
        rows = db.execute(
            "SELECT role, content FROM conversation_messages "
            "ORDER BY created_at ASC"
        ).fetchall()
    assert ("user", "Hello from one worker thread.") in rows
    assert any(role == "assistant" for role, _ in rows)


def test_worker_runs_owner_selected_tool_then_sofia_responds(
    tmp_path: Path,
):
    events: Queue[tuple[str, object]] = Queue()
    worker = DesktopApplicationWorker(
        configuration=replace(
            _configuration(tmp_path),
            filesystem_root=PROJECT_ROOT,
        ),
        session_id=None,
        events=events,
        discord_provisioning=DiscordProvisioning(enabled=False),
    )
    worker.start()
    assert events.get(timeout=30)[0] == "started"
    assert events.get(timeout=30)[0] == "persistence"
    assert events.get(timeout=30)[0] == "discord_disabled"

    worker.load_tools()
    kind, specs = events.get(timeout=30)
    assert kind == "tools"
    assert any(item.tool_name == "inspect_dev_status" for item in specs)

    worker.run_tool("inspect_dev_status", {})
    kind, payload = events.get(timeout=30)
    assert kind == "tool_complete"
    history, _palette, _matrix_status, result = payload
    assert result.capability == "dev.status"
    assert result.kind.value == "success"
    assert history[-2].content == "Owner-direct private tool: inspect_dev_status"
    assert history[-1].actor == "sofia"

    worker.shutdown("")
    assert events.get(timeout=30)[0] == "shutdown_complete"


def test_worker_initializes_provisioned_discord_on_same_application(
    tmp_path: Path,
    monkeypatch,
):
    events: Queue[tuple[str, object]] = Queue()
    starts: list[object] = []
    stops: list[object] = []

    class FakeDiscordBackgroundService:
        def __init__(self, provisioning, channel, *, on_error=None):
            self.provisioning = provisioning
            self.channel = channel
            self.on_error = on_error

        def start(self):
            starts.append(self.channel)

        def stop(self):
            stops.append(self.channel)

    monkeypatch.setattr(
        "sofia.ui.desktop_worker.DiscordBackgroundService",
        FakeDiscordBackgroundService,
    )

    provisioning = DiscordProvisioning(
        enabled=True,
        owner_user_id=123456789012345678,
        bot_user_id=987654321098765432,
        dm_channel_id=223456789012345678,
        token="test-token",
    )
    worker = DesktopApplicationWorker(
        configuration=_configuration(tmp_path),
        session_id=None,
        events=events,
        discord_provisioning=provisioning,
    )

    worker.start()

    kind, payload = events.get(timeout=30)
    assert kind == "started"
    history, draft, palette = payload
    assert isinstance(history, tuple)
    assert isinstance(draft, str)
    assert palette.background.startswith("#")

    kind, payload = events.get(timeout=30)
    assert kind == "persistence"
    assert "CANONICAL DB:" in payload
    assert str(tmp_path / "sofia.db") in payload

    kind, payload = events.get(timeout=30)
    assert kind == "discord_started"
    assert payload is None
    assert len(starts) == 1
    assert starts[0].runtime.session_id

    worker.shutdown("")

    kind, payload = events.get(timeout=30)
    assert kind == "shutdown_complete"
    assert payload is None
    assert stops == starts


def test_worker_marshals_mobile_requests_onto_application_thread(
    tmp_path: Path,
    monkeypatch,
):
    token = "mobile-worker-test-token-that-is-long-enough"
    monkeypatch.setenv("SOFIA_MOBILE_ENABLED", "true")
    monkeypatch.setenv("SOFIA_MOBILE_PORT", "0")
    monkeypatch.setenv("SOFIA_MOBILE_TOKEN", token)
    events: Queue[tuple[str, object]] = Queue()
    worker = DesktopApplicationWorker(
        configuration=_configuration(tmp_path),
        session_id=None,
        events=events,
        discord_provisioning=DiscordProvisioning(enabled=False),
    )

    worker.start()
    address = None
    while address is None:
        kind, payload = events.get(timeout=30)
        if kind == "startup_error":
            raise payload
        if kind == "mobile_started":
            address = payload

    host, port = address
    body = json.dumps({
        "device_id": "android-worker-test",
        "private_mode": False,
    })
    connection = HTTPConnection(host, port, timeout=30)
    connection.request(
        "POST",
        "/v1/mobile/state",
        body=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    response = connection.getresponse()
    result = json.loads(response.read())
    connection.close()

    assert response.status == 200
    assert result["private_mode"] is False
    assert result["adult_chat_enabled"] is False
    assert result["session_id"]

    MobileNotificationStore(tmp_path / "sofia.db").enqueue(
        notification_id="act:worker-mobile",
        title="Sofía",
        content="Worker-routed proactive message.",
        created_at=datetime.now(timezone.utc),
    )
    claim_body = json.dumps({
        "device_id": "android-worker-test",
        "private_mode": False,
    })
    connection = HTTPConnection(host, port, timeout=30)
    connection.request(
        "POST",
        "/v1/mobile/notifications/claim",
        body=claim_body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    claim_response = connection.getresponse()
    claimed = json.loads(claim_response.read())["notification"]
    connection.close()
    assert claim_response.status == 200
    assert claimed["content"] == "Worker-routed proactive message."

    connection = HTTPConnection(host, port, timeout=30)
    connection.request(
        "POST",
        "/v1/mobile/notifications/ack",
        body=json.dumps({
            "device_id": "android-worker-test",
            "notification_id": claimed["id"],
        }),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    ack_response = connection.getresponse()
    acknowledged = json.loads(ack_response.read())
    connection.close()
    assert ack_response.status == 200
    assert acknowledged == {"acknowledged": True}

    worker.shutdown("")
    kind, payload = events.get(timeout=30)
    assert kind == "shutdown_complete"
    assert payload is None
