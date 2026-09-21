"""PKG-ACT: pure delivery eligibility, never a message sender or worker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryIntent:
    channel: str
    recipient_id: str
    source_event_id: str
    recipient_opted_in: bool = False
    quiet_hours_active: bool = True
    muted: bool = False

    def __post_init__(self) -> None:
        for name in ('channel', 'recipient_id', 'source_event_id'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must be a nonempty string.')
        for name in ('recipient_opted_in', 'quiet_hours_active', 'muted'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be boolean.')

    @property
    def eligible_for_authorization(self) -> bool:
        """Only a precondition; no channel authentication or delivery authorization."""
        return self.recipient_opted_in and not self.quiet_hours_active and not self.muted
