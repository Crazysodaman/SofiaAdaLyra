from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sofia.config.model import SofiaConfiguration
from sofia.evolve.approval import AmendmentApproval
from sofia.evolve.amendment import AmendmentProposal
from sofia.evolve.executor import (
    AmendmentExecution,
    ProtectedAmendmentExecutor,
    ProtectedPaths,
)
from sofia.evolve.revision import (
    ReviewedRevisionExecutor,
    RevisionApproval,
    RevisionExecution,
    RevisionProposal,
)
from sofia.evolve.state_plane_adapter import StatePlaneRevisionAdapter
from sofia.safe.evolve_approval import DurableEvolutionApprovalVerifier
from sofia.state.plane import StatePlane


class SofiaEvolutionService:
    """Production EVOLVE facade with no self-approval path."""

    def __init__(
        self,
        *,
        configuration: SofiaConfiguration,
        state_plane: StatePlane,
    ) -> None:
        if not isinstance(configuration, SofiaConfiguration):
            raise TypeError("configuration must be a SofiaConfiguration")
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        verifier = DurableEvolutionApprovalVerifier(configuration.state_path)
        backup_dir = Path(configuration.state_path).parent / "evolve-backups"
        self.approvals = verifier
        self.protected = ProtectedAmendmentExecutor(
            state_path=Path(configuration.state_path),
            paths=ProtectedPaths(
                identity_path=Path(configuration.identity_path),
                constitution_path=Path(configuration.constitution_path),
                constitution_hash_path=Path(configuration.constitution_hash_path),
                backup_dir=backup_dir,
            ),
            verifier=verifier,
        )
        self.reviewed = ReviewedRevisionExecutor(
            state_path=Path(configuration.state_path),
            adapter=StatePlaneRevisionAdapter(state_plane),
            verifier=verifier,
        )

    def apply_protected(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        proposed_content: str,
        now: datetime,
    ) -> AmendmentExecution:
        return self.protected.apply(
            proposal,
            approval,
            proposed_content=proposed_content,
            now=now,
        )

    def rollback_protected(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        now: datetime,
    ) -> AmendmentExecution:
        return self.protected.rollback(
            proposal,
            approval,
            now=now,
        )

    def apply_revision(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        proposed_content: str,
        now: datetime,
    ) -> RevisionExecution:
        return self.reviewed.apply(
            proposal,
            approval,
            proposed_content=proposed_content,
            now=now,
        )

    def rollback_revision(
        self,
        proposal: RevisionProposal,
        approval: RevisionApproval,
        *,
        now: datetime,
    ) -> RevisionExecution:
        return self.reviewed.rollback(
            proposal,
            approval,
            now=now,
        )
