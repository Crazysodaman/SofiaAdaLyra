"""Bounded participation policy tests: relevance, silence, caps and controls."""
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.routing import (
    ParticipationAction,
    ParticipationRouter,
    RoutingLimits,
)
from sofia.platform.chat import ChatActor, ChatEngine, CoreIdentity


NOW = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=NOW):
        self.now_value = now

    def __call__(self):
        return self.now_value

    def advance(self, delta):
        self.now_value += delta


@pytest.fixture
def engine(tmp_path):
    path = tmp_path / "routing.db"
    with sqlite3.connect(path):
        pass
    return ChatEngine(path, owner_id="platform:owner", clock=lambda: NOW)


def core(name):
    return CoreIdentity(uuid4(), f"platform:{name.lower()}", 1, name)


def message(engine, index, body="hello"):
    return engine.send(
        engine.owner_actor(), "general", body, idempotency_key=f"message-{index}"
    )


def router(**overrides):
    values = dict(
        relevance_threshold=0.5,
        cooldown=timedelta(0),
        rate_window=timedelta(minutes=1),
        max_responses_per_window=10,
        duplicate_window=timedelta(minutes=2),
        loop_repeat_threshold=3,
        max_chain_turns=6,
    )
    values.update(overrides)
    limits = RoutingLimits(**values)
    return ParticipationRouter(
        clock=Clock(), limits=limits
    )


def test_relevance_selects_subset_and_explicit_mention_overrides(engine):
    ada, bea, cy = core("Ada"), core("Bea"), core("Cy")
    ids = [ada.core_id_text, bea.core_id_text, cy.core_id_text]
    policy = router()

    first = policy.evaluate(
        trigger=message(engine, 1),
        candidates=ids,
        relevance={ada.core_id_text: 0.9, bea.core_id_text: 0.2, cy.core_id_text: 0.6},
        chain_id="chain:rel",
    )
    by_core = {item.core_id: item for item in first}
    assert by_core[ada.core_id_text].action is ParticipationAction.RESPOND
    assert by_core[cy.core_id_text].action is ParticipationAction.RESPOND
    assert by_core[bea.core_id_text].action is ParticipationAction.SILENCE

    second = policy.evaluate(
        trigger=message(engine, 2, "Bea, take this one"),
        candidates=ids,
        mentions=[bea.core_id_text],
        relevance={ada.core_id_text: 0.9, bea.core_id_text: 0.0, cy.core_id_text: 0.6},
        chain_id="chain:mention",
    )
    by_core = {item.core_id: item for item in second}
    assert by_core[bea.core_id_text].action is ParticipationAction.RESPOND
    assert by_core[bea.core_id_text].mentioned is True
    assert by_core[ada.core_id_text].action is ParticipationAction.RESPOND


def test_decline_availability_preference_and_budget_all_silence(engine):
    ada, bea = core("Ada"), core("Bea")
    ids = [ada.core_id_text, bea.core_id_text]
    policy = router()
    policy.set_declined(bea.core_id_text)
    policy.set_budget(ada.core_id_text, 0)

    decisions = policy.evaluate(
        trigger=message(engine, 1),
        candidates=ids,
        mentions=ids,
        chain_id="chain:controls",
    )
    by_core = {item.core_id: item for item in decisions}
    assert by_core[bea.core_id_text].action is ParticipationAction.DECLINE
    assert by_core[ada.core_id_text].action is ParticipationAction.SILENCE
    assert "budget" in by_core[ada.core_id_text].reason

    policy.set_declined(bea.core_id_text, False)
    policy.set_budget(ada.core_id_text, 2)
    policy.set_availability(bea.core_id_text, False)
    decisions = policy.evaluate(
        trigger=message(engine, 2),
        candidates=ids,
        mentions=ids,
        chain_id="chain:availability",
    )
    by_core = {item.core_id: item for item in decisions}
    assert by_core[bea.core_id_text].action is ParticipationAction.SILENCE
    assert "unavailable" in by_core[bea.core_id_text].reason

    policy.set_availability(ada.core_id_text, True)
    policy.set_preference(ada.core_id_text, muted=True)
    decisions = policy.evaluate(
        trigger=message(engine, 3),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:mute",
    )
    assert decisions[0].action is ParticipationAction.SILENCE
    assert "mutes" in decisions[0].reason


def test_cooldown_and_rate_limit_defer_without_speaking(engine):
    ada = core("Ada")
    policy = router(cooldown=timedelta(minutes=10))
    first = policy.evaluate(
        trigger=message(engine, 1),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:cooldown",
    )
    assert first[0].action is ParticipationAction.RESPOND
    policy.record_response(ada.core_id_text, chain_id="chain:cooldown", body="one")

    second = policy.evaluate(
        trigger=message(engine, 2),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:cooldown",
    )
    assert second[0].action is ParticipationAction.DEFER
    assert second[0].defer_until is not None

    limited = router(
        cooldown=timedelta(0),
        max_responses_per_window=1,
        rate_window=timedelta(hours=1),
    )
    beat = core("Beat")
    first = limited.evaluate(
        trigger=message(engine, 3),
        candidates=[beat.core_id_text],
        mentions=[beat.core_id_text],
        chain_id="chain:rate",
    )
    assert first[0].action is ParticipationAction.RESPOND
    limited.record_response(beat.core_id_text, chain_id="chain:rate", body="one")
    second = limited.evaluate(
        trigger=message(engine, 4),
        candidates=[beat.core_id_text],
        mentions=[beat.core_id_text],
        chain_id="chain:rate",
    )
    assert second[0].action is ParticipationAction.DEFER
    assert "rate" in second[0].reason


def test_duplicate_delivery_and_duplicate_content_are_suppressed(engine):
    ada = core("Ada")
    policy = router()
    trigger = message(engine, 1)

    first = policy.evaluate(
        trigger=trigger,
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:duplicate",
    )
    assert first[0].action is ParticipationAction.RESPOND
    again = policy.evaluate(
        trigger=trigger,
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:duplicate",
    )
    assert again[0].action is ParticipationAction.SUPPRESSED_DUPLICATE

    assert policy.content_is_duplicate(ada.core_id_text, "same words") is False
    policy.record_response(
        ada.core_id_text,
        chain_id="chain:duplicate",
        body="same words",
    )
    assert policy.content_is_duplicate(ada.core_id_text, "  same   words ") is True


def test_loop_detection_stops_repeated_and_overlong_chains(engine):
    ada = core("Ada")
    repeated = router(loop_repeat_threshold=2)
    first = repeated.evaluate(
        trigger=message(engine, 1, "echo echo"),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:loop",
    )
    assert first[0].action is ParticipationAction.RESPOND
    second = repeated.evaluate(
        trigger=message(engine, 2, "echo echo"),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:loop",
    )
    assert second[0].action is ParticipationAction.LOOP_DETECTED

    bounded = router(max_chain_turns=2)
    for index in range(2):
        decision = bounded.evaluate(
            trigger=message(engine, 10 + index, f"turn {index}"),
            candidates=[ada.core_id_text],
            mentions=[ada.core_id_text],
            chain_id="chain:bounded",
        )
        assert decision[0].action is ParticipationAction.RESPOND
        bounded.record_response(
            ada.core_id_text,
            chain_id="chain:bounded",
            body=f"reply {index}",
        )
    final = bounded.evaluate(
        trigger=message(engine, 20, "one too many"),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:bounded",
    )
    assert final[0].action is ParticipationAction.LOOP_DETECTED


def test_owner_can_cancel_chains_terminate_cores_and_control_notification(engine):
    ada, bea = core("Ada"), core("Bea")
    ids = [ada.core_id_text, bea.core_id_text]
    policy = router()
    policy.cancel_chain("chain:cancelled")
    cancelled = policy.evaluate(
        trigger=message(engine, 1),
        candidates=ids,
        mentions=ids,
        chain_id="chain:cancelled",
    )
    assert {item.action for item in cancelled} == {ParticipationAction.CANCELLED}

    policy.terminate(ada.core_id_text)
    policy.set_notification(bea.core_id_text, False)
    terminated = policy.evaluate(
        trigger=message(engine, 2),
        candidates=ids,
        mentions=ids,
        chain_id="chain:terminated",
    )
    by_core = {item.core_id: item for item in terminated}
    assert by_core[ada.core_id_text].action is ParticipationAction.TERMINATED
    assert by_core[bea.core_id_text].notify is False

    policy.terminate_all()
    stopped = policy.evaluate(
        trigger=message(engine, 3),
        candidates=[bea.core_id_text],
        mentions=[bea.core_id_text],
        chain_id="chain:all",
    )
    assert stopped[0].action is ParticipationAction.TERMINATED
    policy.resume_all()
    resumed = policy.evaluate(
        trigger=message(engine, 4),
        candidates=[bea.core_id_text],
        mentions=[bea.core_id_text],
        chain_id="chain:all",
    )
    assert resumed[0].action is ParticipationAction.RESPOND


def test_bounded_slots_commitments_and_preferences_schedule_fairly(engine):
    ada, bea = core("Ada"), core("Bea")
    ids = [ada.core_id_text, bea.core_id_text]
    policy = router(max_cores_per_message=1)
    decisions = policy.evaluate(
        trigger=message(engine, 1),
        candidates=ids,
        relevance={ada.core_id_text: 0.9, bea.core_id_text: 0.8},
        chain_id="chain:slot",
    )
    responding = [item for item in decisions if item.should_respond]
    assert len(responding) == 1
    assert responding[0].core_id == ada.core_id_text
    assert responding[0].rank == 0

    committed = router()
    committed.set_commitment(bea.core_id_text, "release")
    decisions = committed.evaluate(
        trigger=message(engine, 2),
        candidates=ids,
        relevance={ada.core_id_text: 0.0, bea.core_id_text: 0.0},
        topics=["release"],
        chain_id="chain:commitment",
    )
    by_core = {item.core_id: item for item in decisions}
    assert by_core[bea.core_id_text].action is ParticipationAction.RESPOND
    assert "commitment" in by_core[bea.core_id_text].reason
    assert by_core[ada.core_id_text].action is ParticipationAction.SILENCE

    weighted = router()
    weighted.set_preference(ada.core_id_text, weight=0.1)
    decisions = weighted.evaluate(
        trigger=message(engine, 3),
        candidates=[ada.core_id_text],
        relevance={ada.core_id_text: 0.9},
        chain_id="chain:weight",
    )
    assert decisions[0].action is ParticipationAction.SILENCE
    assert "relevance" in decisions[0].reason


def test_router_decisions_never_carry_execution_authority(engine):
    ada = core("Ada")
    policy = router()
    decision = policy.evaluate(
        trigger=message(engine, 1),
        candidates=[ada.core_id_text],
        mentions=[ada.core_id_text],
        chain_id="chain:authority",
    )[0]
    assert decision.grants_authority is False
    assert decision.execution_authority is False
    status = policy.status(ada.core_id_text)
    assert status.core_id == ada.core_id_text
    assert status.remaining_budget == policy.limits.default_budget
