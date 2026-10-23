"""The canonical SQLite URI builder must open local and UNC state safely.

On a network-hosted canonical state the legacy as_uri() connection path
failed with 'invalid uri authority'. The shared builder keeps the UNC
server inside the path portion; these tests pin the exact mappings and
prove real read-only connections on the host they run on.
"""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.state.sqlite_uri import sqlite_file_uri, sqlite_uri_from_posix


def test_sqlite_uri_exact_shape_for_posix_drive_and_unc_paths():
    assert sqlite_uri_from_posix("/tmp/Sofía state/sofia.db", read_only=True) == (
        "file:/tmp/Sof%C3%ADa%20state/sofia.db?mode=ro"
    )
    assert sqlite_uri_from_posix("H:/Users/Sofia state/sofia.db", read_only=True) == (
        "file:///H:/Users/Sofia%20state/sofia.db?mode=ro"
    )
    assert sqlite_uri_from_posix("//Artemis/Hestia/sofia.db", read_only=True) == (
        "file:////Artemis/Hestia/sofia.db?mode=ro"
    )


def test_sqlite_file_uri_accepts_paths_and_optional_modes():
    example = Path("//Artemis/Hestia/state.db")

    assert sqlite_file_uri(example) == "file:////Artemis/Hestia/state.db"
    assert sqlite_file_uri(example, read_only=True) == (
        "file:////Artemis/Hestia/state.db?mode=ro"
    )
    assert sqlite_file_uri(example, read_only=False) == (
        "file:////Artemis/Hestia/state.db?mode=rw"
    )

    local = Path("C:/Users/sofia/platform/state/db")

    assert sqlite_file_uri(local, read_only=True) == (
        "file:///C:/Users/sofia/platform/state/db?mode=ro"
    )

    with pytest.raises(TypeError):
        sqlite_file_uri(123)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        sqlite_uri_from_posix("//Artemis/Hestia/state.db", read_only="ro")


def test_local_sqlite_state_connects_with_the_shared_builder(tmp_path: Path):
    local = tmp_path / "local.db"

    bootstrap = sqlite3.connect(local)
    bootstrap.execute("CREATE TABLE unary (x)")
    bootstrap.execute("INSERT INTO unary VALUES (1)")
    bootstrap.commit()
    bootstrap.close()

    with closing(sqlite3.connect(
        sqlite_file_uri(local, read_only=True), uri=True, timeout=5,
    )) as db:
        assert db.execute("SELECT x FROM unary").fetchone() == (1,)


def _canonical_state_path() -> Path | None:
    try:
        from sofia.platform.config import production_state_path

        configured = production_state_path()
    except Exception:
        return None

    if configured.is_file():
        return configured

    return None


def test_configured_canonical_state_connects_with_the_shared_builder():
    canonical = _canonical_state_path()

    if canonical is None:
        pytest.skip(
            "No canonical production state file is present in this environment."
        )

    uri = sqlite_file_uri(canonical, read_only=True)
    read_only_marker = "?mode=ro"

    assert read_only_marker in uri
    assert uri.casefold().startswith("file:")

    with closing(sqlite3.connect(uri, uri=True, timeout=10)) as db:
        table_count = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]

    assert table_count > 0
