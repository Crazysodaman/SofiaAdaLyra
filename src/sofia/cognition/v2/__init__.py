"""Cognition v2 architectural contracts.

Batch 1 defines ownership and data boundaries only. Production coordination
continues through the existing pipeline until the Turn Kernel is introduced in
Batch 2 and explicitly composed as the sole coordinator.
"""

from .contracts import (
    AcquisitionState,
    AnswerPlan,
    ClaimPlanner,
    ClaimPlan,
    ClaimValidator,
    CognitiveSchedule,
    CognitiveTask,
    CognitiveTaskKind,
    CoordinatedTurn,
    ConversationFocus,
    ConversationFocusStore,
    EpistemicState,
    EvidenceAtom,
    EvidenceAcquirer,
    EvidenceNeed,
    FocusTopic,
    FocusReference,
    ModelWorkerRole,
    PersonalityRenderer,
    PendingAction,
    ReferenceResolution,
    CognitiveScheduler,
    TurnKernel,
    TurnKernelInput,
    TurnPlan,
    UnresolvedRequest,
)
from .focus import ConversationFocusConflict, SQLiteConversationFocusStore
from .kernel import ProductionTurnKernel
from .references import ConversationReferenceResolver, EntityCandidate

__all__ = [
    "AcquisitionState",
    "AnswerPlan",
    "ClaimPlanner",
    "ClaimPlan",
    "ClaimValidator",
    "CognitiveSchedule",
    "CognitiveTask",
    "CognitiveTaskKind",
    "CoordinatedTurn",
    "ConversationFocus",
    "ConversationFocusStore",
    "EpistemicState",
    "EvidenceAtom",
    "EvidenceAcquirer",
    "EvidenceNeed",
    "FocusTopic",
    "FocusReference",
    "ModelWorkerRole",
    "PersonalityRenderer",
    "PendingAction",
    "ReferenceResolution",
    "CognitiveScheduler",
    "TurnKernel",
    "TurnKernelInput",
    "TurnPlan",
    "UnresolvedRequest",
    "ConversationFocusConflict",
    "SQLiteConversationFocusStore",
    "ProductionTurnKernel",
    "ConversationReferenceResolver",
    "EntityCandidate",
]
