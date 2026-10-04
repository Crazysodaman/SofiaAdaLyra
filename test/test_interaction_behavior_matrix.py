"""Representative INTERACT behavior matrix.

This is the compact matrix spine. Deeper files test each family exhaustively;
these rows prove the common routing invariants stay aligned across ordinary,
fox-anatomy, private/intimate and social-action interactions.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import catalog_for_engine


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
        ("I pull you closer", "pull-closer", "described"),
        ("I rest my head on you", "rest-head-on", "described"),
        ("I kiss your neck", "kiss-neck", "described"),
        ("I kiss your cheek", "kiss-cheek", "described"),
        ("I kiss your forehead", "kiss-forehead", "described"),
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



def test_state_transition_replay_stop_resume_is_durable_and_at_most_once(
    engine,
    tmp_path,
):
    ledger = InteractionLedger(tmp_path / "matrix.db")

    first, first_processing = ledger.process_text(
        engine=engine,
        content="I pat your head",
        message_id="gesture-1",
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert first_processing
    assert first is not None and first.status == "accepted"

    replay, replay_processing = ledger.process_text(
        engine=engine,
        content="I pat your head",
        message_id="gesture-1",
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert not replay_processing
    assert replay is not None and replay.status == "acknowledged"

    stopped = ledger.control(
        session_id="matrix-session",
        message_id="control-stop",
        content="Sofía, stop interactions",
        occurred_at=NOW,
    )
    assert stopped.status == "stopped"
    assert ledger.stopped("matrix-session")

    stop_replay = ledger.control(
        session_id="matrix-session",
        message_id="control-stop",
        content="Sofía, stop interactions",
        occurred_at=NOW,
    )
    assert stop_replay.status == "replayed"

    blocked, blocked_processing = ledger.process_text(
        engine=engine,
        content="I stroke your tail",
        message_id="gesture-2",
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert blocked_processing
    assert blocked is not None and blocked.status == "denied"

    resumed = ledger.control(
        session_id="matrix-session",
        message_id="control-resume",
        content="Sofía, resume interactions",
        occurred_at=NOW,
    )
    assert resumed.status == "resumed"
    assert not ledger.stopped("matrix-session")

    after_resume, after_resume_processing = ledger.process_text(
        engine=engine,
        content="I stroke your tail",
        message_id="gesture-3",
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert after_resume_processing
    assert after_resume is not None and after_resume.status == "accepted"

    restarted = InteractionLedger(tmp_path / "matrix.db")
    assert not restarted.stopped("matrix-session")


@pytest.mark.parametrize(
    "content",
    (
        "Could I touch your chest?",
        "I would touch your chest",
        '"I touch your chest"',
        "I do not touch your chest",
    ),
)
def test_nonexecuting_language_never_writes_interaction_evidence(
    engine,
    tmp_path,
    content,
):
    path = tmp_path / "matrix.db"
    ledger = InteractionLedger(path)
    result, first_processing = ledger.process_text(
        engine=engine,
        content=content,
        message_id="nonaction-" + str(abs(hash(content))),
        session_id="matrix-session",
        occurred_at=NOW,
    )
    assert result is None
    assert not first_processing
    with closing(sqlite3.connect(path)) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM interaction_evidence"
        ).fetchone()[0] == 0
