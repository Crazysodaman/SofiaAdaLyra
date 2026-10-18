"""Evidence-grounded generalization evaluation without execution authority."""

from .contracts import (
    AttemptMetrics, ExplorationAdmission, NovelProblemCase, NovelProblemSuite, ProblemDomain,
    SuiteSplit, answer_digest,
)
from .service import GeneralizationService
from .workflow import GeneralizationWorkflowStore, WorkflowStep
from .skills import LearnedSkill, LearnedSkillStore
from .advanced import AdvancedGeneralizationStore, EpisodePhase, FailureHypothesis

__all__ = [
    "AttemptMetrics", "ExplorationAdmission", "GeneralizationService", "NovelProblemCase",
    "NovelProblemSuite", "ProblemDomain", "SuiteSplit", "answer_digest",
    "GeneralizationWorkflowStore", "WorkflowStep",
    "LearnedSkill", "LearnedSkillStore",
    "AdvancedGeneralizationStore", "EpisodePhase", "FailureHypothesis",
]
