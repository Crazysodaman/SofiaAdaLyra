from pathlib import Path

import pytest

from sofia.ui.remote_transport import (
    RemoteChatClientConfig,
    RemoteChatServerConfig,
)


@pytest.mark.parametrize("bad", ["A" * 64, "g" * 64, "a" * 63, "", None])
def test_remote_chat_client_rejects_noncanonical_server_pin(bad):
    with pytest.raises((TypeError, ValueError)):
        RemoteChatClientConfig(
            "artemis",
            7443,
            Path("ca.pem"),
            Path("client.pem"),
            Path("client.key"),
            bad,
        )


@pytest.mark.parametrize("bad", ["B" * 64, "z" * 64, "b" * 65])
def test_remote_chat_server_rejects_noncanonical_client_pin(bad):
    with pytest.raises(ValueError):
        RemoteChatServerConfig(
            "0.0.0.0",
            7443,
            Path("server.pem"),
            Path("server.key"),
            Path("ca.pem"),
            bad,
            Path("ledger.db"),
        )
