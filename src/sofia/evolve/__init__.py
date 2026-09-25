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
from .revision import (
    ReviewedRevisionExecutor,
    RevisionAdapter,
    RevisionApproval,
    RevisionApprovalVerifier,
    RevisionExecution,
    RevisionExecutionError,
    RevisionProposal,
    RevisionScope,
    RevisionStatus,
    revision_content_digest,
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
    "ReviewedRevisionExecutor",
    "RevisionAdapter",
    "RevisionApproval",
    "RevisionApprovalVerifier",
    "RevisionExecution",
    "RevisionExecutionError",
    "RevisionProposal",
    "RevisionScope",
    "RevisionStatus",
    "approval_matches",
    "content_digest",
    "inspect",
    "revision_content_digest",
]
