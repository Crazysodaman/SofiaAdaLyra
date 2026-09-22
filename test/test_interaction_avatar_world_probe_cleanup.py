"""Windows-sensitive disposable-probe cleanup; no real Ollama or production DB."""
from dataclasses import replace

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.interaction.avatar_world_probe import _shutdown_disposable_app


def test_disposable_probe_releases_all_runtime_database_connections(monkeypatch, tmp_path):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    monkeypatch.setattr(
        OllamaProvider, '_respond_once',
        lambda self, request: CognitiveResponse(content='Isolated test response.'),
    )
    database = tmp_path / 'probe-only.db'
    config = replace(
        create_default_configuration(), state_path=database, filesystem_root=tmp_path,
    )
    app = SofiaApplication(config)
    try:
        app.start()
        assert app.conversation.respond('I ask to hug you').content == 'Isolated test response.'
    finally:
        _shutdown_disposable_app(app)
    assert app.conversation._conversation_store._connection is None
    assert app.runtime._memory_system._store._connection is None
    assert app.runtime._operational_store._connection is None
    # FilesystemObservationStore.close() leaves its connection field populated.
    # Actual deletion is the Windows-specific proof that the handle was closed.
    database.unlink()  # Raises PermissionError on Windows if a handle remains.
    assert not database.exists()
