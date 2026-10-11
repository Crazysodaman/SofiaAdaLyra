"""End-to-end authenticated Android Main history and conversation mode isolation.

Test source is authored alongside the production path. Do not run the test
suite until the user authorizes the end-of-coding verification campaign.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.mobile.gateway import MobileCompanionGateway
from sofia.mobile.server import MobileCompanionServer, MobileServerConfiguration
from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore


NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


class CanonicalMainApp:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.runtime = SimpleNamespace(environment_service=None)
        self.sessions = {}
        self.serial = 0

    def open_channel_conversation(self, *, session_id=None):
        if session_id is not None:
            return self.sessions[session_id]
        self.serial += 1
        conversation = SimpleNamespace(session_id=f"mobile-new-{self.serial}")
        self.sessions[conversation.session_id] = conversation
        return conversation

    def main_thread_page(self, *, principal, before=None, limit=30):
        store = LifelongThreadStore(self.state_path)
        main = store.get_or_create(owner=principal)
        return store.visible_message_page(
            thread_id=main.thread_id, principal=principal,
            before=before, limit=limit,
        )


def _setup(tmp_path):
    path = tmp_path / "sofia.db"
    source = ConversationStore(path)
    social = SocialSessionStore(path)
    app = CanonicalMainApp(path)
    gateway = MobileCompanionGateway(app, state_path=path)
    return path, source, social, app, gateway


def _allow_private_main(path):
    PermissionStore(path).set_private_adult_authority(
        private_chat=True, adult_chat=False,
        adult_avatar=False, adult_external_delivery=False,
    )


def _record(source, social, gateway, *, private_mode, text, number):
    principal = gateway._principal("android-owner", private_mode=private_mode)
    session = source.create_session()
    social.bind(session_id=session.id, principal=principal)
    message = ConversationMessage(
        id=f"source-{number}", session_id=session.id,
        role=ConversationRole.USER, content=text,
        created_at=NOW + timedelta(seconds=number),
    )
    source.save(message)
    store = LifelongThreadStore(source.database_path)
    main = store.get_or_create(owner=principal)
    store.link_message(
        thread_id=main.thread_id, source_message_id=message.id,
        principal=principal,
    )
    return principal


def test_mobile_main_only_shows_exact_source_audience_with_keyset_paging(tmp_path):
    path, source, social, _, gateway = _setup(tmp_path)
    _allow_private_main(path)
    try:
        _record(source, social, gateway, private_mode=False, text="Shared older", number=1)
        _record(source, social, gateway, private_mode=False, text="Shared newer", number=2)
        _record(source, social, gateway, private_mode=True, text="Private only", number=3)

        standard = gateway.main_history(
            device_id="android-owner", private_mode=False, limit=1,
        )
        assert [row["content"] for row in standard["messages"]] == ["Shared newer"]
        assert standard["audience_kind"] == "shared"
        assert standard["has_more"] is True
        older = gateway.main_history(
            device_id="android-owner", private_mode=False, limit=1,
            before=standard["next_before"],
        )
        assert [row["content"] for row in older["messages"]] == ["Shared older"]
        private = gateway.main_history(
            device_id="android-owner", private_mode=True, limit=50,
        )
        assert [row["content"] for row in private["messages"]] == ["Private only"]
        assert private["audience_kind"] == "private"
        another_device = gateway.main_history(
            device_id="android-other", private_mode=True,
        )
        assert another_device["messages"] == []
    finally:
        source.close()


@pytest.mark.parametrize("bad", (
    {"linked_at": "2026-10-10T00:00:00", "message_id": "id"},
    {"linked_at": "x", "message_id": "id"},
    {"linked_at": NOW.isoformat(), "message_id": ""},
    {"linked_at": NOW.isoformat(), "message_id": "id", "principal_id": "other"},
    ["unsupported"],
))
def test_mobile_history_rejects_untrusted_or_invalid_cursors(tmp_path, bad):
    _, source, _, _, gateway = _setup(tmp_path)
    try:
        with pytest.raises((TypeError, ValueError)):
            gateway.main_history(
                device_id="android-owner", private_mode=False, before=bad,
            )
    finally:
        source.close()


def test_mobile_http_main_page_requires_bearer_and_scopes_content(tmp_path):
    path, source, social, _, gateway = _setup(tmp_path)
    _allow_private_main(path)
    _record(source, social, gateway, private_mode=True, text="Secret line", number=1)
    token = "t" * 40
    server = MobileCompanionServer(
        gateway, token=token,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    host, port = server.address
    body = json.dumps({
        "device_id": "android-owner", "private_mode": False,
        "before": None, "limit": 25,
    })
    try:
        denied = HTTPConnection(host, port, timeout=5)
        denied.request("POST", "/v1/mobile/main/page", body=body)
        assert denied.getresponse().status == 401
        denied.close()

        authenticated = HTTPConnection(host, port, timeout=5)
        authenticated.request(
            "POST", "/v1/mobile/main/page", body=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        reply = authenticated.getresponse()
        response = json.loads(reply.read())
        authenticated.close()
        assert reply.status == 200
        assert response["messages"] == []
        assert "Secret line" not in json.dumps(response)
    finally:
        server.close()
        source.close()


def test_mobile_modes_persist_distinct_sessions_and_reject_rebinding(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    try:
        shared = gateway._conversation("android-owner", private_mode=False)
        private = gateway._conversation("android-owner", private_mode=True)
        assert shared.session_id != private.session_id
        with closing(sqlite3.connect(path)) as db:
            stored = db.execute(
                "SELECT presentation_mode,session_id "
                "FROM mobile_conversation_binding_v2 ORDER BY presentation_mode"
            ).fetchall()
        assert len(stored) == 2
        assert {x[1] for x in stored} == {
            shared.session_id, private.session_id,
        }
        # Recreated adapter checks the CURRENT social binding before reuse.
        social.bind(
            session_id=shared.session_id,
            principal=PrincipalContext(
                principal_id="another-owner",
                audience_id="foreign-channel",
                audience_kind=AudienceKind.SHARED,
            ),
        )
        reloaded = MobileCompanionGateway(app, state_path=path)
        with pytest.raises(PermissionError, match="authenticated audience"):
            reloaded._conversation("android-owner", private_mode=False)
    finally:
        source.close()


def test_private_main_history_requires_host_permission(tmp_path):
    _, source, social, _, gateway = _setup(tmp_path)
    try:
        _record(source, social, gateway, private_mode=True, text="Protected", number=1)
        with pytest.raises(PermissionError, match="private-chat grant"):
            gateway.main_history(device_id="android-owner", private_mode=True)
    finally:
        source.close()
