from pathlib import Path
from queue import Queue

from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
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
    PROJECT_ROOT / "src" / "sofia" / "data" / "avatar.json"
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
    )

    worker.start()

    kind, payload = events.get(timeout=30)
    assert kind == "started"
    history, draft, palette = payload
    assert isinstance(history, tuple)
    assert isinstance(draft, str)
    assert palette.background.startswith("#")

    worker.send("Hello from one worker thread.")

    kind, payload = events.get(timeout=30)
    assert kind == "sent"
    history, palette = payload
    assert history[-2].actor == "user"
    assert history[-2].content == (
        "Hello from one worker thread."
    )
    assert history[-1].actor == "sofia"
    assert palette.background.startswith("#")

    worker.shutdown("")

    kind, payload = events.get(timeout=30)
    assert kind == "shutdown_complete"
    assert payload is None
