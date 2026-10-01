"""Deferred runtime-mobility endpoint selection.

This module is retained for roadmap step #10 redundancy/fencing/runtime mobility
experiments. It is not part of the live desktop composition: current production
desktop chat is bound to the one canonical local state database.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .control_center import DesktopControlSettings, RemoteChatMode


class RuntimeEndpointState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuntimeEndpoint:
    host_id: str
    endpoint: str
    authority_epoch: int
    state: RuntimeEndpointState

    def __post_init__(self) -> None:
        if not self.host_id.strip() or not self.endpoint.strip():
            raise ValueError("runtime endpoint host and address required")
        if type(self.authority_epoch) is not int or self.authority_epoch < 0:
            raise ValueError("authority_epoch must be nonnegative")
        if not isinstance(self.state, RuntimeEndpointState):
            raise TypeError("RuntimeEndpointState required")


class RemoteEndpointRequired(RuntimeError):
    pass


class RuntimeEndpointSelector:
    """Select local, Fleet-authoritative, or explicitly pinned chat routing."""

    def choose(
        self,
        settings: DesktopControlSettings,
        *,
        local_endpoint: RuntimeEndpoint | None,
        fleet_endpoint: RuntimeEndpoint | None,
    ) -> RuntimeEndpoint:
        if not isinstance(settings, DesktopControlSettings):
            raise TypeError("DesktopControlSettings required")

        if settings.remote_chat_mode is RemoteChatMode.LOCAL:
            if local_endpoint is None:
                raise RemoteEndpointRequired("local Sofía runtime is unavailable")
            return local_endpoint

        if settings.remote_chat_mode is RemoteChatMode.PINNED_ENDPOINT:
            assert settings.pinned_chat_endpoint is not None
            if fleet_endpoint is not None and fleet_endpoint.endpoint == settings.pinned_chat_endpoint:
                return fleet_endpoint
            if local_endpoint is not None and local_endpoint.endpoint == settings.pinned_chat_endpoint:
                return local_endpoint
            raise RemoteEndpointRequired("pinned Sofía endpoint is not currently verified")

        candidates = tuple(
            value
            for value in (fleet_endpoint, local_endpoint)
            if value is not None and value.state is RuntimeEndpointState.READY
        )
        if not candidates:
            raise RemoteEndpointRequired("no verified ready Sofía runtime endpoint is available")
        return max(candidates, key=lambda value: (value.authority_epoch, value.host_id))
