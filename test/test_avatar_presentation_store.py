from __future__ import annotations

import json
import sqlite3

import pytest

from sofia.avatar.presentation import (
    AppearanceState,
    AttireMode,
    PresentationAuthority,
    PresentationConflict,
    PrivatePresentationGrant,
)
from sofia.avatar.presentation_store import PresentationStore, PresentationStoreError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def setup_authority():
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="#8B1E3F",
            tail_color="#3A245C",
            style_tags=("engineer",),
        ),
    )
    return catalog, outfits, authority


def grant():
    return PrivatePresentationGrant(True, True, True, True, False)


def test_store_round_trip_preserves_current_and_daily(tmp_path):
    catalog, outfits, authority = setup_authority()
    authority.propose_outfit(
        operation_id="op.lounge",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="late night",
        daily=True,
    )
    authority.commit_text(operation_id="op.lounge", renderer_unavailable=True)
    authority.propose_nude(
        operation_id="op.nude",
        expected_revision=2,
        reason="private state",
        grant=grant(),
    )
    authority.commit_text(
        operation_id="op.nude",
        renderer_unavailable=True,
        grant=grant(),
    )

    store = PresentationStore(tmp_path / "sofia.db")
    store.save(authority)
    restored = store.load(catalog.wardrobe, outfits=outfits)

    assert restored.current.attire is AttireMode.NUDE
    assert restored.last_daily.outfit_id == "lounge.relaxed"


def test_store_writes_snapshot_into_canonical_sqlite(tmp_path):
    _, _, authority = setup_authority()
    path = tmp_path / "sofia.db"
    PresentationStore(path).save(authority)

    with sqlite3.connect(path) as db:
        row = db.execute(
            """
            SELECT snapshot_json
            FROM avatar_presentation_state
            WHERE state_key='canonical'
            """
        ).fetchone()

    assert row is not None
    assert json.loads(row[0])["schema"] == "sofia.avatar.presentation.v1"


def test_store_refuses_unsettled_transition(tmp_path):
    _, _, authority = setup_authority()
    authority.propose_outfit(
        operation_id="op.pending",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="pending",
    )
    with pytest.raises(PresentationConflict, match="unresolved"):
        PresentationStore(tmp_path / "sofia.db").save(authority)


def test_store_rejects_corrupt_snapshot_json(tmp_path):
    path = tmp_path / "sofia.db"
    store = PresentationStore(path)
    with sqlite3.connect(path) as db:
        db.execute(
            """
            INSERT INTO avatar_presentation_state (
                state_key,
                snapshot_json,
                updated_at
            )
            VALUES ('canonical', '{broken', '2026-10-01T00:00:00+00:00')
            """
        )
        db.commit()
    catalog, outfits, _ = setup_authority()
    with pytest.raises(PresentationStoreError):
        store.load(catalog.wardrobe, outfits=outfits)



def test_store_wraps_denied_restored_snapshot_as_store_error(tmp_path):
    catalog, outfits, authority = setup_authority()
    snapshot = authority.snapshot()
    snapshot["last_daily"]["private_only"] = True

    path = tmp_path / "sofia.db"
    store = PresentationStore(path)
    with sqlite3.connect(path) as db:
        db.execute(
            """
            INSERT INTO avatar_presentation_state (
                state_key,
                snapshot_json,
                updated_at
            )
            VALUES ('canonical', ?, '2026-10-03T00:00:00+00:00')
            """,
            (json.dumps(snapshot),),
        )
        db.commit()

    with pytest.raises(PresentationStoreError, match="invalid"):
        store.load(catalog.wardrobe, outfits=outfits)



def test_persist_mutation_rolls_back_live_authority_when_save_fails(
    tmp_path,
    monkeypatch,
):
    catalog, outfits, authority = setup_authority()
    store = PresentationStore(tmp_path / "sofia.db")
    store.save(authority)
    before = authority.snapshot()

    def fail_save(_authority):
        raise PresentationStoreError("synthetic durable failure")

    monkeypatch.setattr(store, "save", fail_save)

    def mutate():
        authority.propose_outfit(
            operation_id="op.synthetic.failure",
            expected_revision=authority.current.revision,
            outfit_id="lounge.relaxed",
            reason="synthetic failure",
            daily=True,
        )
        return authority.commit_text(
            operation_id="op.synthetic.failure",
            renderer_unavailable=True,
        )

    with pytest.raises(PresentationStoreError, match="synthetic"):
        store.persist_mutation(authority, mutate)

    assert authority.snapshot() == before
    assert authority.pending is None


def test_persist_mutation_compensates_when_verification_fails(
    tmp_path,
    monkeypatch,
):
    catalog, outfits, authority = setup_authority()
    path = tmp_path / "sofia.db"
    store = PresentationStore(path)
    store.save(authority)
    before = authority.snapshot()

    monkeypatch.setattr(
        store,
        "_read_snapshot_json",
        lambda: json.dumps({"schema": "wrong"}),
    )

    def mutate():
        authority.propose_outfit(
            operation_id="op.synthetic.verify",
            expected_revision=authority.current.revision,
            outfit_id="lounge.relaxed",
            reason="synthetic verification failure",
            daily=True,
        )
        return authority.commit_text(
            operation_id="op.synthetic.verify",
            renderer_unavailable=True,
        )

    with pytest.raises(PresentationStoreError, match="verification"):
        store.persist_mutation(authority, mutate)

    assert authority.snapshot() == before
    with sqlite3.connect(path) as db:
        encoded = db.execute(
            """
            SELECT snapshot_json
            FROM avatar_presentation_state
            WHERE state_key='canonical'
            """
        ).fetchone()[0]
    assert json.loads(encoded) == before
