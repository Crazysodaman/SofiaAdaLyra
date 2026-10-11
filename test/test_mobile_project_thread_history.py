"""Deferred authenticated Android project-thread source privacy and paging.

No tests/CI run during coding. Project threads are canonical lifelong
threads; Android is deliberately a read-only presentation, not a writer.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from test.test_mobile_main_history import _setup, _allow_private_main

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _project(source, social, gateway, *, device, private, name, words):
    principal = gateway._principal(device, private_mode=private)
    thread_store = LifelongThreadStore(source.database_path)
    thread = thread_store.get_or_create(
        owner=principal, kind="project", name=name,
    )
    for i, word in enumerate(words):
        session = source.create_session()
        social.bind(session_id=session.id, principal=principal)
        original = ConversationMessage(
            id=str(uuid4()), session_id=session.id,
            role=ConversationRole.USER, content=word,
            created_at=NOW + timedelta(seconds=i),
        )
        source.save(original)
        thread_store.link_message(
            thread_id=thread.thread_id,
            source_message_id=original.id,
            principal=principal,
        )
    return thread


def _dispatch(gateway, token, path, *, private=False, **fields):
    return gateway.dispatch_authenticated(
        credential=token, operation=path,
        payload={"device_id": "android-owner", "private_mode": private, **fields},
    )


def test_android_can_page_canonical_project_without_other_audience_titles(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    _allow_private_main(path)
    token = gateway.credentials.enroll("android-owner")
    try:
        shared = _project(
            source, social, gateway, device="android-owner",
            private=False, name="Gaia robot",
            words=("Gaia source alpha", "Gaia source beta"),
        )
        private = _project(
            source, social, gateway, device="android-owner",
            private=True, name="Private work",
            words=("private project source",),
        )
        foreign = _project(
            source, social, gateway, device="android-other",
            private=False, name="Other device confidential",
            words=("other device secrets",),
        )

        standard = _dispatch(
            gateway, token, "/v1/mobile/threads", limit=30,
        )
        assert [x["name"] for x in standard["threads"] if x["kind"] == "project"] == [
            "Gaia robot"
        ]
        assert "Private work" not in str(standard)
        assert "Other device confidential" not in str(standard)

        first = _dispatch(
            gateway, token, "/v1/mobile/thread/page",
            thread_id=shared.thread_id, before=None, limit=1,
        )
        assert [x["content"] for x in first["messages"]] == ["Gaia source beta"]
        assert first["kind"] == "project"
        assert first["name"] == "Gaia robot"
        assert first["last_seen"] is None
        second = _dispatch(
            gateway, token, "/v1/mobile/thread/page",
            thread_id=shared.thread_id,
            before=first["next_before"], limit=1,
        )
        assert [x["content"] for x in second["messages"]] == [
            "Gaia source alpha"
        ]
        done = _dispatch(
            gateway, token, "/v1/mobile/thread/page",
            thread_id=shared.thread_id,
            before=second["next_before"], limit=1,
        )
        assert done["messages"] == []

        with pytest.raises(PermissionError):
            _dispatch(
                gateway, token, "/v1/mobile/thread/page",
                thread_id=private.thread_id, before=None, limit=30,
            )
        with pytest.raises(PermissionError):
            _dispatch(
                gateway, token, "/v1/mobile/thread/page",
                thread_id=foreign.thread_id, before=None, limit=30,
            )

        authorized_private = _dispatch(
            gateway, token, "/v1/mobile/threads",
            private=True, limit=30,
        )
        assert "Private work" in str(authorized_private)
        assert "Gaia robot" not in str(authorized_private)
    finally:
        source.close()


def test_mobile_project_history_only_accepts_exact_authenticated_route(tmp_path):
    path, source, social, app, gateway = _setup(tmp_path)
    token = gateway.credentials.enroll("android-owner")
    project = _project(
        source, social, gateway, device="android-owner",
        private=False, name="Model train layout", words=("HO-scale original",),
    )
    try:
        with pytest.raises(PermissionError):
            gateway.dispatch_authenticated(
                credential=token, operation="/v1/mobile/thread/page",
                payload={
                    "device_id": "android-other", "private_mode": False,
                    "thread_id": project.thread_id, "before": None, "limit": 1,
                },
            )
        with pytest.raises(ValueError, match="project page limit"):
            _dispatch(
                gateway, token, "/v1/mobile/thread/page",
                thread_id=project.thread_id, before=None, limit=True,
            )
        with pytest.raises(ValueError, match="cursor"):
            _dispatch(
                gateway, token, "/v1/mobile/thread/page",
                thread_id=project.thread_id, before={
                    "linked_at": "no-date", "message_id": "source"
                }, limit=1,
            )
        assert _dispatch(
            gateway, token, "/v1/mobile/thread/page",
            thread_id=project.thread_id, before=None, limit=1,
        )["messages"][0]["content"] == "HO-scale original"
    finally:
        source.close()
