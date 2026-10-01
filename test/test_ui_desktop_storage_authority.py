from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.ui.control_center import (
    DesktopControlSettingsStore,
    RemoteChatMode,
)
from sofia.ui.desktop_application import create_desktop_application


def configuration(tmp_path: Path) -> SofiaConfiguration:
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state):
        pass
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=state,
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
    )


def _seed_legacy_remote_mode(path: Path) -> None:
    store = DesktopControlSettingsStore(path)
    with sqlite3.connect(path) as db:
        db.execute(
            """
            INSERT INTO ui_control_settings (
                settings_key,
                close_to_tray,
                start_with_windows,
                game_mode,
                remote_chat_mode,
                pinned_chat_endpoint,
                runtime_service_name,
                llm_service_name,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(settings_key) DO UPDATE SET
                remote_chat_mode=excluded.remote_chat_mode,
                pinned_chat_endpoint=excluded.pinned_chat_endpoint,
                updated_at=excluded.updated_at
            """,
            (
                store._KEY,
                1,
                0,
                "auto",
                "fleet_auto",
                "https://artemis:7443",
                "SofiaAdaLyra",
                "Ollama",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()


def test_desktop_application_uses_configured_canonical_database(tmp_path):
    config = configuration(tmp_path)

    app = create_desktop_application(config)

    assert isinstance(app, SofiaApplication)
    assert app.chat_storage_mode == "local"
    assert app.chat_state_path == config.state_path
    assert app.local_state_path == config.state_path


def test_legacy_remote_chat_setting_is_migrated_to_local(tmp_path):
    config = configuration(tmp_path)
    _seed_legacy_remote_mode(config.state_path)

    app = create_desktop_application(config)
    settings = DesktopControlSettingsStore(config.state_path).load()

    assert isinstance(app, SofiaApplication)
    assert settings.remote_chat_mode is RemoteChatMode.LOCAL
    assert settings.pinned_chat_endpoint is None
    assert app.chat_state_path == config.state_path
