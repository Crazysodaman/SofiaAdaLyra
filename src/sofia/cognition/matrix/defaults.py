"""Default package-owned matrix evaluator registry."""
from __future__ import annotations

from sofia.authority.matrix import AuthorityMatrixEvaluator
from sofia.avatar.matrix import AvatarMatrixEvaluator
from sofia.emotion.matrix import EmotionMatrixEvaluator
from sofia.environment.matrix import EnvironmentMatrixEvaluator
from sofia.interaction.matrix import InteractionMatrixEvaluator
from sofia.machine.matrix import MachineMatrixEvaluator
from sofia.memory.matrix import MemoryMatrixEvaluator
from sofia.ops.matrix import OpsMatrixEvaluator
from sofia.social.matrix import SocialMatrixEvaluator

from .cognition_domain import CognitionMatrixEvaluator
from .coordinator import MatrixRegistry


def default_matrix_registry() -> MatrixRegistry:
    """Return one evaluator per domain, with domain packages owning semantics."""
    return MatrixRegistry(
        (
            SocialMatrixEvaluator(),
            EmotionMatrixEvaluator(),
            EnvironmentMatrixEvaluator(),
            AvatarMatrixEvaluator(),
            InteractionMatrixEvaluator(),
            MemoryMatrixEvaluator(),
            CognitionMatrixEvaluator(),
            MachineMatrixEvaluator(),
            OpsMatrixEvaluator(),
            AuthorityMatrixEvaluator(),
        )
    )
