from pathlib import Path

import pytest

from sofia.ui.drafts import UIDraftStore


def test_draft_persists_across_store_instances(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"

    first = UIDraftStore(database_path)
    saved = first.save(
        client_id="desktop",
        session_id="session-1",
        content="unfinished question",
    )
    assert saved is not None
    first.close()

    second = UIDraftStore(database_path)
    loaded = second.load(
        client_id="desktop",
        session_id="session-1",
    )

    assert loaded is not None
    assert loaded.content == "unfinished question"
    second.close()


def test_drafts_are_scoped_by_client_and_session(
    tmp_path: Path,
):
    store = UIDraftStore(tmp_path / "sofia.db")
    store.save(
        client_id="desktop",
        session_id="one",
        content="desktop one",
    )
    store.save(
        client_id="mobile",
        session_id="one",
        content="mobile one",
    )
    store.save(
        client_id="desktop",
        session_id="two",
        content="desktop two",
    )

    assert store.load(
        client_id="desktop",
        session_id="one",
    ).content == "desktop one"
    assert store.load(
        client_id="mobile",
        session_id="one",
    ).content == "mobile one"
    assert store.load(
        client_id="desktop",
        session_id="two",
    ).content == "desktop two"

    store.close()


def test_empty_draft_clears_existing_state(
    tmp_path: Path,
):
    store = UIDraftStore(tmp_path / "sofia.db")
    store.save(
        client_id="desktop",
        session_id="session",
        content="draft",
    )

    result = store.save(
        client_id="desktop",
        session_id="session",
        content="",
    )

    assert result is None
    assert store.load(
        client_id="desktop",
        session_id="session",
    ) is None
    store.close()


def test_closed_draft_store_fails_closed(
    tmp_path: Path,
):
    store = UIDraftStore(tmp_path / "sofia.db")
    store.close()

    with pytest.raises(RuntimeError):
        store.load(
            client_id="desktop",
            session_id="session",
        )


def test_draft_rejects_invalid_identifiers(
    tmp_path: Path,
):
    store = UIDraftStore(tmp_path / "sofia.db")

    with pytest.raises(ValueError):
        store.save(
            client_id="",
            session_id="session",
            content="draft",
        )

    with pytest.raises(ValueError):
        store.load(
            client_id="desktop",
            session_id="",
        )

    store.close()
