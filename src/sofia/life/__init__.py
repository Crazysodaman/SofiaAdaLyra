"""Independent digital life and Project Forge over canonical owners."""

from .model import (
    ArtifactEvaluation, ExperienceRecord, InterestRecord, InterestStatus,
    LifeProject, LifeSelection, MilestoneStatus, PersonalJudgment,
    ProjectBrief, ProjectEvent, ProjectIdea, ProjectMilestone, ProjectScope,
    ProjectStatus, ResourceBudget, SelectionKind, TechnicalOutcome,
)
from .store import LifeStore
from .coordinator import SelfDirectedLifeCoordinator
from .idea_agent import (
    ProjectIdeaAgent, ProjectIdeaGenerationError, ProjectIdeaSuggestion,
)

__all__ = [
    "ArtifactEvaluation", "ExperienceRecord", "InterestRecord", "InterestStatus",
    "LifeProject", "LifeSelection", "MilestoneStatus", "PersonalJudgment",
    "ProjectBrief", "ProjectEvent", "ProjectIdea", "ProjectMilestone",
    "ProjectScope", "ProjectStatus", "ResourceBudget", "SelectionKind",
    "TechnicalOutcome", "LifeStore", "SelfDirectedLifeCoordinator",
    "ProjectIdeaAgent", "ProjectIdeaGenerationError", "ProjectIdeaSuggestion",
]
