"""Independent digital life and Project Forge over canonical owners."""

from .model import (
    ArtifactEvaluation, ExperienceRecord, InterestRecord, InterestStatus,
    LifeProject, LifeSelection, MilestoneStatus, MotivationSignal, PersonalJudgment,
    ProjectBrief, ProjectEvent, ProjectIdea, ProjectMilestone, ProjectScope,
    ProjectStatus, ResourceBudget, SelectionKind, TechnicalOutcome,
)
from .store import LifeStore
from .hobby import HobbyEngagement, HobbyRecord, HobbyStatus, HobbyStore
from .decay import (
    DecayedHobby, DecayedInterest, effective_hobby_strength,
    effective_interest_strength, hobby_decay_report, interest_decay_report,
)
from .fulfillment import FulfillmentReader, FulfillmentReport
from .coordinator import SelfDirectedLifeCoordinator
from .idea_agent import (
    ProjectIdeaAgent, ProjectIdeaGenerationError, ProjectIdeaSuggestion,
)

__all__ = [
    "ArtifactEvaluation", "ExperienceRecord", "InterestRecord", "InterestStatus",
    "LifeProject", "LifeSelection", "MilestoneStatus", "MotivationSignal", "PersonalJudgment",
    "ProjectBrief", "ProjectEvent", "ProjectIdea", "ProjectMilestone",
    "ProjectScope", "ProjectStatus", "ResourceBudget", "SelectionKind",
    "TechnicalOutcome", "LifeStore", "SelfDirectedLifeCoordinator",
    "ProjectIdeaAgent", "ProjectIdeaGenerationError", "ProjectIdeaSuggestion",
    "HobbyEngagement", "HobbyRecord", "HobbyStatus", "HobbyStore",
    "DecayedHobby", "DecayedInterest", "effective_hobby_strength",
    "effective_interest_strength", "hobby_decay_report", "interest_decay_report",
    "FulfillmentReader", "FulfillmentReport",
]
