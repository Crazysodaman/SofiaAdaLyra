"""CORE-004: long-session desktop history and cursor/replay regressions.

Scripted Core-free SDK responses isolate the desktop projection. No personal
Core DB, Ollama instance, remote network or Discord channel is accessed.
"""
from datetime import timedelta

import pytest

from sofia.modules.ui.core_link_desktop import CoreLinkDesktopClient, CoreLinkDesktopStateStore
from sofia.sdk import CoreLinkResponseStatus
from test.test_core_link_desktop import NOW, ScriptedTransport, binding, response_script_for_start


def page_item(index: int) -> dict[str, str]:
    return {
        "message_id": f"message:{index:04d}",
        "role": "user" if index % 2 == 0 else "assistant",
        "content": f"Turn part {index}",
        "created_at": (NOW + timedelta(seconds=index)).isoformat(),
    }


def test_core004_desktop_shows_newest_after_more_than_one_history_page(tmp_path):
    first = [page_item(i) for i in range(100)]
    second = [page_item(i) for i in range(100, 105)]
    first_cursor = {
        "created_at": first[-1]["created_at"],
        "message_id": first[-1]["message_id"],
    }
    script = response_script_for_start()
    script[-1] = ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
        "session_id": "session:remote", "messages": first,
        "next_cursor": first_cursor,
    })
    script.append(("conversation.history", CoreLinkResponseStatus.COMPLETED, {
        "session_id": "session:remote", "messages": second,
        "next_cursor": {
            "created_at": second[-1]["created_at"],
            "message_id": second[-1]["message_id"],
        },
    }))
    transport = ScriptedTransport(script)
    selected = binding()
    client = CoreLinkDesktopClient(
        transport, selected,
        CoreLinkDesktopStateStore((tmp_path / "paged-desktop.json").resolve(), selected),
        clock=lambda: NOW,
    )
    messages = client.start()
    assert len(messages) == 100
    assert messages[0].message_id == "message:0005"
    assert messages[-1].message_id == "message:0104"
    history_requests = [
        req for req in transport.requests if req.operation == "conversation.history"
    ]
    assert len(history_requests) == 2
    assert history_requests[0].payload["after"] is None
    assert history_requests[1].payload["after"] == first_cursor


@pytest.mark.parametrize("invalid_kind", ["duplicate_message", "nonadvancing_cursor"])
def test_core004_desktop_rejects_history_page_replay_and_preserves_projection(
    tmp_path, invalid_kind,
):
    first = [page_item(i) for i in range(100)]
    cursor = {
        "created_at": first[-1]["created_at"],
        "message_id": first[-1]["message_id"],
    }
    script = response_script_for_start()
    if invalid_kind == "nonadvancing_cursor":
        script[-1] = ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote", "messages": first,
            "next_cursor": {"created_at": NOW.isoformat(), "message_id": "message:0000"},
        })
    else:
        script[-1] = ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote", "messages": first,
            "next_cursor": cursor,
        })
        script.append(("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote", "messages": [first[-1]],
            "next_cursor": cursor,
        }))
    transport = ScriptedTransport(script)
    selected = binding()
    client = CoreLinkDesktopClient(
        transport, selected,
        CoreLinkDesktopStateStore((tmp_path / "replay-desktop.json").resolve(), selected),
        clock=lambda: NOW,
    )
    with pytest.raises(RuntimeError, match="(history ordering/replay|history cursor|history payload|history item)"):
        client.start()
    assert client.messages == (), "never publish a partially verified history"
