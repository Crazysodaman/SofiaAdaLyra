"""Windows-sensitive disposable-probe cleanup; no real Ollama or production DB."""
from dataclasses import replace

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration


def test_disposable_probe_releases_all_runtime_database_connections(monkeypatch, tmp_path):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    monkeypatch.setenv('SOFIA_COGNITION_MODEL_AUTO_MANAGE', '0')
    monkeypatch.setattr(
        SofiaApplication,
        '_evaluate_contextual_presentation',
        lambda self, *, now, refresh_environment: None,
    )
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
        app.shutdown()
    assert app.conversation._conversation_store._connection is None
    assert app.runtime._memory_system._store._connection is None
    assert app.runtime._operational_store._closed is True
    assert app.runtime._filesystem_observation_store._connection is None
    # Actual deletion is the Windows-specific proof that every handle was closed.
    database.unlink()
    assert not database.exists()
