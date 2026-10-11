"""Deferred authenticated mobile read epoch pinning and revocation checks.

All reads use local synthetic canonical SQLite and fake in-process adapters.
No HTTP transport, hardware, Android instrumentation or tests are run here.
"""
import pytest

from sofia.mobile.gateway import MobileCredentialRevoked
from test.test_mobile_main_history import _setup, _record


def _page(gateway, token):
    return gateway.dispatch_authenticated(
        credential=token, operation="/v1/mobile/main/page",
        payload={
            "device_id": "android-owner",
            "private_mode": False,
            "before": None,
            "limit": 10,
        },
    )


def test_rotating_during_main_read_preserves_original_audience_and_blocks_output(
    tmp_path, monkeypatch,
):
    path, source, social, app, gateway = _setup(tmp_path)
    try:
        old_token = gateway.credentials.enroll("android-owner")
        _record(
            source, social, gateway, private_mode=False,
            text="only generation one may see this source", number=1,
        )
        old_page = app.main_thread_page
        observed = []
        replacement_tokens = []

        def rotate_before_query(*, principal, before=None, limit=30):
            observed.append(principal.audience_id)
            replacement_tokens.append(
                gateway.credentials.enroll("android-owner", rotate=True)
            )
            return old_page(principal=principal, before=before, limit=limit)

        monkeypatch.setattr(app, "main_thread_page", rotate_before_query)
        with pytest.raises(
            MobileCredentialRevoked, match="before response publication",
        ):
            _page(gateway, old_token)

        assert len(observed) == 1
        assert not observed[0].endswith(":g2")
        monkeypatch.setattr(app, "main_thread_page", old_page)
        fresh = _page(gateway, replacement_tokens[0])
        assert fresh["messages"] == []
        assert fresh["audience_id"].endswith(":g2")
    finally:
        source.close()


def test_repeated_valid_main_read_preserves_source_and_epoch(
    tmp_path,
):
    _path, source, social, _app, gateway = _setup(tmp_path)
    try:
        token = gateway.credentials.enroll("android-owner")
        _record(
            source, social, gateway, private_mode=False,
            text="original unaltered source", number=2,
        )
        first = _page(gateway, token)
        second = _page(gateway, token)
        assert first["messages"] == second["messages"]
        assert [item["content"] for item in first["messages"]] == [
            "original unaltered source",
        ]
        assert not first["audience_id"].endswith(":g2")
    finally:
        source.close()
