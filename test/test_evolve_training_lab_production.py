"""Deferred production Hephaestus GPU/isolated training research plan tests."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import json
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.evolve.training_sources import TrainingDatasetStore,inspect_public_dataset
from sofia.evolve.training_lab import (
    TrainingLabPlan,TrainingLabReviewStore,assess_training_lab,
)
from sofia.safe.permissions import capability_permission_policy,PermissionLevel

pytestmark=pytest.mark.pkg_core
NOW=datetime(2026,10,11,20,tzinfo=timezone.utc)
ARTEMIS=uuid4()
HEPHAESTUS=uuid4()


def source(path,stem):
    path.write_text("".join(json.dumps({
        "instruction":f"Public {stem} practice {i}",
        "response":f"Harmless demonstration {i}",
    })+"\n" for i in range(22)),encoding="utf-8")


def model_and_sources(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    RuntimeUserSettingsStore(state).load()
    ds=TrainingDatasetStore(state)
    a=tmp_path/"training.jsonl"; b=tmp_path/"evaluation.jsonl"
    source(a,"train");source(b,"eval")
    def review(path,kind):
        obj=inspect_public_dataset(
            path=path,source_class="owner_original_nonprivate",
            license_id="OWNER-ORIGINAL",
            source_ref="owner-source:"+kind,
            approval_ref="owner-ui:"+kind,
            at=NOW,
        )
        ds.record(obj)
        return obj
    return state,ds,review(a,"training"),review(b,"heldout")


def plan(training,heldout,**overrides):
    kwargs={
        "plan_id":"train:"+uuid4().hex,
        "artemis_node_id":ARTEMIS,
        "hephaestus_vm_id":HEPHAESTUS,
        "base_model_sha256":"a"*64,
        "training_data_sha256":training.digest,
        "heldout_data_sha256":heldout.digest,
        "data_use_approval_ref":training.approval_ref,
        "method":"qlora",
        "seed":42,
        "cpu_cores":2,"ram_mb":4096,
        "scratch_disk_gib":12,
        "max_wall_seconds":3600,
        "max_gpu_seconds":0,"max_gpu_vram_mb":0,
        "max_external_cost_usd_cents":0,"gpu_worker":"none",
        "created_at":NOW,"expires_at":NOW+timedelta(minutes=15),
        "owner_review_receipt":"owner-ui:independent-lab-"+uuid4().hex,
    }
    kwargs.update(overrides)
    return TrainingLabPlan(**kwargs)


def test_reviewed_public_sources_can_qualify_but_osless_guest_never_trains(tmp_path):
    state,ds,training,heldout=model_and_sources(tmp_path)
    reviewed_plan=plan(training,heldout)
    judgment=assess_training_lab(
        reviewed_plan,dataset_store=ds,
        guest_debian_attested=False,
        venus_gpu_job_approved=False,at=NOW,
    )
    assert judgment.source_review_eligible is True
    assert judgment.runtime_ready is False
    assert judgment.training_authorized is False
    assert judgment.weights_promotion_allowed is False
    assert any("attested Debian" in text for text in judgment.hard_blockers)
    assert any("no trained-adapter GPU" in text for text in judgment.hard_blockers)
    assert reviewed_plan.manifest()["guest_admin"]=="sofia-admin"
    assert reviewed_plan.manifest()["guest_worker"]=="sofia-worker"
    assert reviewed_plan.manifest()["network_mode"]=="internal_host_guest_no_lan"
    assert reviewed_plan.manifest()["canonical_db_mount"] is False
    assert reviewed_plan.manifest()["guest_root_execution"] is False
    status=TrainingLabReviewStore(state)
    status.record(reviewed_plan,judgment)
    status.record(reviewed_plan,judgment)
    brief=status.latest_status()
    assert brief["source_eligible"] is True
    assert brief["may_execute_training"] is False
    assert brief["may_promote_model"] is False
    assert brief["gpu_lease_granted"] is False
    assert capability_permission_policy("ops.training.lab.inspect").level is PermissionLevel.OBSERVE_READ


@pytest.mark.parametrize("override",[
    {"network_mode":"NAT"},
    {"guest_ssh_enabled":True},
    {"guest_root_execution":True},
    {"canonical_db_mount":True},
    {"host_secrets_mounted":True},
    {"may_train":True},
    {"may_install_model":True},
    {"seed":-1},
    {"cpu_cores":96},
    {"ram_mb":999999},
    {"scratch_disk_gib":4096},
    {"max_wall_seconds":999999},
    {"max_gpu_seconds":999999},
    {"max_gpu_vram_mb":999999},
    {"max_external_cost_usd_cents":50000},
    {"gpu_worker":"unknown_external_node"},
    {"method":"from_scratch"},
])
def test_training_lab_source_rejects_unreviewed_host_privileges_and_costs(tmp_path,override):
    _,_,train,evaluation=model_and_sources(tmp_path)
    with pytest.raises((PermissionError,ValueError)):
        plan(train,evaluation,**override)


@pytest.mark.parametrize("override", [
    {"guest_ssh_enabled": 1},
    {"guest_root_execution": "false"},
    {"canonical_db_mount": None},
    {"host_secrets_mounted": 0},
    {"may_train": "no"},
    {"may_install_model": []},
])
def test_training_review_requires_typed_authority_flags(tmp_path, override):
    _, _, training, heldout = model_and_sources(tmp_path)
    with pytest.raises(TypeError, match="explicit boolean"):
        plan(training, heldout, **override)


def test_training_guest_identity_must_be_distinct_from_host(tmp_path):
    _, _, training, heldout = model_and_sources(tmp_path)
    with pytest.raises(PermissionError, match="cannot reuse enrolled host"):
        plan(training, heldout, hephaestus_vm_id=ARTEMIS)


def test_training_review_rejects_invalid_clock_type(tmp_path):
    _, dataset_store, training, heldout = model_and_sources(tmp_path)
    with pytest.raises(ValueError, match="aware plan review time"):
        assess_training_lab(plan(training, heldout), dataset_store=dataset_store, at=None)


def test_venus_gpu_plan_is_not_a_valid_gpu_lease(tmp_path):
    state,ds,training,heldout=model_and_sources(tmp_path)
    pending=plan(
        training,heldout,gpu_worker="venus_separately_approved",
        max_gpu_seconds=1800,max_gpu_vram_mb=8192,
    )
    result=assess_training_lab(
        pending,dataset_store=ds,
        guest_debian_attested=False,
        venus_gpu_job_approved=False,at=NOW,
    )
    assert not result.runtime_ready
    assert any("Venus GPU lease" in message for message in result.hard_blockers)
    # Even a test caller claiming hypothetical OS/GPU readiness is NOT
    # host authority and must not make the returned review executable.
    purported=assess_training_lab(
        pending,dataset_store=ds,
        guest_debian_attested=True,
        venus_gpu_job_approved=True,at=NOW,
    )
    assert purported.training_authorized is False
    assert purported.runtime_ready is False
    assert purported.weights_promotion_allowed is False


def test_revocation_still_blocks_training_lab_after_initial_review(tmp_path):
    state,ds,training,heldout=model_and_sources(tmp_path)
    draft=plan(training,heldout)
    ds.revoke(digest=training.digest,at=NOW,owner_receipt="owner-ui:revoke-guest-plan")
    judgment=assess_training_lab(draft,dataset_store=ds,at=NOW)
    assert judgment.source_review_eligible is False
    assert "source was never independently reviewed" in ";".join(judgment.hard_blockers)


def test_training_plan_expires_and_never_acquires_permanent_rights(tmp_path):
    _,ds,training,heldout=model_and_sources(tmp_path)
    scheduled=plan(training,heldout)
    expired=assess_training_lab(
        scheduled,dataset_store=ds,at=NOW+timedelta(minutes=16),
    )
    assert "training plan expired" in expired.hard_blockers
    assert expired.training_authorized is False
    assert expired.gpu_lease_granted is False



def test_option_b_unverified_internal_network_blocks_training_lab_even_if_ids_match(
    tmp_path,monkeypatch,
):
    from sofia.ops.workshop_handoff import WorkshopHandoffStore
    state,ds,training,heldout=model_and_sources(tmp_path)
    proposed=plan(training,heldout)
    handoff=WorkshopHandoffStore(state)
    monkeypatch.setattr(
        WorkshopHandoffStore,"read_model_brief",
        lambda self:{
            "status":"reviewed_read_only",
            "artemis_node_id":str(ARTEMIS),
            "vm_guid":str(HEPHAESTUS),
            "guest_name":"Hephaestus",
            "ready_for_bootstrap_review":False,
            "internal_isolation_observed":False,
        },
    )
    result=assess_training_lab(
        proposed,dataset_store=ds,
        workshop_handoff_store=handoff,at=NOW,
    )
    assert result.source_review_eligible is True
    assert not result.runtime_ready
    assert any("Internal network isolation" in msg for msg in result.hard_blockers)
