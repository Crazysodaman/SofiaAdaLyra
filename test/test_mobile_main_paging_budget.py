"""Deferred end-to-end regression for byte-bounded mobile Main history.

Exercises the real canonical conversation, audience binding and pagination.
Do not run until the owner opens the V18 verification campaign.
"""
import json

from test.test_mobile_main_history import _allow_private_main, _record, _setup


def test_large_history_replays_all_original_messages_with_bounded_pages(tmp_path):
    path, source, social, _, gateway = _setup(tmp_path)
    _allow_private_main(path)
    try:
        for number in range(1, 33):
            _record(
                source, social, gateway,
                private_mode=False,
                text=f"message-{number:02d}:" + ("m" * 11_000),
                number=number,
            )
        _record(
            source, social, gateway,
            private_mode=True, text="never-share:" + ("s" * 11_000),
            number=33,
        )

        seen = []
        before = None
        for _ in range(10):
            page = gateway.main_history(
                device_id="android-owner",
                private_mode=False,
                before=before,
                limit=30,
            )
            assert len(json.dumps(page).encode("utf-8")) < 256_000
            assert all("never-share" not in m["content"] for m in page["messages"])
            ids = [m["id"] for m in page["messages"]]
            assert not set(ids).intersection(seen)
            seen.extend(ids)
            if not page["has_more"]:
                break
            assert page["next_before"] is not None
            before = page["next_before"]
        else:
            raise AssertionError("Main keyset history did not terminate")

        assert len(seen) == 32
        assert len(set(seen)) == 32
        assert set(seen) == {f"source-{number}" for number in range(1, 33)}
    finally:
        source.close()
