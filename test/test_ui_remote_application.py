from pathlib import Path
import sqlite3

from sofia.config.model import ProviderConfiguration,SofiaConfiguration
from sofia.ui.control_center import (
    DesktopControlSettings,
    DesktopControlSettingsStore,
    RemoteChatMode,
)
from sofia.ui.remote_application import (
    RemoteDesktopApplication,
    create_desktop_application,
)


def configuration(tmp_path):
    state=tmp_path/"sofia.db"
    with sqlite3.connect(state):
        pass
    return SofiaConfiguration(
        constitution_path=tmp_path/"constitution.md",
        constitution_hash_path=tmp_path/"constitution.sha256",
        identity_path=tmp_path/"identity.json",
        personality_path=tmp_path/"personality.json",
        avatar_path=tmp_path/"avatar.json",
        state_path=state,
        provider=ProviderConfiguration(provider="test",model="test"),
        filesystem_root=tmp_path,
    )


def test_fleet_auto_without_published_remote_endpoint_keeps_local_application(tmp_path,monkeypatch):
    config=configuration(tmp_path)
    monkeypatch.delenv("SOFIA_REMOTE_CHAT_ENDPOINT",raising=False)
    app=create_desktop_application(config)
    from sofia.application import SofiaApplication
    assert isinstance(app,SofiaApplication)


def test_pinned_remote_settings_select_thin_client_without_starting_local_runtime(tmp_path,monkeypatch):
    config=configuration(tmp_path)
    store=DesktopControlSettingsStore(config.state_path)
    store.save(
        DesktopControlSettings(
            remote_chat_mode=RemoteChatMode.PINNED_ENDPOINT,
            pinned_chat_endpoint="https://artemis:7443",
        ),
        at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    monkeypatch.setenv("SOFIA_REMOTE_CHAT_CA_FILE",str(tmp_path/"ca.pem"))
    monkeypatch.setenv("SOFIA_REMOTE_CHAT_CLIENT_CERT",str(tmp_path/"client.pem"))
    monkeypatch.setenv("SOFIA_REMOTE_CHAT_CLIENT_KEY",str(tmp_path/"client.key"))
    monkeypatch.setenv("SOFIA_REMOTE_CHAT_SERVER_PIN","a"*64)
    app=create_desktop_application(config)
    assert isinstance(app,RemoteDesktopApplication)
    assert app.chat_storage_mode == "remote"
    assert app.chat_state_path is None
    assert app.local_state_path == config.state_path
