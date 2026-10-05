"""Private mobile chat, adult authority, and sensor gateway contracts."""
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from types import SimpleNamespace

from sofia.emotion.model import ActiveEmotion, CurrentEmotionalState
from sofia.mobile.gateway import MobileCompanionGateway
from sofia.mobile.server import MobileCompanionServer, MobileServerConfiguration
from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind


NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


class FakeEnvironment:
    def __init__(self):
        self.providers = ()
        self.invalidations = 0

    def register_provider(self, provider):
        self.providers = (*self.providers, provider)

    def invalidate(self):
        self.invalidations += 1


class FakeConversation:
    session_id = "mobile-session"
    current_expression_plan = SimpleNamespace(
        primary="slow-tail-sway",
        alternates=("sultry-gaze",),
        pose="look-back",
        intensity="moderate",
    )

    def __init__(self):
        self.calls = []

    def respond(self, content, *, principal, channel):
        self.calls.append((content, principal, channel))
        return SimpleNamespace(content="Private mobile reply.")

    def current_emotional_state(self, *, now):
        return CurrentEmotionalState(
            as_of=now,
            subject="person:sparks",
            tone="mixed",
            active=(
                ActiveEmotion(
                    "sexual-desire", 0.6, ("assistant:1",), ("event:1",)
                ),
                ActiveEmotion(
                    "affection", 0.5, ("assistant:1",), ("event:1",)
                ),
            ),
        )


class FakeRuntime:
    def __init__(self):
        self.environment_service = FakeEnvironment()

    def avatar_projection_for(self, *, principal, private_grant=None):
        return SimpleNamespace(
            outfit_id="private.violet_tease" if private_grant else "daily.default",
            source_revision=7,
        )


class FakeApplication:
    def __init__(self):
        self.runtime = FakeRuntime()
        self.conversation = FakeConversation()

    def open_channel_conversation(self, *, session_id=None):
        return self.conversation


def _gateway(tmp_path):
    app = FakeApplication()
    gateway = MobileCompanionGateway(app, state_path=tmp_path / "state.db")
    PermissionStore(tmp_path / "state.db").set_private_adult_authority(
        private_chat=True,
        adult_chat=True,
        adult_avatar=True,
        adult_external_delivery=False,
    )
    return app, gateway


def test_mobile_chat_is_authenticated_private_owner_context(tmp_path):
    app, gateway = _gateway(tmp_path)
    result = gateway.chat(
        device_id="android-owner",
        message="Hello privately",
        private_mode=True,
    )

    content, principal, channel = app.conversation.calls[0]
    assert content == "Hello privately"
    assert principal.audience_kind is AudienceKind.PRIVATE
    assert principal.audience_id.startswith("mobile:private:")
    assert channel == "mobile-private"
    assert result["adult_chat_enabled"] is True
    assert result["adult_avatar_enabled"] is True
    assert result["avatar"]["outfit_id"] == "private.violet_tease"
    assert result["expression"]["primary"] == "slow-tail-sway"
    assert result["emotion"]["active"][0]["name"] == "sexual-desire"


def test_private_avatar_requires_explicit_phone_toggle(tmp_path):
    app, gateway = _gateway(tmp_path)
    result = gateway.state(device_id="android-owner", private_mode=False)

    assert result["private_mode"] is False
    assert result["adult_chat_enabled"] is False
    assert result["adult_avatar_enabled"] is False
    assert result["avatar"]["outfit_id"] == "daily.default"

    gateway.chat(
        device_id="android-owner",
        message="Keep this safe for a shared screen",
        private_mode=False,
    )
    _, principal, channel = app.conversation.calls[-1]
    assert principal.audience_kind is AudienceKind.SHARED
    assert channel == "mobile-standard"


def test_sensor_ingestion_invalidates_live_environment(tmp_path):
    app, gateway = _gateway(tmp_path)
    result = gateway.ingest_sensors({
        "device_id": "android-owner",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "America/Chicago",
        "network": "wifi",
        "activity": "stationary",
    })

    assert result["accepted"] is True
    assert app.runtime.environment_service.invalidations == 1
    assert app.runtime.environment_service.providers[0].name == (
        "authenticated-mobile-sensors"
    )


def test_http_server_requires_bearer_token_and_serves_private_state(tmp_path):
    _, gateway = _gateway(tmp_path)
    token = "t" * 40
    server = MobileCompanionServer(
        gateway,
        token=token,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    host, port = server.address
    try:
        denied = HTTPConnection(host, port, timeout=5)
        denied.request("GET", "/v1/mobile/health")
        assert denied.getresponse().status == 401
        denied.close()

        body = json.dumps({
            "device_id": "android-owner",
            "private_mode": True,
        })
        allowed = HTTPConnection(host, port, timeout=5)
        allowed.request(
            "POST",
            "/v1/mobile/state",
            body=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response = allowed.getresponse()
        payload = json.loads(response.read())
        allowed.close()
        assert response.status == 200
        assert payload["private_owner_channel"] is True
        assert payload["adult_chat_enabled"] is True
    finally:
        server.close()


def test_non_loopback_server_requires_tls():
    try:
        MobileServerConfiguration(host="0.0.0.0")
    except ValueError as exc:
        assert "requires TLS" in str(exc)
    else:
        raise AssertionError("non-loopback plaintext binding was accepted")
