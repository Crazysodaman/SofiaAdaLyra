"""Deferred real-admission tests: example-level heldout separation.

No dataset leaves the temporary directory, no trainer or model is invoked,
and the canonical review stores no raw training rows.
"""
from datetime import datetime, timezone
import json

import pytest

from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.evolve.training_sources import (
    TrainingDatasetStore, inspect_public_dataset,
)
from sofia.evolve.training_policy import (
    AdaptationPlan, assess_registered_adaptation,
)

pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)


def create_dataset(path, *, prompt, answer):
    path.write_text(
        "".join(
            json.dumps({
                "instruction": prompt.format(i=i),
                "response": answer.format(i=i),
            }) + "\n"
            for i in range(23)
        ),
        encoding="utf-8",
    )


def add_review(store, path, name):
    reviewed = inspect_public_dataset(
        path=path,
        source_class="owner_original_nonprivate",
        license_id="OWNER-ORIGINAL",
        source_ref="owner-source:" + name,
        approval_ref="owner-ui:" + name,
        at=NOW,
    )
    store.record(reviewed)
    return reviewed


def plan(train, heldout):
    return AdaptationPlan(
        base_model_digest="a" * 64,
        training_data_digest=train.digest,
        heldout_data_digest=heldout.digest,
        data_use_approval_ref=train.approval_ref,
        adaptation_kind="lora", max_gpu_hours=1.0,
        max_vram_mb=4096, preserve_source_privacy=True,
    )


def test_different_file_hashes_do_not_prove_independent_heldout(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TrainingDatasetStore(state)
    first = tmp_path / "training.jsonl"
    second = tmp_path / "heldout.jsonl"
    create_dataset(
        first, prompt="Explain public motor test number {i}",
        answer="Neutral engineering example alpha {i}",
    )
    create_dataset(
        second, prompt="  EXPLAIN PUBLIC MOTOR TEST NUMBER {i} ",
        answer="Alternative public response beta {i}",
    )
    train = add_review(store, first, "training")
    heldout = add_review(store, second, "heldout")
    assert train.digest != heldout.digest
    review = assess_registered_adaptation(
        plan(train, heldout), dataset_store=store,
    )
    assert review.research_eligible is False
    assert review.production_install_authorized is False
    assert "share instruction examples" in "; ".join(review.blockers)


def test_internal_whitespace_variants_do_not_leak_heldout(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TrainingDatasetStore(state)
    first = tmp_path / "training.jsonl"
    second = tmp_path / "heldout.jsonl"
    create_dataset(
        first, prompt="Explain  public  motor test number {i}",
        answer="Neutral engineering example alpha {i}",
    )
    create_dataset(
        second, prompt="Explain\tpublic motor test number {i}",
        answer="Independent-looking response beta {i}",
    )
    train = add_review(store, first, "training")
    heldout = add_review(store, second, "heldout")
    review = assess_registered_adaptation(plan(train, heldout), dataset_store=store)
    assert not review.research_eligible
    assert not review.production_install_authorized
    assert "share instruction examples" in "; ".join(review.blockers)


def test_disjoint_verified_prompts_remain_research_eligible_not_train_authorized(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TrainingDatasetStore(state)
    first = tmp_path / "training.jsonl"
    second = tmp_path / "heldout.jsonl"
    create_dataset(
        first, prompt="Explain public motor test number {i}",
        answer="Neutral engineering example alpha {i}",
    )
    create_dataset(
        second, prompt="Explain separate electrical drill number {i}",
        answer="Public demonstration beta {i}",
    )
    train = add_review(store, first, "training")
    heldout = add_review(store, second, "heldout")
    review = assess_registered_adaptation(
        plan(train, heldout), dataset_store=store,
    )
    assert review.research_eligible is True
    assert review.production_install_authorized is False


def test_revoked_source_cannot_be_relabelled_as_reviewed(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = TrainingDatasetStore(state)
    first = tmp_path / "training.jsonl"
    create_dataset(
        first, prompt="Public transformer drill number {i}",
        answer="Public explanation gamma {i}",
    )
    reviewed = add_review(store, first, "training")
    store.revoke(
        digest=reviewed.digest, at=NOW,
        owner_receipt="owner-ui:withdraw-research-rights",
    )
    with pytest.raises(PermissionError, match="permanently revoked"):
        store.record(reviewed)
    assert store.find(reviewed.digest) is None
