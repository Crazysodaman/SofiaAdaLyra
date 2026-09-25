"""Expression intents and acknowledgments, not fabricated body or voice output."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from sofia.interaction.registry import InteractionCatalog, EXPRESSION_DEFINITIONS

EXPRESSION_IDS = frozenset(item.id for item in EXPRESSION_DEFINITIONS)


@dataclass(frozen=True)
class ExpressionPlan:
    id: str
    source_id: str
    expression_id: str
    actor: Literal['sofia']
    channel: Literal['text', 'voice', 'avatar']
    intensity: str | None
    state: Literal['planned', 'described', 'executed', 'unsupported', 'blocked', 'silent', 'cancelled']
    acknowledgment_id: str | None = None


class ExpressionPlanner:
    """No inference from emotion labels; no real audio/animation capability."""

    def __init__(self, catalog: InteractionCatalog,
                 available_channels: frozenset[str] = frozenset({'text'})) -> None:
        if not isinstance(catalog, InteractionCatalog):
            raise TypeError('Validated catalog required.')
        if not available_channels.issubset({'text', 'voice', 'avatar'}):
            raise ValueError('Unknown channel.')
        self.catalog = catalog
        self.available_channels = available_channels

    def plan(self, *, plan_id: str, source_id: str, expression_id: str,
             channel: str = 'text', intensity: str | None = None,
             originating_contact: bool = False,
             contact_permitted: bool = False) -> ExpressionPlan:
        for value in (plan_id, source_id):
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ValueError('Bounded nonempty source and plan IDs required.')
        if expression_id not in EXPRESSION_IDS:
            raise ValueError('Unknown expression ID.')
        if channel not in ('text', 'voice', 'avatar'):
            raise ValueError('Unknown expression channel.')
        if intensity not in (None, 'subtle', 'moderate', 'strong'):
            raise ValueError('Unsupported intensity.')
        if not isinstance(originating_contact, bool) or not isinstance(contact_permitted, bool):
            raise TypeError('Contact gate must be explicit.')
        if expression_id == 'none':
            state = 'silent'
        elif originating_contact and not contact_permitted:
            state = 'blocked'
        elif channel not in self.available_channels:
            state = 'unsupported'
        else:
            state = 'planned'
        return ExpressionPlan(plan_id, source_id, expression_id, 'sofia',
                              channel, intensity, state)

    @staticmethod
    def acknowledge(plan: ExpressionPlan, *, receipt_id: str,
                    adapter_verified: bool = False,
                    contact_still_permitted: bool = True) -> ExpressionPlan:
        """Only actual consumer acknowledgement promotes an intent to output."""
        if not isinstance(plan, ExpressionPlan):
            raise TypeError('Expression plan required.')
        if plan.state != 'planned':
            raise ValueError('Only an unconsumed planned expression can be acknowledged.')
        if not contact_still_permitted:
            return replace(plan, state='blocked')
        if not isinstance(receipt_id, str) or not receipt_id.strip() or len(receipt_id) > 160:
            raise ValueError('A real consumer receipt ID is required.')
        if plan.channel != 'text' and adapter_verified is not True:
            raise ValueError('Only an authenticated rendering/audio adapter can confirm playback.')
        return replace(plan, state='described' if plan.channel == 'text' else 'executed',
                       acknowledgment_id=receipt_id)

    @staticmethod
    def cancel(plan: ExpressionPlan) -> ExpressionPlan:
        if not isinstance(plan, ExpressionPlan):
            raise TypeError('Expression plan required.')
        if plan.state != 'planned':
            return plan
        return replace(plan, state='cancelled')
