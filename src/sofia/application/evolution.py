from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sofia.config.model import SofiaConfiguration
from sofia.evolve.approval import AmendmentApproval
from sofia.evolve.amendment import (
    AmendmentProposal,
    ProtectedTarget,
    content_digest,
)
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
    RevisionScope,
    revision_content_digest,
)
from sofia.evolve.state_plane_adapter import StatePlaneRevisionAdapter
from sofia.evolve.lifecycle import (
    EvolutionEvidence,
    EvolutionLifecycleStore,
    EvolutionOutcome,
    EvolutionOutcomeRecord,
    EvolutionProposalRecord,
    EvolutionProposalStatus,
)
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
        self.lifecycle = EvolutionLifecycleStore(configuration.state_path)
        self.adapter = StatePlaneRevisionAdapter(state_plane)
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
            adapter=self.adapter,
            verifier=verifier,
        )

    def record_evidence(
        self,
        *,
        evidence_id: str,
        kind: str,
        source_ref: str,
        summary: str,
        payload: dict[str, object],
        observed_at: datetime,
        recorded_at: datetime | None = None,
    ) -> EvolutionEvidence:
        """Record provenance-backed evidence before it can support a proposal."""

        return self.lifecycle.record_evidence(
            EvolutionEvidence(
                evidence_id=evidence_id,
                kind=kind,
                source_ref=source_ref,
                summary=summary,
                payload=payload,
                observed_at=observed_at,
                recorded_at=recorded_at or datetime.now(timezone.utc),
            )
        )

    def propose_revision(
        self,
        *,
        proposal_id: str,
        scope: RevisionScope,
        key: str,
        proposed_content: str,
        evidence_ids: tuple[str, ...],
        reason: str,
        rollback_plan: str,
        success_metric: str,
        now: datetime,
        ttl: timedelta = timedelta(days=7),
    ) -> EvolutionProposalRecord:
        self.adapter.validate(scope, key, proposed_content)
        proposal = RevisionProposal(
            proposal_id=proposal_id,
            scope=scope,
            key=key,
            expected_digest=self.adapter.read_digest(scope, key),
            proposed_digest=revision_content_digest(proposed_content),
            evidence_ids=evidence_ids,
            reason=reason,
            rollback_plan=rollback_plan,
            created_at=now,
            expires_at=now + ttl,
        )
        return self.lifecycle.add_proposal(
            proposal,
            proposed_content=proposed_content,
            success_metric=success_metric,
            now=now,
        )

    def propose_amendment(
        self,
        *,
        proposal_id: str,
        target: ProtectedTarget,
        proposed_content: str,
        evidence_ids: tuple[str, ...],
        reason: str,
        rollback_plan: str,
        success_metric: str,
        now: datetime,
        ttl: timedelta = timedelta(days=7),
    ) -> EvolutionProposalRecord:
        current = self.protected._read_text(self.protected._target_path(target))
        self.protected._validate_proposed_content(target, current, proposed_content)
        proposal = AmendmentProposal(
            proposal_id=proposal_id,
            target=target,
            expected_digest=content_digest(current),
            proposed_digest=content_digest(proposed_content),
            evidence_ids=evidence_ids,
            reason=reason,
            rollback_plan=rollback_plan,
            created_at=now,
            expires_at=now + ttl,
        )
        return self.lifecycle.add_proposal(
            proposal,
            proposed_content=proposed_content,
            success_metric=success_metric,
            now=now,
        )

    def proposals(self, *, limit: int = 50) -> tuple[EvolutionProposalRecord, ...]:
        return self.lifecycle.list_proposals(limit=limit)

    def proposal(self, proposal_id: str) -> EvolutionProposalRecord:
        return self.lifecycle.get_proposal(proposal_id)

    def apply_recorded(
        self,
        *,
        proposal_id: str,
        approval_id: str,
        now: datetime,
    ) -> AmendmentExecution | RevisionExecution:
        record = self.lifecycle.get_proposal(proposal_id)
        if record.status is not EvolutionProposalStatus.APPROVED:
            raise PermissionError("EVOLVE proposal is not in approved lifecycle state")
        proposal = self.lifecycle.proposal_object(proposal_id)
        approval = self.approvals.load_approval(approval_id)
        if isinstance(proposal, AmendmentProposal):
            if not isinstance(approval, AmendmentApproval):
                raise TypeError("protected proposal requires amendment approval")
            result = self.apply_protected(
                proposal,
                approval,
                proposed_content=record.proposed_content,
                now=now,
            )
            next_status = EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION
        else:
            if not isinstance(approval, RevisionApproval):
                raise TypeError("reviewed proposal requires revision approval")
            result = self.apply_revision(
                proposal,
                approval,
                proposed_content=record.proposed_content,
                now=now,
            )
            next_status = (
                EvolutionProposalStatus.EVALUATING
                if proposal.scope is RevisionScope.PREFERENCE
                else EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION
            )
        self.lifecycle.transition(
            proposal_id,
            expected=(EvolutionProposalStatus.APPROVED,),
            status=next_status,
            now=now,
        )
        return result

    def mark_effective(self, proposal_id: str, *, now: datetime) -> EvolutionProposalRecord:
        """Confirm a restart/recomposition made an applied change effective."""

        return self.lifecycle.transition(
            proposal_id,
            expected=(EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION,),
            status=EvolutionProposalStatus.EVALUATING,
            now=now,
        )

    def rollback_recorded(
        self,
        *,
        proposal_id: str,
        approval_id: str,
        now: datetime,
    ) -> AmendmentExecution | RevisionExecution:
        record = self.lifecycle.get_proposal(proposal_id)
        allowed = (
            EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION,
            EvolutionProposalStatus.EVALUATING,
            EvolutionProposalStatus.UNDER_REVIEW,
        )
        if record.status not in allowed:
            raise PermissionError("EVOLVE proposal is not in a rollback-eligible state")
        proposal = self.lifecycle.proposal_object(proposal_id)
        approval = self.approvals.load_approval(approval_id)
        if isinstance(proposal, AmendmentProposal):
            if not isinstance(approval, AmendmentApproval):
                raise TypeError("protected proposal requires amendment approval")
            result = self.rollback_protected(proposal, approval, now=now)
        else:
            if not isinstance(approval, RevisionApproval):
                raise TypeError("reviewed proposal requires revision approval")
            result = self.rollback_revision(proposal, approval, now=now)
        self.lifecycle.transition(
            proposal_id,
            expected=allowed,
            status=EvolutionProposalStatus.ROLLED_BACK,
            now=now,
        )
        return result

    def record_outcome(
        self,
        proposal_id: str,
        *,
        outcome: EvolutionOutcome,
        evidence_id: str,
        notes: str,
        measured_at: datetime,
    ) -> EvolutionOutcomeRecord:
        return self.lifecycle.record_outcome(
            proposal_id,
            outcome=outcome,
            evidence_id=evidence_id,
            notes=notes,
            measured_at=measured_at,
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
