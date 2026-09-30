"""Build provider-context policy from a classified turn matrix."""
from __future__ import annotations

from .model import (
    ContextPlan,
    HistoryPolicy,
    MatrixDomain,
    MatrixRelevance,
    TurnMatrix,
)


_HISTORY_LIMITS = {
    HistoryPolicy.NONE: 1,
    HistoryPolicy.LAST_TURN: 3,
    HistoryPolicy.TOPIC_WINDOW: 8,
    HistoryPolicy.BOUNDED_RECENT: 12,
    HistoryPolicy.RETRIEVE_SPECIFIC: 1,
}


class MatrixContextPlanner:
    """Translate relevance into an explicit provider-context plan.

    Identity, Constitution and baseline personality remain runtime invariants.
    This plan controls turn-specific domain projection and transcript history.
    """

    def plan(self, turn: TurnMatrix) -> ContextPlan:
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")

        included = tuple(
            contribution.domain
            for contribution in turn.domains
            if contribution.relevance is not MatrixRelevance.NONE
        )
        included_set = set(included)
        excluded = tuple(
            domain
            for domain in MatrixDomain
            if domain not in included_set
        )
        return ContextPlan(
            included_domains=included,
            excluded_domains=excluded,
            history_policy=turn.history_policy,
            max_history_messages=_HISTORY_LIMITS[turn.history_policy],
        )
