import pytest

from sofia.ui.control_center import (
    DesktopControlSettings,
    RemoteChatMode,
)
from sofia.ui.remote_client import (
    RemoteEndpointRequired,
    RuntimeEndpoint,
    RuntimeEndpointSelector,
    RuntimeEndpointState,
)


def endpoint(host, epoch, state=RuntimeEndpointState.READY):
    return RuntimeEndpoint(host, f"https://{host}:7443", epoch, state)


def test_fleet_auto_follows_highest_ready_authority_epoch():
    settings = DesktopControlSettings(remote_chat_mode=RemoteChatMode.FLEET_AUTO)
    chosen = RuntimeEndpointSelector().choose(
        settings,
        local_endpoint=endpoint("venus", 4),
        fleet_endpoint=endpoint("artemis", 7),
    )
    assert chosen.host_id == "artemis"


def test_fleet_auto_falls_back_to_local_when_remote_not_ready():
    settings = DesktopControlSettings(remote_chat_mode=RemoteChatMode.FLEET_AUTO)
    chosen = RuntimeEndpointSelector().choose(
        settings,
        local_endpoint=endpoint("venus", 4),
        fleet_endpoint=endpoint("artemis", 7, RuntimeEndpointState.DEGRADED),
    )
    assert chosen.host_id == "venus"


def test_local_mode_never_silently_uses_remote_runtime():
    settings = DesktopControlSettings(remote_chat_mode=RemoteChatMode.LOCAL)
    with pytest.raises(RemoteEndpointRequired, match="local"):
        RuntimeEndpointSelector().choose(
            settings,
            local_endpoint=None,
            fleet_endpoint=endpoint("artemis", 7),
        )


def test_pinned_endpoint_requires_current_verified_match():
    settings = DesktopControlSettings(
        remote_chat_mode=RemoteChatMode.PINNED_ENDPOINT,
        pinned_chat_endpoint="https://terra:7443",
    )
    with pytest.raises(RemoteEndpointRequired, match="pinned"):
        RuntimeEndpointSelector().choose(
            settings,
            local_endpoint=endpoint("venus", 4),
            fleet_endpoint=endpoint("artemis", 7),
        )
