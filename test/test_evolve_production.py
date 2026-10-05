from datetime import datetime, timedelta, timezone
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.application.evolution import SofiaEvolutionService
from sofia.composition.root import compose
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.evolve.approval import ApprovalAction
from sofia.evolve.lifecycle import (
    EvolutionEvidence,
    EvolutionLifecycleStore,
    EvolutionOutcome,
    EvolutionProposalStatus,
)
from sofia.evolve.revision import RevisionApproval, RevisionScope
from sofia.safe.evolve_approval import (
    DurableEvolutionApprovalVerifier,
    approval_signature_payload,
    revocation_signature_payload,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


def configuration(tmp_path) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
    )


def key_material(tmp_path):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "evolve-approval.pub"
    public_path.write_bytes(public)
    return private, public, public_path


def evidence(evidence_id="evidence-1") -> EvolutionEvidence:
    return EvolutionEvidence(
        evidence_id=evidence_id,
        kind="verification",
        source_ref="verify:full:test-revision",
        summary="Observed deterministic regression and verified reproduction.",
        payload={"accepted": True, "finding": "provider temperature too high"},
        observed_at=NOW,
        recorded_at=NOW,
    )


def test_lifecycle_requires_real_evidence_and_preserves_canonical_proposal(tmp_path):
    store = EvolutionLifecycleStore(tmp_path / "state.db")
    service_config = configuration(tmp_path)
    plane = SQLiteStatePlane(service_config.state_path)
    service = SofiaEvolutionService(configuration=service_config, state_plane=plane)

    with pytest.raises(ValueError, match="evidence does not exist"):
        service.propose_revision(
            proposal_id="proposal-missing-evidence",
            scope=RevisionScope.CONFIG,
            key="provider.temperature",
            proposed_content='{"value":0.3}',
            evidence_ids=("opaque-proof",),
            reason="Tune observed instability",
            rollback_plan="Restore prior reviewed value",
            success_metric="Verification score does not regress",
            now=NOW,
        )

    service.lifecycle.record_evidence(evidence())
    record = service.propose_revision(
        proposal_id="proposal-1",
        scope=RevisionScope.CONFIG,
        key="provider.temperature",
        proposed_content='{"value":0.3}',
        evidence_ids=("evidence-1",),
        reason="Tune observed instability",
        rollback_plan="Restore prior reviewed value",
        success_metric="Verification score does not regress",
        now=NOW,
    )
    restored = service.lifecycle.proposal_object(record.proposal_id)

    assert record.status is EvolutionProposalStatus.PROPOSED
    assert restored.fingerprint == record.fingerprint
    assert restored.evidence_ids == ("evidence-1",)
    assert store.list_proposals() == ()


def test_approval_is_bound_to_external_ed25519_trust_root(tmp_path):
    private, public, _ = key_material(tmp_path)
    path = tmp_path / "state.db"
    verifier = DurableEvolutionApprovalVerifier(
        path,
        trusted_keys={"sparks-root": public},
    )
    approval = RevisionApproval(
        approval_id="approval-1",
        proposal_id="proposal-1",
        proposal_fingerprint="a" * 64,
        action=ApprovalAction.APPLY,
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_reference="review:1",
    )
    signature = private.sign(approval_signature_payload(approval))
    verifier.record_revision(
        approval,
        signer_key_id="sparks-root",
        signature=signature,
    )
    loaded = verifier.load_approval("approval-1")

    assert loaded == approval
    with pytest.raises(PermissionError, match="signature"):
        DurableEvolutionApprovalVerifier(
            tmp_path / "other.db",
            trusted_keys={"sparks-root": public},
        ).record_revision(
            approval,
            signer_key_id="sparks-root",
            signature=b"not-a-signature",
        )


def test_approval_revocation_requires_external_signature(tmp_path):
    private, public, _ = key_material(tmp_path)
    verifier = DurableEvolutionApprovalVerifier(
        tmp_path / "state.db",
        trusted_keys={"sparks-root": public},
    )
    approval = RevisionApproval(
        approval_id="approval-1",
        proposal_id="proposal-1",
        proposal_fingerprint="a" * 64,
        action=ApprovalAction.APPLY,
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_reference="review:1",
    )
    verifier.record_revision(
        approval,
        signer_key_id="sparks-root",
        signature=private.sign(approval_signature_payload(approval)),
    )
    revoked_at = NOW + timedelta(minutes=1)
    authority_reference = "review:1:revocation"

    with pytest.raises(PermissionError, match="signature"):
        verifier.revoke(
            approval.approval_id,
            signer_key_id="sparks-root",
            signature=b"not-a-signature",
            revoked_at=revoked_at,
            authority_reference=authority_reference,
        )

    verifier.revoke(
        approval.approval_id,
        signer_key_id="sparks-root",
        signature=private.sign(
            revocation_signature_payload(
                approval.approval_id,
                revoked_at=revoked_at,
                authority_reference=authority_reference,
            )
        ),
        revoked_at=revoked_at,
        authority_reference=authority_reference,
    )
    assert not verifier._matches(
        approval_id=approval.approval_id,
        proposal_id=approval.proposal_id,
        proposal_fingerprint=approval.proposal_fingerprint,
        target_kind="revision",
        target_value="*",
        action=approval.action.value,
        approved_by=approval.approved_by,
        authority_reference=approval.authority_reference,
        now=revoked_at,
    )


def test_production_revision_runs_proposal_approval_activation_and_outcome_loop(
    tmp_path,
    monkeypatch,
):
    private, _, public_path = key_material(tmp_path)
    monkeypatch.setenv("SOFIA_EVOLVE_APPROVAL_KEY_ID", "sparks-root")
    monkeypatch.setenv("SOFIA_EVOLVE_APPROVAL_PUBLIC_KEY", str(public_path))
    config = configuration(tmp_path)
    plane = SQLiteStatePlane(config.state_path)
    service = SofiaEvolutionService(configuration=config, state_plane=plane)
    service.lifecycle.record_evidence(evidence())
    record = service.propose_revision(
        proposal_id="proposal-1",
        scope=RevisionScope.CONFIG,
        key="provider.temperature",
        proposed_content=json.dumps({"value": 0.3}, separators=(",", ":")),
        evidence_ids=("evidence-1",),
        reason="Tune observed instability",
        rollback_plan="Restore prior reviewed value",
        success_metric="Full verification remains accepted",
        now=NOW,
    )
    proposal = service.lifecycle.proposal_object(record.proposal_id)
    approval = RevisionApproval(
        approval_id="approval-1",
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.fingerprint,
        action=ApprovalAction.APPLY,
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        authority_reference="review:proposal-1",
    )
    service.approvals.record_revision(
        approval,
        signer_key_id="sparks-root",
        signature=private.sign(approval_signature_payload(approval)),
    )
    service.lifecycle.transition(
        proposal.proposal_id,
        expected=(EvolutionProposalStatus.PROPOSED,),
        status=EvolutionProposalStatus.APPROVED,
        now=NOW,
    )

    service.apply_recorded(
        proposal_id=proposal.proposal_id,
        approval_id=approval.approval_id,
        now=NOW,
    )
    assert service.proposal(proposal.proposal_id).status is (
        EvolutionProposalStatus.APPLIED_PENDING_ACTIVATION
    )
    service.mark_effective(proposal.proposal_id, now=NOW + timedelta(minutes=1))
    service.lifecycle.record_evidence(evidence("outcome-1"))
    outcome = service.record_outcome(
        proposal.proposal_id,
        outcome=EvolutionOutcome.IMPROVED,
        evidence_id="outcome-1",
        notes="Full verification remained accepted after recomposition.",
        measured_at=NOW + timedelta(minutes=2),
    )

    assert outcome.outcome is EvolutionOutcome.IMPROVED
    assert service.proposal(proposal.proposal_id).status is EvolutionProposalStatus.ACCEPTED


def test_production_composition_registers_cognitive_evolve_tools(tmp_path):
    runtime = compose(configuration(tmp_path))
    names = set(runtime.capability_system.capability_names())
    tools = {
        item.name
        for item in runtime.cognitive_system.tool_dispatcher.definitions
    }

    assert {
        "evolve.evidence.list",
        "evolve.proposal.revision.create",
        "evolve.apply",
    } <= names
    assert {
        "list_evolve_evidence",
        "propose_evolve_revision",
        "apply_evolve_proposal",
    } <= tools
