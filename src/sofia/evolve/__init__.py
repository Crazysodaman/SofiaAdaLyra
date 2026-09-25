"""PKG-EVOLVE: governed proposals and independently authorized revisions."""

from .amendment import (
    AmendmentProposal,
    ProposalStatus,
    ProtectedTarget,
    content_digest,
    inspect,
)
from .approval import (
    AmendmentApproval,
    ApprovalAction,
    ApprovalVerifier,
    approval_matches,
)
from .executor import (
    AmendmentExecution,
    AmendmentExecutionStatus,
    ProtectedAmendmentError,
    ProtectedAmendmentExecutor,
    ProtectedPaths,
)

__all__ = [
    "AmendmentApproval",
    "AmendmentExecution",
    "AmendmentExecutionStatus",
    "AmendmentProposal",
    "ApprovalAction",
    "ApprovalVerifier",
    "ProposalStatus",
    "ProtectedAmendmentError",
    "ProtectedAmendmentExecutor",
    "ProtectedPaths",
    "ProtectedTarget",
    "approval_matches",
    "content_digest",
    "inspect",
]
