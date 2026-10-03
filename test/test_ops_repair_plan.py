from sofia.ops.desired import Drift
from sofia.ops.repair_plan import (
    FleetRepairPlanner,
    FleetRepairProposal,
    RepairProposalKind,
)


def test_workload_placement_drift_proposes_reviewable_migration():
    drift = Drift(
        "workload_placement",
        "plex",
        "dionysus",
        "persephone",
    )

    proposal = FleetRepairPlanner().propose(drift)

    assert proposal.kind is RepairProposalKind.WORKLOAD_MIGRATION
    assert proposal.workload_id == "plex"
    assert proposal.source_host_id == "persephone"
    assert proposal.target_host_id == "dionysus"
    assert proposal.authorized is False


def test_missing_workload_source_never_invents_migration_source():
    proposal = FleetRepairPlanner().propose(
        Drift(
            "workload_placement",
            "plex",
            "dionysus",
            None,
        )
    )

    assert proposal.kind is RepairProposalKind.NO_SAFE_REPAIR
    assert proposal.source_host_id is None
    assert "do not invent" in proposal.reason


def test_host_lifecycle_drift_does_not_guess_reboot_or_restart():
    proposal = FleetRepairPlanner().propose(
        Drift(
            "host_lifecycle",
            "artemis",
            "healthy",
            "degraded",
        )
    )

    assert proposal.kind is RepairProposalKind.NO_SAFE_REPAIR
    assert "causal repair" in proposal.reason


def test_repair_proposal_cannot_carry_authority():
    drift = Drift(
        "workload_placement",
        "plex",
        "dionysus",
        "persephone",
    )

    try:
        FleetRepairProposal(
            drift=drift,
            kind=RepairProposalKind.WORKLOAD_MIGRATION,
            reason="review",
            workload_id="plex",
            source_host_id="persephone",
            target_host_id="dionysus",
            authorized=True,
        )
    except ValueError as exc:
        assert "cannot carry execution authority" in str(exc)
    else:
        raise AssertionError("repair proposal unexpectedly carried authority")
