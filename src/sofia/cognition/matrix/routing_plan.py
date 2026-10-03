"""Matrix-to-existing-dual-engine routing policy."""
from __future__ import annotations

import re

from .model import (
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    MatrixRoute,
    RoutingPlan,
    TurnEnvelope,
    TurnMatrix,
)


_VERIFY = re.compile(
    r"\b(?:verify|double[- ]check|confirm|are\s+you\s+sure|"
    r"check\s+your\s+answer)\b",
    re.IGNORECASE,
)


class MatrixRoutingPlanner:
    """Request a logical route while preserving the existing router."""

    def plan(self, envelope: TurnEnvelope, turn: TurnMatrix) -> RoutingPlan:
        if not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")

        if turn.ambiguous or _VERIFY.search(envelope.content):
            return RoutingPlan(
                MatrixRoute.VERIFY,
                "ambiguous or explicitly verification-oriented turn",
            )
        if turn.intent is MatrixIntent.ACTION_REQUEST:
            return RoutingPlan(
                MatrixRoute.VERIFY,
                "high-impact action planning receives dual-engine review",
            )
        if turn.intent is MatrixIntent.SOCIAL_CHECKIN:
            return RoutingPlan(
                MatrixRoute.STANDARD,
                "social self-expression is personality-critical and stays on the primary engine",
            )
        if (
            turn.relevance_for(MatrixDomain.EMOTION)
            is not MatrixRelevance.NONE
        ):
            return RoutingPlan(
                MatrixRoute.STANDARD,
                "emotion-grounded self-expression requires the primary personality path",
            )
        if (
            turn.relevance_for(MatrixDomain.SOCIAL)
            is not MatrixRelevance.NONE
        ):
            return RoutingPlan(
                MatrixRoute.STANDARD,
                "ordinary Sofía conversation stays on the primary personality path",
            )
        if (
            turn.relevance_for(MatrixDomain.INTERACTION)
            is MatrixRelevance.REQUIRED
        ):
            return RoutingPlan(
                MatrixRoute.STANDARD,
                "represented interaction requires primary grounded reasoning",
            )
        if (
            turn.relevance_for(MatrixDomain.MACHINE)
            is MatrixRelevance.REQUIRED
            or turn.relevance_for(MatrixDomain.OPS)
            is MatrixRelevance.REQUIRED
        ):
            return RoutingPlan(
                MatrixRoute.DEEP,
                "operational evidence turn requires primary deep reasoning",
            )
        if turn.intent is MatrixIntent.MEMORY_QUERY:
            return RoutingPlan(
                MatrixRoute.STANDARD,
                "memory-grounded response uses primary reasoning",
            )
        return RoutingPlan(
            MatrixRoute.AUTO,
            "existing cognitive router retains complexity-based routing",
        )
