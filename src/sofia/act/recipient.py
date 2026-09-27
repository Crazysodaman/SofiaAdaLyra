"""Authenticated recipient binding for ACT delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.act.delivery import ActOutbox, BoundMessage
from sofia.social.principal import Audience, AuthenticatedPrincipal


@dataclass(frozen=True, slots=True)
class ActRecipient:
    principal: AuthenticatedPrincipal
    audience: Audience
    channel: str
    destination: str

    def __post_init__(self) -> None:
        if not isinstance(self.principal, AuthenticatedPrincipal):
            raise TypeError("principal must be AuthenticatedPrincipal")
        if not isinstance(self.audience, Audience):
            raise TypeError("audience must be Audience")
        if (
            self.audience.member_principal_ids
            and self.principal.principal_id
            not in self.audience.member_principal_ids
        ):
            raise ValueError("principal is not a member of the audience")
        if not isinstance(self.channel, str) or not self.channel.strip():
            raise ValueError("channel required")
        if not isinstance(self.destination, str) or not self.destination.strip():
            raise ValueError("destination required")


def bind_for_principal(
    outbox: ActOutbox,
    *,
    message_id: str,
    recipient: ActRecipient,
    expires_at: datetime,
    at: datetime,
) -> BoundMessage:
    """Bind ACT's existing immutable envelope to authenticated identity."""

    if not isinstance(outbox, ActOutbox):
        raise TypeError("ActOutbox required")
    if not isinstance(recipient, ActRecipient):
        raise TypeError("ActRecipient required")
    return outbox.bind(
        message_id=message_id,
        recipient_id=recipient.principal.principal_id,
        channel=recipient.channel,
        destination=recipient.destination,
        expires_at=expires_at,
        at=at,
    )
