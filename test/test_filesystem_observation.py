from pathlib import Path

from sofia.filesystem.observation import (
    FilesystemObservationStore,
    FilesystemObserver,
)


def test_observer_records_files_and_ignores_runtime_directories(
    tmp_path: Path,
):
    source = tmp_path / "source.py"
    source.write_text(
        "print('hello')",
        encoding="utf-8",
    )

    ignored = tmp_path / "__pycache__"
    ignored.mkdir()

    ignored_file = ignored / "cache.pyc"
    ignored_file.write_bytes(
        b"ignored"
    )

    observer = FilesystemObserver(
        root=tmp_path,
    )

    observation = observer.observe()

    paths = {
        entry.path
        for entry in observation.entries
    }

    assert source in paths
    assert ignored_file not in paths


def test_observation_store_persists_snapshot(
    tmp_path: Path,
):
    state_path = tmp_path / "state.db"

    source = tmp_path / "source.py"
    source.write_text(
        "print('hello')",
        encoding="utf-8",
    )

    observer = FilesystemObserver(
        root=tmp_path,
    )

    observation = observer.observe()

    store = FilesystemObservationStore(
        state_path
    )

    store.record(observation)

    restored = store.latest(tmp_path)

    assert restored is not None
    assert restored.root == tmp_path.resolve()
    assert len(restored.entries) == len(
        observation.entries
    )

    restored_paths = {
        entry.path
        for entry in restored.entries
    }

    assert source.resolve() in restored_paths

    store.close()