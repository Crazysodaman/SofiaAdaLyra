"""PKG-UI presentation delivery state.

This module records planning and caller-reported presentation acknowledgements.
It does not authenticate a renderer, play audio, render an avatar, or prove
that an external delivery occurred.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PresentationChannel(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    AVATAR = "avatar"


class PresentationStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    REPORTED_ACKNOWLEDGED_UNVERIFIED = "reported_acknowledged_unverified"


@dataclass(frozen=True, slots=True)
class ExpressionDelivery:
    planned_channels: tuple[PresentationChannel, ...]
    acknowledged_channels: tuple[PresentationChannel, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.planned_channels, tuple):
            raise TypeError("planned_channels must be a tuple")
        if not isinstance(self.acknowledged_channels, tuple):
            raise TypeError("acknowledged_channels must be a tuple")
        if any(not isinstance(x, PresentationChannel) for x in self.planned_channels):
            raise ValueError("planned_channels contains an unknown channel")
        if any(not isinstance(x, PresentationChannel) for x in self.acknowledged_channels):
            raise ValueError("acknowledged_channels contains an unknown channel")
        if len(set(self.planned_channels)) != len(self.planned_channels):
            raise ValueError("planned_channels contains duplicates")
        if len(set(self.acknowledged_channels)) != len(self.acknowledged_channels):
            raise ValueError("acknowledged_channels contains duplicates")
        if not set(self.acknowledged_channels).issubset(self.planned_channels):
            raise ValueError("cannot acknowledge an unplanned presentation channel")

    def status(self, channel: PresentationChannel) -> PresentationStatus:
        if not isinstance(channel, PresentationChannel):
            raise TypeError("channel must be PresentationChannel")
        if channel in self.acknowledged_channels:
            return PresentationStatus.REPORTED_ACKNOWLEDGED_UNVERIFIED
        if channel in self.planned_channels:
            return PresentationStatus.PENDING
        return PresentationStatus.NOT_REQUESTED
