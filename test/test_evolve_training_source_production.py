"""Deferred production EVOLVE private-data exclusion and registered LoRA admission."""
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import json
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
import pytest
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.evolve.training_sources import (
    TRAINING_METHODS,TrainingDatasetStore,inspect_public_dataset,
)
from sofia.evolve.training_policy import (
    AdaptationPlan,assess_registered_adaptation,
)
from sofia.safe.permissions import capability_permission_policy,PermissionLevel

pytestmark=pytest.mark.pkg_core
NOW=datetime(2026,10,11,18,tzinfo=timezone.utc)


def corpus(path:Path,word:str)->None:
    path.write_text("".join(
        json.dumps({
            "instruction":f"Public {word} wiring drill {i}",
            "response":f"Step {i} shows neutral demonstration only",
        })+"\n" for i in range(23)
    ),encoding="utf-8")


def approve(path:Path,store:TrainingDatasetStore,receipt:str):
    review=inspect_public_dataset(
        path=path,
        source_class="owner_original_nonprivate",
        license_id="OWNER-ORIGINAL",
        source_ref="owner-source:"+receipt,
        approval_ref="owner-ui:"+receipt,
        at=NOW,
    )
    store.record(review)
    return review


def test_training_modes_distinguish_prompt_adapters_and_scratch_with_no_self_deploy():
    assert set(TRAINING_METHODS)=={
        "modelfile_prompt","lora_qlora","from_scratch",
    }
    assert TRAINING_METHODS["modelfile_prompt"]["weights_modified"] is False
    assert TRAINING_METHODS["lora_qlora"]["weights_modified"] is True
    assert TRAINING_METHODS["from_scratch"]["weights_modified"] is True
    assert TRAINING_METHODS["from_scratch"]["may_deploy"] is False
    assert TRAINING_METHODS["lora_qlora"]["may_deploy"] is False


def test_genuine_public_dataset_review_never_records_raw_samples_or_authorizes_job(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    RuntimeUserSettingsStore(state).load()
    rows=tmp_path/"owner_public.jsonl"
    corpus(rows,"gaia")
    store=TrainingDatasetStore(state)
    saved=approve(rows,store,"gaia-public")
    assert saved.unique_rows==23
    assert saved.training_authorized is False
    assert saved.private_data_authorized is False
    assert saved.deployment_authorized is False
    assert store.find(saved.digest)==saved
    status=store.model_brief()
    assert status["actual_training_authorized"] is False
    assert status["model_switch_authorized"] is False
    assert status["raw_chat_screen_discord_training"] is False
    import sqlite3
    with sqlite3.connect(state) as db:
        raw=db.execute(
            "SELECT metadata FROM evolve_training_dataset_review"
        ).fetchone()[0]
    assert "Public gaia wiring drill" not in raw
    assert "neutral demonstration" not in raw
    assert capability_permission_policy("ops.training.inspect").level is PermissionLevel.OBSERVE_READ


@pytest.mark.parametrize("denied",[
    "raw_lifelong_chat","emotion_journal","private_discord",
    "screen_capture","voice_recording","third_party_private",
    "memory","secret_screenshot",
])
def test_raw_private_sources_cannot_be_relabelled_as_training_material(tmp_path,denied):
    rows=tmp_path/"public.jsonl"
    corpus(rows,"public")
    with pytest.raises(PermissionError,match="prohibited"):
        inspect_public_dataset(
            path=rows,source_class=denied,license_id="OWNER-ORIGINAL",
            source_ref="owner-source:test",approval_ref="owner-ui:test",at=NOW,
        )


@pytest.mark.parametrize("bad_row",[
    {"role":"user","content":"Hello"},
    {"instruction":"Please summarize private discord messages","response":"No"},
    {"instruction":"Use account password=12345","response":"No"},
    {"instruction":"Send to user@example.com","response":"No"},
    {"messages":[{"role":"user","content":"Private"}]},
    {"instruction":"Take a screenshot","response":"No"},
])
def test_source_scanner_blocks_raw_private_and_secret_patterns(tmp_path,bad_row):
    path=tmp_path/"possibly_private.jsonl"
    valid=[{
        "instruction":f"Public explanation #{i}",
        "response":f"Public answer #{i}",
    } for i in range(25)]
    valid.append(bad_row)
    path.write_text("".join(json.dumps(v)+"\n" for v in valid),encoding="utf-8")
    with pytest.raises(PermissionError):
        inspect_public_dataset(
            path=path,source_class="owner_original_nonprivate",
            license_id="OWNER-ORIGINAL",
            source_ref="owner-source:review",approval_ref="owner-ui:review",at=NOW,
        )


def test_adaptation_requires_independent_heldout_and_reverifies_bytes(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    RuntimeUserSettingsStore(state).load()
    store=TrainingDatasetStore(state)
    train=tmp_path/"train.jsonl"
    heldout=tmp_path/"heldout.jsonl"
    corpus(train,"project")
    corpus(heldout,"examples")
    training=approve(train,store,"training")
    hold=approve(heldout,store,"heldout")
    plan=AdaptationPlan(
        base_model_digest="a"*64,
        training_data_digest=training.digest,
        heldout_data_digest=hold.digest,
        data_use_approval_ref=training.approval_ref,
        adaptation_kind="lora",
        max_gpu_hours=1.0,max_vram_mb=4096,preserve_source_privacy=True,
    )
    review=assess_registered_adaptation(plan,dataset_store=store)
    assert review.research_eligible is True
    assert review.production_install_authorized is False
    heldout.write_text(heldout.read_text()+"\n")
    changed=assess_registered_adaptation(plan,dataset_store=store)
    assert changed.research_eligible is False
    assert any("changed since" in msg or "unsafe on reread" in msg for msg in changed.blockers)
    assert assess_registered_adaptation(
        replace(plan,data_use_approval_ref="owner-ui:wrong"),dataset_store=store,
    ).research_eligible is False


def test_no_training_job_is_created_by_a_dataset_admission():
    assert TRAINING_METHODS["lora_qlora"]["may_deploy"] is False



def test_owner_revocation_prevents_future_lora_use_of_previously_reviewed_source(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    RuntimeUserSettingsStore(state).load()
    store=TrainingDatasetStore(state)
    source=tmp_path/"public_training.jsonl"
    heldout=tmp_path/"public_eval.jsonl"
    corpus(source,"owners")
    corpus(heldout,"heldout")
    train_review=approve(source,store,"approved-training")
    hold_review=approve(heldout,store,"approved-heldout")
    baseline=AdaptationPlan(
        base_model_digest="a"*64,
        training_data_digest=train_review.digest,
        heldout_data_digest=hold_review.digest,
        data_use_approval_ref=train_review.approval_ref,
        adaptation_kind="qlora",
        max_gpu_hours=1.0,max_vram_mb=4096,preserve_source_privacy=True,
    )
    assert assess_registered_adaptation(
        baseline,dataset_store=store,
    ).research_eligible
    store.revoke(
        digest=train_review.digest,
        at=NOW,owner_receipt="owner-ui:withdraw-1",
    )
    assert store.find(train_review.digest) is None
    result=assess_registered_adaptation(
        baseline,dataset_store=store,
    )
    assert result.research_eligible is False
    assert "never independently reviewed" in ";".join(result.blockers)
    brief=store.model_brief()
    assert any(
        row["digest"]==train_review.digest and row["status"]=="revoked"
        for row in brief["reviewed"]
    )
    assert brief["actual_training_authorized"] is False
    with pytest.raises(PermissionError,match="permanently revoked"):
        store.revoke(
            digest=train_review.digest,
            at=NOW,owner_receipt="owner-ui:withdraw-2",
        )


def test_training_data_revocation_requires_verified_review_and_exact_owner_receipt(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    RuntimeUserSettingsStore(state).load()
    store=TrainingDatasetStore(state)
    with pytest.raises(LookupError,match="unknown training dataset"):
        store.revoke(
            digest="a"*64,
            at=NOW,owner_receipt="owner-ui:revoke",
        )
    with pytest.raises(PermissionError,match="owner dataset"):
        store.revoke(
            digest="a"*64,at=NOW,
            owner_receipt="llm-self:forged",
        )
    with pytest.raises(ValueError,match="exact"):
        store.revoke(
            digest="missing",at=NOW,
            owner_receipt="owner-ui:revoke",
        )
