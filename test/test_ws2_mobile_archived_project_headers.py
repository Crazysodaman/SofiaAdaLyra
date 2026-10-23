"""Deferred Android project archive selection and withdrawn-source privacy.

Synthetic authenticated pairing and canonical SQLite only. No real phone,
host deployment, source deletion, or test execution.
"""
import sqlite3

import pytest

from sofia.core.conversation.lifelong import LifelongThreadStore
from test.test_mobile_project_thread_history import _project, _dispatch
from test.test_mobile_main_history import _setup


def test_mobile_archive_listing_stays_original_audience_scoped(tmp_path):
    _path, originals, social, _app, gateway = _setup(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    principal = gateway._principal("android-owner", private_mode=False)
    try:
        archived = _project(
            originals, social, gateway, device="android-owner",
            private=False, name="Historical Gaia Work",
            words=("original retained data",),
        )
        private = _project(
            originals, social, gateway, device="android-other",
            private=False, name="Other device project",
            words=("never visible here",),
        )
        store = LifelongThreadStore(originals.database_path)
        store.set_project_archived(
            principal=principal, thread_id=archived.thread_id, archived=True,
        )
        default = _dispatch(
            gateway, bearer, "/v1/mobile/threads", limit=30,
        )
        assert default["include_archived"] is False
        assert archived.thread_id not in {t["thread_id"] for t in default["threads"]}
        included = _dispatch(
            gateway, bearer, "/v1/mobile/threads", limit=30,
            include_archived=True,
        )
        assert included["include_archived"] is True
        rows = {
            t["thread_id"]: t for t in included["threads"] if t["kind"] == "project"
        }
        assert rows[archived.thread_id]["archived"] is True
        assert private.thread_id not in rows

        with pytest.raises(TypeError, match="include_archived"):
            _dispatch(
                gateway, bearer, "/v1/mobile/threads", limit=30,
                include_archived="true",
            )
    finally:
        originals.close()


def test_withdrawing_all_source_links_never_resurrects_former_title(
    tmp_path,
):
    path, originals, social, _app, gateway = _setup(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    try:
        project = _project(
            originals, social, gateway, device="android-owner",
            private=False, name="Withdrawn Project", words=("previous source",),
        )
        with sqlite3.connect(path) as db:
            assert db.execute(
                "SELECT has_linked_source FROM lifelong_thread WHERE thread_id=?",
                (project.thread_id,),
            ).fetchone() == (1,)
            db.execute(
                "DELETE FROM lifelong_thread_event WHERE thread_id=?",
                (project.thread_id,),
            )
        included = _dispatch(
            gateway, bearer, "/v1/mobile/threads", limit=30,
            include_archived=True,
        )
        assert project.thread_id not in {
            row["thread_id"] for row in included["threads"]
        }
        assert "Withdrawn Project" not in str(included)
        with pytest.raises(PermissionError, match="no visible originals"):
            gateway.project_thread_history(
                device_id="android-owner", private_mode=False,
                thread_id=project.thread_id, limit=30,
            )
    finally:
        originals.close()


def test_new_empty_project_has_audience_but_no_exposed_originals(tmp_path):
    _path, originals, _social, _app, gateway = _setup(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    principal = gateway._principal("android-owner", private_mode=False)
    try:
        store = LifelongThreadStore(originals.database_path)
        created = store.get_or_create(
            owner=principal, kind="project", name="New Local Project",
        )
        result = _dispatch(
            gateway, bearer, "/v1/mobile/threads", limit=30,
        )
        assert any(
            x["thread_id"] == created.thread_id and x["archived"] is False
            for x in result["threads"]
        )
        assert gateway.project_thread_history(
            device_id="android-owner", private_mode=False,
            thread_id=created.thread_id, limit=30,
        )["messages"] == []
    finally:
        originals.close()
