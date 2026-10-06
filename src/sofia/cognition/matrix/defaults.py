"""Default package-owned matrix evaluator registry."""
from __future__ import annotations

from .coordinator import MatrixRegistry
import re
from .model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_MODEL = re.compile(
    r"\b(?:llm|model|ollama|primary|secondary|routing|cognition|"
    r"matrix|matrixes|matrices|matrixs)\b",
    re.IGNORECASE,
)


class CognitionMatrixEvaluator:
    domain = MatrixDomain.COGNITION

    def evaluate(self, envelope, turn):
        if _MODEL.search(envelope.content):
            return DomainContribution(
                self.domain,
                (
                    MatrixRelevance.REQUIRED
                    if turn.intent in {
                        MatrixIntent.OPERATIONAL_QUERY,
                        MatrixIntent.ACTION_REQUEST,
                    }
                    else MatrixRelevance.RELEVANT
                ),
                "COGNITION owns Sofía model/routing/matrix architecture context",
            )
        return None


def default_matrix_registry() -> MatrixRegistry:
    """Resolve domain evaluators lazily to avoid package import cycles."""
    from sofia.authority.matrix import AuthorityMatrixEvaluator
    from sofia.avatar.matrix import AvatarMatrixEvaluator
    from sofia.emotion.matrix import EmotionMatrixEvaluator
    from sofia.environment.matrix import EnvironmentMatrixEvaluator
    from sofia.continuity.matrix import ContinuityMatrixEvaluator
    from sofia.interaction.matrix import InteractionMatrixEvaluator
    from sofia.voice.matrix import VoiceMatrixEvaluator
    from sofia.machine.matrix import MachineMatrixEvaluator
    from sofia.memory.matrix import MemoryMatrixEvaluator
    from sofia.rel.matrix import RelationshipMatrixEvaluator
    from sofia.habits.matrix import HabitMatrixEvaluator
    from sofia.dev.matrix import DevMatrixEvaluator
    from sofia.knowledge.matrix import KnowledgeMatrixEvaluator
    from sofia.integrate.matrix import IntegrateMatrixEvaluator
    from sofia.body.matrix import BodyMatrixEvaluator
    from sofia.ops.matrix import OpsMatrixEvaluator
    from sofia.social.matrix import SocialMatrixEvaluator
    from sofia.goals.matrix import GoalMatrixEvaluator


    return MatrixRegistry(
        (
            SocialMatrixEvaluator(),
            EmotionMatrixEvaluator(),
            EnvironmentMatrixEvaluator(),
            ContinuityMatrixEvaluator(),
            AvatarMatrixEvaluator(),
            InteractionMatrixEvaluator(),
            VoiceMatrixEvaluator(),
            MemoryMatrixEvaluator(),
            RelationshipMatrixEvaluator(),
            HabitMatrixEvaluator(),
            DevMatrixEvaluator(),
            KnowledgeMatrixEvaluator(),
            IntegrateMatrixEvaluator(),
            BodyMatrixEvaluator(),
            CognitionMatrixEvaluator(),
            MachineMatrixEvaluator(),
            OpsMatrixEvaluator(),
            GoalMatrixEvaluator(),
            AuthorityMatrixEvaluator(),
        )
    )
