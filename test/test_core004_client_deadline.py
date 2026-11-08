"""CORE-004: desktop timeout is an uncertain durable turn, never a retry.

Scripted transport failure emulates a lost HTTPS response after dispatch.
No production connections, model, Core database or Discord channel are used.
"""
from datetime import timedelta

import pytest

from sofia.modules.ui.core_link_desktop import (
    CoreLinkDesktopClient, CoreLinkDesktopStateStore, RemoteTurnUncertain,
)
from sofia.platform.core_link import CoreLinkTransportError
from sofia.sdk import CoreLinkResponseStatus
from test.test_core_link_desktop import (
    NOW, ScriptedTransport, binding, response_script_for_start,
)


class DropSendResponse(ScriptedTransport):
    def request(self, request):
        if request.operation == "conversation.send":
            self.requests.append(request)
            raise CoreLinkTransportError("simulated HTTPS receive timeout after POST")
        return super().request(request)


def test_core004_timeout_preserves_key_and_never_blindly_resends(tmp_path):
    selected = binding()
    path = (tmp_path / "timeout-state.json").resolve()
    first_transport = DropSendResponse(response_script_for_start())
    client = CoreLinkDesktopClient(
        first_transport, selected, CoreLinkDesktopStateStore(path, selected),
        clock=lambda: NOW,
    )
    assert client.start() == ()
    with pytest.raises(RemoteTurnUncertain, match="transport loss"):
        client.send("One ambiguous but durable turn")
    pending = CoreLinkDesktopStateStore(path, selected).load()
    key = pending.pending_idempotency_key
    assert key is not None
    assert pending.pending_content == "One ambiguous but durable turn"
    assert pending.draft == "One ambiguous but durable turn"
    assert [r.operation for r in first_transport.requests].count("conversation.send") == 1
    with pytest.raises(RemoteTurnUncertain, match="not been reconciled"):
        client.send("Potentially duplicated text")
    assert [r.operation for r in first_transport.requests].count("conversation.send") == 1

    second_transport = ScriptedTransport([
        ("status", CoreLinkResponseStatus.COMPLETED, {
            "remote_platform_id": "platform:canonical",
            "remote_core_identity_id": "core:sofia",
            "remote_core_generation": 9,
            "protocol": "1.0", "state": "ready",
            "operator_stop_active": False,
        }),
        ("conversation.select", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote",
        }),
        ("conversation.result", CoreLinkResponseStatus.COMPLETED, {
            "event_id": "event:settled", "state": "completed",
            "content": "Recovered one result", "canonical_sequence": 1,
        }),
        ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote",
            "messages": [
                {"message_id": "received:1", "role": "user",
                 "content": "One ambiguous but durable turn",
                 "created_at": NOW.isoformat()},
                {"message_id": "received:2", "role": "assistant",
                 "content": "Recovered one result",
                 "created_at": (NOW + timedelta(seconds=1)).isoformat()},
            ],
            "next_cursor": None,
        }),
    ])
    restarted = CoreLinkDesktopClient(
        second_transport, selected, CoreLinkDesktopStateStore(path, selected),
        clock=lambda: NOW,
    )
    history = restarted.start()
    assert [item.content for item in history] == [
        "One ambiguous but durable turn", "Recovered one result",
    ]
    assert not any(r.operation == "conversation.send" for r in second_transport.requests)
    result_requests = [r for r in second_transport.requests if r.operation == "conversation.result"]
    assert len(result_requests) == 1
    assert result_requests[0].payload == {"idempotency_key": key}
    assert CoreLinkDesktopStateStore(path, selected).load().pending_idempotency_key is None
