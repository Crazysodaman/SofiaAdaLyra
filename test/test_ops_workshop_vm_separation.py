"""Production canonical VM identity is never a disposable workshop guest.

The admission service is intentionally read-only. Hyper-V creation, guest OS
installation, enrollment, operator consent and machine fencing are separate
privileged processes and are not implied by these tests.
"""
import pytest

from sofia.ops.workshop_policy import LaboratoryExperiment, review_lab_experiment


def _spec(guest_name: str) -> LaboratoryExperiment:
    return LaboratoryExperiment(
        experiment_id="lab-001",
        guest_image_sha256="a" * 64,
        hypervisor_host_id="verified-artemis-host-id",
        guest_name=guest_name,
        max_vcpu=4,
        max_memory_mb=4096,
        max_storage_gib=32,
        max_duration_minutes=60,
        network_mode="isolated",
        operator_approval_ref="independent-operator-review",
    )


@pytest.mark.parametrize("alias", ["Sofia", "SOFIA", " sofia ", "SoFiA"])
def test_workshop_never_admits_canonical_runtime_vm_identity(alias: str):
    result = review_lab_experiment(_spec(alias))
    assert result.review_eligible is False
    assert result.may_create_vm is False
    assert "reserved canonical VM name Sofia" in " ".join(result.blockers)


def test_distinct_hephaestus_workshop_can_be_review_eligible_not_self_created():
    result = review_lab_experiment(_spec("Hephaestus"))
    assert result.review_eligible is True
    # Eligible for supervised review is not permission to create a VM.
    assert result.may_create_vm is False


def test_workshop_network_and_exact_operator_approval_still_required():
    spec = _spec("Experiment-Guest")
    without_approval = LaboratoryExperiment(
        **{**spec.__dict__, "operator_approval_ref": None}
    )
    exposed = LaboratoryExperiment(
        **{**spec.__dict__, "network_mode": "bridged"}
    )
    assert not review_lab_experiment(without_approval).review_eligible
    assert not review_lab_experiment(exposed).review_eligible
