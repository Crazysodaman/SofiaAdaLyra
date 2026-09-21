"""PKG-UI: distinguish planned channels from reported render acknowledgments.

Caller-supplied receipts are NOT authenticated here; no device is controlled.
"""
from __future__ import annotations

from dataclasses import dataclass


_CHANNELS = frozenset({'text', 'voice', 'avatar'})


@dataclass(frozen=True)
class ExpressionDelivery:
    planned_channels: tuple[str, ...]
    acknowledged_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ('planned_channels', 'acknowledged_channels'):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(value not in _CHANNELS for value in values):
                raise ValueError(f'{name} must contain recognized channels.')
            if len(set(values)) != len(values):
                raise ValueError('Duplicate channels are not valid.')
        if not set(self.acknowledged_channels).issubset(self.planned_channels):
            raise ValueError('Cannot acknowledge an unplanned expression.')

    def status(self, channel: str) -> str:
        if channel not in _CHANNELS:
            raise ValueError('Unknown expression channel.')
        if channel in self.acknowledged_channels:
            return 'reported_acknowledged_unverified'
        return 'pending' if channel in self.planned_channels else 'not_requested'
