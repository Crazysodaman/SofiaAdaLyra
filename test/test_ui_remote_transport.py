from pathlib import Path
from uuid import uuid4

import pytest

from sofia.ui.remote_transport import (
    PinnedRemoteConversation,
    RemoteChatClientConfig,
    RemoteChatLedger,
    RemoteChatOutcomeUnknown,
)


def test_remote_chat_ledger_dedupes_exact_request_and_rejects_changed_content(tmp_path):
    ledger=RemoteChatLedger(tmp_path/"remote-chat.db")
    request_id=uuid4()
    assert ledger.reserve(request_id,"hello") is None
    ledger.finish(request_id,"hi")
    assert ledger.reserve(request_id,"hello")==("final","hi")
    with pytest.raises(PermissionError,match="different"):
        ledger.reserve(request_id,"different")


def test_remote_chat_ledger_marks_uncertain_generation(tmp_path):
    ledger=RemoteChatLedger(tmp_path/"remote-chat.db")
    request_id=uuid4()
    ledger.reserve(request_id,"hello")
    ledger.mark_unknown(request_id,"ProviderTimeout")
    state,response=ledger.reserve(request_id,"hello")
    assert state=="outcome_unknown"
    assert response is None


def test_remote_client_config_requires_https_endpoint(tmp_path):
    with pytest.raises(ValueError,match="https"):
        RemoteChatClientConfig.from_endpoint(
            "http://artemis:7443",
            ca_file=tmp_path/"ca.pem",
            client_certificate=tmp_path/"client.pem",
            client_private_key=tmp_path/"client.key",
            expected_server_public_key_sha256="a"*64,
        )


def test_remote_conversation_returns_cognitive_response_without_local_runtime():
    config=RemoteChatClientConfig(
        "artemis",7443,Path("ca"),Path("cert"),Path("key"),"a"*64
    )
    conversation=PinnedRemoteConversation(config)
    conversation._request=lambda method,path,payload=None: {
        "request_id":str(uuid4()),"outcome":"final","content":"remote hello"
    }
    assert conversation.respond("hello").content=="remote hello"


def test_remote_conversation_does_not_auto_retry_uncertain_send():
    config=RemoteChatClientConfig(
        "artemis",7443,Path("ca"),Path("cert"),Path("key"),"a"*64
    )
    conversation=PinnedRemoteConversation(config)
    def fail(*args,**kwargs):
        raise OSError("connection reset")
    conversation._request=fail
    with pytest.raises(RemoteChatOutcomeUnknown) as error:
        conversation.respond("hello")
    assert error.value.request_id is not None
