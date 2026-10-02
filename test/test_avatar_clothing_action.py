"""Authoritative natural-language clothing action acceptance tests."""
from sofia.avatar.clothing_action import (
    ClothingActionService,
    WardrobeAutonomyDecision,
    WardrobeAutonomyPolicy,
)
from sofia.avatar.presentation import AppearanceState, PresentationAuthority
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.runtime_state import PresentationRuntimeBundle
from sofia.avatar.wardrobe import Layer
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def bundle(tmp_path):
    catalog = build_starter_wardrobe()
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits={
            plan.outfit_id: plan.item_ids
            for plan in catalog.presets
        },
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="canonical default",
            hair_color="deep crimson",
            tail_color="dark violet",
            style_tags=("canonical", "engineer"),
        ),
    )
    store = PresentationStore(tmp_path / "sofia.db")
    store.save(authority)
    return PresentationRuntimeBundle(authority, store, catalog)


def persisted_authority(runtime_bundle):
    return runtime_bundle.store.load(
        runtime_bundle.catalog.wardrobe,
        outfits={
            plan.outfit_id: plan.item_ids
            for plan in runtime_bundle.catalog.presets
        },
    )


def test_change_into_bikini_commits_persists_and_updates_matrix(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="change into bikini 4",
        previous_user_content=None,
        operation_id="test.bikini.04",
    )

    assert reply is not None
    assert "Midnight Asymmetric Bikini" in reply
    assert runtime_bundle.authority.current.outfit_id == "swim.bikini.04"

    matrix = runtime_bundle.current_matrix()
    assert (
        matrix.cell(slot="torso", layer=Layer.BASE).garment_id
        == "closet.swim.bikini.04.top"
    )
    assert (
        matrix.cell(slot="pelvis", layer=Layer.BASE).garment_id
        == "closet.swim.bikini.04.bottom"
    )
    persisted = persisted_authority(runtime_bundle)
    assert persisted.current.outfit_id == "swim.bikini.04"
    assert persisted.current.item_ids == runtime_bundle.authority.current.item_ids


def test_take_off_jacket_builds_dynamic_outfit_and_persists_it(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="take off your jacket",
        previous_user_content=None,
        operation_id="test.remove.jacket",
    )

    assert reply is not None
    assert "Asymmetric engineer jacket" in reply
    current = runtime_bundle.authority.current
    assert current.outfit_id.startswith("dynamic.chat.")
    assert "engineer.jacket" not in current.item_ids
    assert runtime_bundle.current_matrix().cell(
        slot="torso",
        layer=Layer.OUTER,
    ) is None

    persisted = persisted_authority(runtime_bundle)
    assert persisted.current.outfit_id == current.outfit_id
    assert "engineer.jacket" not in persisted.current.item_ids


def test_swap_boots_selects_compatible_public_replacement(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="swap your boots",
        previous_user_content=None,
        operation_id="test.swap.boots",
    )

    assert reply is not None
    assert "swapped" in reply
    assert "engineer.boots" not in runtime_bundle.authority.current.item_ids

    matrix = runtime_bundle.current_matrix()
    left = matrix.cell(slot="left_foot", layer=Layer.BASE)
    right = matrix.cell(slot="right_foot", layer=Layer.BASE)
    assert left is not None
    assert right is not None
    assert left.garment_id == right.garment_id
    assert left.garment_id.startswith("closet.normal.footwear.")


def test_hypothetical_does_not_mutate_but_do_it_executes_prior_request(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    original = runtime_bundle.authority.current

    hypothetical = "if i asked you to change into bikini 2 will you"
    reply = service.handle(
        content=hypothetical,
        previous_user_content=None,
        operation_id="test.hypothetical",
    )

    assert reply is not None
    assert "request itself" in reply
    assert runtime_bundle.authority.current == original

    followup = service.handle(
        content="do it",
        previous_user_content=hypothetical,
        operation_id="test.followup",
    )

    assert followup is not None
    assert runtime_bundle.authority.current.outfit_id == "swim.bikini.02"


def test_undress_and_do_it_fail_closed_without_private_grant(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    original = runtime_bundle.authority.current

    hypothetical = "if i asked you to undress will you"
    reply = service.handle(
        content=hypothetical,
        previous_user_content=None,
        operation_id="test.undress.question",
    )
    assert reply is not None
    assert "private presentation" in reply
    assert runtime_bundle.authority.current == original

    followup = service.handle(
        content="do it",
        previous_user_content=hypothetical,
        operation_id="test.undress.followup",
    )
    assert followup is not None
    assert "keeping my current outfit" in followup
    assert runtime_bundle.authority.current == original
    assert persisted_authority(runtime_bundle).current == original


class DeclinePublicChange(WardrobeAutonomyPolicy):
    def decide(self, *, intent, candidate_item_ids, private_only):
        return WardrobeAutonomyDecision(
            False,
            "I prefer to keep this outfit right now",
        )


def test_autonomy_policy_can_decline_public_change_without_mutation(tmp_path):
    runtime_bundle = bundle(tmp_path)
    original = runtime_bundle.authority.current
    service = ClothingActionService(
        runtime_bundle,
        autonomy=DeclinePublicChange(),
    )

    reply = service.handle(
        content="wear bikini 1",
        previous_user_content=None,
        operation_id="test.decline",
    )

    assert reply is not None
    assert "keeping my current outfit" in reply
    assert "prefer to keep this outfit" in reply
    assert runtime_bundle.authority.current == original
    assert persisted_authority(runtime_bundle).current == original


def test_unrelated_text_is_not_a_clothing_action(tmp_path):
    service = ClothingActionService(bundle(tmp_path))

    assert service.handle(
        content="how are you",
        previous_user_content=None,
        operation_id="test.unrelated",
    ) is None
