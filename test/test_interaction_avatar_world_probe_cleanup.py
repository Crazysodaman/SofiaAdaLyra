"""Windows-sensitive disposable-probe cleanup; no real Ollama or production DB."""
from dataclasses import replace
import gc
from pathlib import Path
import sqlite3
import traceback

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.interaction.avatar_world_probe import _shutdown_disposable_app


def _open_sqlite_diagnostics(
    database: Path,
    origins: dict[int, str],
) -> tuple[str, ...]:
    target = str(database.resolve()).casefold()
    diagnostics: list[str] = []
    for candidate in gc.get_objects():
        if not isinstance(candidate, sqlite3.Connection):
            continue
        try:
            rows = candidate.execute("PRAGMA database_list").fetchall()
        except (sqlite3.Error, ReferenceError):
            continue
        paths = tuple(str(row[2]) for row in rows if len(row) >= 3 and row[2])
        if not any(path.casefold() == target for path in paths):
            continue
        referrers: list[str] = []
        for referrer in gc.get_referrers(candidate):
            if isinstance(referrer, dict):
                keys = [
                    str(key)
                    for key, value in referrer.items()
                    if value is candidate
                ]
                if keys:
                    referrers.append("dict:" + ",".join(sorted(keys)))
            else:
                referrers.append(
                    f"{type(referrer).__module__}.{type(referrer).__qualname__}"
                )
        diagnostics.append(
            "open sqlite connection "
            f"paths={paths!r} referrers={tuple(referrers)!r} "
            f"origin={origins.get(id(candidate), '<unknown>')}"
        )
    return tuple(diagnostics)


def test_disposable_probe_releases_all_runtime_database_connections(monkeypatch, tmp_path):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    monkeypatch.setattr(
        OllamaProvider, '_respond_once',
        lambda self, request: CognitiveResponse(content='Isolated test response.'),
    )
    origins: dict[int, str] = {}
    original_connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        frames = [
            frame
            for frame in traceback.extract_stack(limit=18)
            if "sofia" in frame.filename.casefold()
        ]
        origins[id(connection)] = " > ".join(
            f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
            for frame in frames[-8:]
        )
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
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
    assert app.runtime._filesystem_observation_store._connection is None
    diagnostics = _open_sqlite_diagnostics(database, origins)
    assert diagnostics == (), "\n".join(diagnostics)
    # Actual deletion is the Windows-specific proof that every handle was closed.
    database.unlink()  # Raises PermissionError on Windows if a handle remains.
    assert not database.exists()
