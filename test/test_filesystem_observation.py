import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sofia.platform.filesystem.observation import (
    FilesystemObservationStore,
    FilesystemObserver,
)

pytestmark = [pytest.mark.pkg_dev]


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


def _reference_legacy_signatures(root: Path) -> list[tuple[str, int, str]]:
    """Replicates the shipped legacy observation order and bounds exactly."""
    signatures: list[tuple[str, int, str]] = []

    for path in sorted(
        root.rglob("*"),
        key=lambda path: str(path).casefold(),
    ):
        if len(signatures) >= FilesystemObserver.MAX_FILES:
            break

        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(
            part in FilesystemObserver._IGNORED_PARTS
            for part in relative.parts
        ):
            continue

        try:
            stat = path.stat()
        except OSError:
            continue

        if stat.st_size > FilesystemObserver.MAX_FILE_BYTES:
            continue

        signatures.append((
            str(relative),
            stat.st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ))

    return signatures


def test_observation_matches_reference_walk_in_casefold_order(tmp_path: Path):
    root = tmp_path / "observed"

    deep = root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "payload.txt").write_text("deep", encoding="utf-8")

    (root / "S.TXT").write_text("upper", encoding="utf-8")
    (root / "s.txt").write_text("present", encoding="utf-8")
    (root / "b_sub.txt").write_text("flat", encoding="utf-8")

    b_sub = root / "b_sub"
    b_sub.mkdir()
    (b_sub / "b_obs.txt").write_text("nested", encoding="utf-8")

    state = root / "state"
    state.mkdir()
    (state / "state_only.txt").write_text("stash", encoding="utf-8")

    versions = root / "state_reports"
    versions.mkdir()
    (versions / "state_summary.md").write_text("summary", encoding="utf-8")
    (root / "state_reports" / "state").write_text("nested file name", encoding="utf-8")

    pycache = root / "a" / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.pyc").write_bytes(b"ignore me")

    venv = root / ".venv" / "site-pkgs"
    venv.mkdir(parents=True)
    (venv / "dist-site.py").write_text("skip", encoding="utf-8")

    git = root / ".git"
    git.mkdir()
    (git / "packed-refs").write_text("skip", encoding="utf-8")

    node = root / "node_modules" / "some-package" / "snap"
    node.mkdir(parents=True)
    (node / "c.pyc").write_bytes(b"skip me")

    oversized = root / "a" / "max_size.txt"
    oversized.write_bytes(b"\x00" * (FilesystemObserver.MAX_FILE_BYTES + 1))

    exact = root / "a" / "exact_size.txt"
    exact.write_bytes(b"\x01" * FilesystemObserver.MAX_FILE_BYTES)

    observation = FilesystemObserver(root).observe()

    reference = _reference_legacy_signatures(root)
    actual = [(
        str(entry.path.relative_to(root)),
        entry.size_bytes,
        entry.content_hash,
    ) for entry in observation.entries]

    assert [item[0] for item in actual] == [item[0] for item in reference]
    assert actual == reference


def test_observation_cap_truncates_exactly_at_max_files_casefold_prefix(tmp_path: Path):
    root = tmp_path / "cap"
    root.mkdir()

    for index in range(1010):
        leaf = (root / f"F{index:04d}.txt")
        leaf.write_text(f"file {index}", encoding="utf-8")

    observation = FilesystemObserver(root).observe()

    assert len(observation.entries) == FilesystemObserver.MAX_FILES

    relative_names = [
        entry.path.relative_to(root).as_posix()
        for entry in observation.entries
    ]

    limit = FilesystemObserver.MAX_FILES

    assert relative_names == [
        f"F{index:04d}.txt" for index in range(limit)
    ]


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Directory-junction cycles are a Windows-specific reparse behavior.",
)
def test_self_referential_junction_tree_terminates_at_bounded_scope(
    tmp_path: Path,
):
    root = tmp_path / "bounded"
    root.mkdir()

    (root / "a.txt").write_text("plain anchor", encoding="utf-8")
    loop = root / "loop"

    link_result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(loop), str(root)],
        capture_output=True,
        check=False,
        text=True,
    )

    if not loop.is_dir():
        pytest.skip(f"mklink unavailable in this environment: {link_result.stderr}")

    observation = FilesystemObserver(root).observe()

    relative_names = sorted(
        entry.path.relative_to(root).as_posix()
        for entry in observation.entries
    )

    assert relative_names == ["a.txt"]
