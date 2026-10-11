"""CA-4105 immutable authenticated session audience vs cosmetic display names.

Written for deferred release acceptance; not executed in this coding pass.
"""
from contextlib import closing
import sqlite3

import pytest

from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite, CanonicalStateUnavailable


def principal(*, audience="local:text", name="Sparks", kind=AudienceKind.PRIVATE):
    return PrincipalContext(
        principal_id="owner:authenticated",
        audience_id=audience,
        audience_kind=kind,
        display_name=name,
    )


def test_renaming_owner_never_changes_authenticated_historical_binding(tmp_path):
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    store = SocialSessionStore(path)
    original = principal(name="Sparks")
    store.bind(session_id="immutable-history", principal=original)
    updated_display = principal(name="A different display label")
    assert store.bind(
        session_id="immutable-history", principal=updated_display,
    ) == updated_display
    persisted = store.get("immutable-history")
    assert persisted.principal_id == original.principal_id
    assert persisted.audience_id == original.audience_id
    assert persisted.display_name == "Sparks"


def test_same_principal_new_audience_never_rebinds_an_older_session(tmp_path):
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    store = SocialSessionStore(path)
    store.bind(session_id="old-local", principal=principal())
    with pytest.raises(PermissionError, match="another principal or audience"):
        store.bind(
            session_id="old-local",
            principal=principal(audience="mobile:private:second"),
        )
    with pytest.raises(PermissionError, match="another principal or audience"):
        store.bind(
            session_id="old-local",
            principal=principal(kind=AudienceKind.SHARED),
        )
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute(
            "SELECT audience_id,audience_kind FROM social_session_principal "
            "WHERE session_id='old-local'"
        ).fetchall()
    assert rows == [("local:text", "private")]


def test_social_binding_cannot_resurrect_deleted_canonical_state(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = SocialSessionStore(state)
    store.bind(session_id="saved-session", principal=principal())
    state.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.get("saved-session")
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.bind(session_id="new-session", principal=principal())
    assert not state.exists()


def test_social_binding_cannot_follow_replaced_canonical_state(tmp_path):
    import os

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = SocialSessionStore(state)
    store.bind(session_id="saved-session", principal=principal())
    replacement = tmp_path / "replacement.db"
    with closing(sqlite3.connect(replacement)) as db:
        db.execute("CREATE TABLE decoy (id INTEGER PRIMARY KEY)")
    os.replace(replacement, state)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.get("saved-session")
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.bind(session_id="new-session", principal=principal())
