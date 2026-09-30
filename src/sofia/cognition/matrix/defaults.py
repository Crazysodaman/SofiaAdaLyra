"""Default package-owned matrix evaluator registry."""
from __future__ import annotations

from .coordinator import MatrixRegistry


def default_matrix_registry() -> MatrixRegistry:
    """Resolve domain evaluators lazily to avoid package import cycles."""
    from sofia.authority.matrix import AuthorityMatrixEvaluator
    from sofia.avatar.matrix import AvatarMatrixEvaluator
    from sofia.emotion.matrix import EmotionMatrixEvaluator
    from sofia.environment.matrix import EnvironmentMatrixEvaluator
    from sofia.continuity.matrix import ContinuityMatrixEvaluator
    from sofia.interaction.matrix import InteractionMatrixEvaluator
    from sofia.machine.matrix import MachineMatrixEvaluator
    from sofia.memory.matrix import MemoryMatrixEvaluator
    from sofia.ops.matrix import OpsMatrixEvaluator
    from sofia.social.matrix import SocialMatrixEvaluator

    from .cognition_domain import CognitionMatrixEvaluator

    return MatrixRegistry(
        (
            SocialMatrixEvaluator(),
            EmotionMatrixEvaluator(),
            EnvironmentMatrixEvaluator(),
            ContinuityMatrixEvaluator(),
            AvatarMatrixEvaluator(),
            InteractionMatrixEvaluator(),
            MemoryMatrixEvaluator(),
            CognitionMatrixEvaluator(),
            MachineMatrixEvaluator(),
            OpsMatrixEvaluator(),
            AuthorityMatrixEvaluator(),
        )
    )
