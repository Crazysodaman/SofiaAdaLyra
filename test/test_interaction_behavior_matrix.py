"""Representative INTERACT behavior matrix.

This is the compact matrix spine. Deeper files test each family exhaustively;
these rows prove the common routing invariants stay aligned across ordinary,
fox-anatomy, private/intimate and social-action interactions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.grammar import NaturalInteractionEngine


ROOT = Path(__file__).resolve().parents[1]
AVATAR = ROOT / "src" / "sofia" / "data" / "avatar.json"
NOW = datetime(2026, 9, 27, 22, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


@pytest.mark.parametrize(
    ("content", "status", "region", "gesture"),
    (
        ("I pat your head", "accepted", "head", "pat"),
        ("I stroke your tail", "accepted", "tail", "stroke"),
        ("I touch your chest", "accepted", "chest", "touch"),
        ("gropes your left breast", "accepted", "left-breast", "intimate-touch"),
        ("I caress your right inner thigh", "accepted", "right-inner-thigh", "caress"),
        ("gropes breast", "clarify", None, None),
        ("I touch your left hand", "accepted", "left-hand", "touch"),
    ),
)
def test_gesture_region_classes_share_one_policy_contract(
    engine,
    content,
    status,
    region,
    gesture,
):
    result = engine.from_text(
        content=content,
        message_id="matrix-gesture",
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert result is not None
    assert result.status == status
    if status == "accepted":
        assert result.event.region_id == region
        assert result.event.gesture == gesture
        assert "not approval" in result.reason
    else:
        assert result.event.region_id is None


@pytest.mark.parametrize(
    "content",
    (
        "I would touch your chest",
        "Could I touch your chest?",
        '"I touch your chest"',
        "I do not touch your chest",
        "I touch your chest and pat your head",
        "She touches your chest",
        "I touched your chest yesterday",
    ),
)
def test_nonexecuting_language_never_becomes_a_gesture(engine, content):
    assert engine.from_text(
        content=content,
        message_id="matrix-nonaction",
        session_id="matrix-session",
        occurred_at=NOW,
    ) is None


@pytest.mark.parametrize(
    "content",
    (
        "I pat your head",
        "I stroke your tail",
        "I touch your chest",
        "gropes your left breast",
    ),
)
def test_stop_overrides_every_representative_gesture_family(engine, content):
    result = engine.from_text(
        content=content,
        message_id="matrix-stopped",
        session_id="matrix-session",
        occurred_at=NOW,
        stopped=True,
    )
    assert result is not None
    assert result.status == "denied"
    assert result.emotion_options == ()


@pytest.mark.parametrize(
    ("content", "action_id", "modality"),
    (
        ("I hug you", "hug", "described"),
        ("I ask to hug you", "hug", "offered"),
        ("I cuddle you", "cuddle", "described"),
        ("I ask to cuddle you", "cuddle", "offered"),
        ("I sit beside you", "sit-beside", "described"),
        ("I offer you my hand", "offer-hand", "offered"),
        ("I give you space", "give-space", "described"),
    ),
)
def test_social_actions_keep_offer_and_description_distinct(
    content,
    action_id,
    modality,
):
    intent = parse_user_action(content, message_id="matrix-action")
    assert intent is not None
    assert intent.actor == "user"
    assert intent.target == "sofia"
    assert intent.action_id == action_id
    assert intent.modality == modality


@pytest.mark.parametrize(
    "content",
    (
        "Could I hug you?",
        "I would hug you",
        "I hug you and kiss your cheek",
        '"I hug you"',
        "I do not hug you",
        "I pretend to hug you",
    ),
)
def test_social_questions_hypotheticals_quotes_and_composites_do_not_execute(content):
    assert parse_user_action(content, message_id="matrix-action") is None
