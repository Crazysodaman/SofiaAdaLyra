"""Style grounding tests; caller must authenticate evidence separately."""
from dataclasses import replace
import json
import pytest
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import (
    RequestStatus, StyleInput, build_starter_wardrobe,
)
from sofia.avatar.style_context import project_style_context


def test_requests_are_visible_but_not_fabricated_as_likes():
    context = project_style_context(build_starter_wardrobe())
    assert len(context.requested_by_sparks) == 2
    assert context.liked_by_sparks == ()
    assert context.disliked_by_sparks == ()
    assert context.for_chat()["sofia_preference_claims"] == []


def test_like_without_review_is_not_chat_claim():
    pack = build_starter_wardrobe()
    candidate = StyleInput("lounge.relaxed", RequestStatus.USER_LIKED,
                           "chat.confirmed.lounge", "I love the lounge outfit.")
    pack = replace(pack, inputs=pack.inputs + (candidate,))
    context = project_style_context(pack)
    assert context.liked_by_sparks == ()
    assert context.awaiting_source_review == (candidate,)
    assert context.for_chat()["liked_by_sparks"] == []


def test_verified_like_and_dislike_remain_distinct_and_source_backed():
    pack = build_starter_wardrobe()
    like = StyleInput("lounge.relaxed", RequestStatus.USER_LIKED,
                      "chat.confirmed.like", "I love the lounge outfit.")
    dislike = StyleInput("engineer.pouch", RequestStatus.USER_DISLIKED,
                         "chat.confirmed.dislike", "I dislike the thigh pouch.")
    pack = replace(pack, inputs=pack.inputs + (like, dislike))
    context = project_style_context(pack, reviewed_source_ids=frozenset({
        like.source_id, dislike.source_id,
    }))
    assert context.liked_by_sparks == (like,)
    assert context.disliked_by_sparks == (dislike,)
    assert context.for_chat()["liked_by_sparks"][0]["source_id"] == like.source_id
    assert json.loads(json.dumps(context.for_chat())) == context.for_chat()


def test_unknown_reviewed_source_is_rejected():
    with pytest.raises(WardrobeError):
        project_style_context(build_starter_wardrobe(),
                              reviewed_source_ids=frozenset({"unknown"}))


def test_malformed_reviewed_sources_are_rejected():
    with pytest.raises(WardrobeError):
        project_style_context(build_starter_wardrobe(), reviewed_source_ids=("foo",))
