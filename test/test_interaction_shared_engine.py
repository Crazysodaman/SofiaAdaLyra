"""Offline interaction contract tests: one kernel, no renderer or Ollama."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.model import Embodiment, PhysicalSelf
from sofia.embodiment.store import AvatarStore
from sofia.interaction.core import InteractionEngine, REGISTRY_VERSION

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


@pytest.fixture
def engine():
    return InteractionEngine(AvatarStore(AVATAR).load())


def text(engine, value, *, mid="message-1", stopped=False):
    return engine.from_text(content=value, message_id=mid,
                            session_id="session-1", occurred_at=NOW, stopped=stopped)


def pointer(engine, region, gesture, *, fixture="pointer-1", phase="end", stopped=False):
    return engine.from_lab_pointer(fixture_id=fixture, session_id="session-1",
                                   region_id=region, gesture=gesture, occurred_at=NOW,
                                   phase=phase, stopped=stopped)


@pytest.mark.parametrize("phrase,region,gesture", [
    ("*pats your head*", "head", "pat"),
    ("head pats", "head", "pat"),
    ("*taps your left ear*", "left-ear", "tap"),
    ("*strokes your right ear tip*", "right-ear-tip", "stroke"),
    ("touches your tail base", "tail-base", "touch"),
    ("*holds your right hand*", "right-hand", "hold"),
    ("*pats your left knee*", "left-knee", "pat"),
    ("*touches your left toe*", "left-toe", "touch"),
])
def test_text_and_simulated_avatar_share_exact_semantics_and_policy(engine, phrase, region, gesture):
    written = text(engine, phrase)
    simulated = pointer(engine, region, gesture)
    assert written is not None
    assert written.event.semantics == simulated.event.semantics
    assert written.event.registry_version == simulated.event.registry_version == REGISTRY_VERSION
    assert written.status == simulated.status == "accepted"
    assert written.emotion_options == simulated.emotion_options
    assert written.text_cues == simulated.text_cues
    assert written.event.source == "user_text"
    assert simulated.event.source == "virtual_lab"
    assert written.event.evidence_ref != simulated.event.evidence_ref


def test_registry_covers_canonical_fox_features_and_broad_human_form(engine):
    expected = {"head", "scalp", "hair", "forehead", "face", "left-cheek",
                "nose", "mouth", "lips", "neck", "throat", "left-ear", "right-ear",
                "left-ear-tip", "right-ear-base", "tail", "tail-base", "tail-tip",
                "left-shoulder", "right-forearm", "left-wrist", "right-hand",
                "left-thumb", "right-finger", "torso", "back", "waist", "hips",
                "left-thigh", "right-knee", "left-calf", "right-ankle", "left-foot",
                "right-toe", "chest", "left-breast", "buttocks", "groin", "genitals"}
    assert expected <= engine.regions.keys()
    assert engine.regions["left-ear"].origin == "explicit_fox_anatomy"
    assert engine.regions["left-hand"].origin == "human_form"
    assert all(region.private for region in (engine.regions[r] for r in
               ("chest", "left-breast", "buttocks", "groin", "genitals")))


@pytest.mark.parametrize("phrase", [
    "How do I pat your head?", "I would pat your head", "Don't pat your head",
    "If I touch your ears", "`pats your head`", '"pats your head"',
    "```pats your head```", "I patted your head yesterday",
    "*pats your head*\nhello", "Sofía, are you online?",
    "*pats your head and strokes your tail*",
])
def test_discussion_hypothetical_code_or_multi_action_abstains(engine, phrase):
    assert text(engine, phrase) is None


def test_unspecified_side_unknown_region_and_real_click_are_not_guessed(engine):
    assert text(engine, "*pats your ear*").status == "clarify"
    assert text(engine, "*taps your third ear*").status == "clarify"
    assert pointer(engine, None, "tap").status == "clarify"
    assert pointer(engine, "left-ear", "tap").event.gesture == "tap"
    assert pointer(engine, "left-ear", "tap").event.gesture != "pat"


@pytest.mark.parametrize("region", ["chest", "left-breast", "buttocks", "groin", "genitals", "right-inner-thigh"])
def test_private_regions_are_mapped_but_deny_contact_in_both_modes(engine, region):
    label = region.replace("-", " ")
    written = text(engine, f"*touches your {label}*")
    simulated = pointer(engine, region, "touch")
    assert written is not None
    assert written.event.region_id == region
    assert written.status == simulated.status == "denied"
    assert not written.emotion_options and not simulated.text_cues


def test_stop_cancel_and_partial_phase_never_report_completed_contact(engine):
    assert text(engine, "*pats your head*", stopped=True).status == "denied"
    assert pointer(engine, "head", "pat", phase="cancel").status == "denied"
    assert pointer(engine, "head", "pat", phase="begin").status == "acknowledged"
    assert pointer(engine, "head", "release").status == "acknowledged"
    assert not pointer(engine, "head", "pat", phase="begin").emotion_options


def test_registry_refuses_unmapped_features_and_inconsistent_fox_anatomy():
    with pytest.raises(ValueError, match="Unmapped"):
        InteractionEngine(Embodiment(subject="Sofía", physical_self=PhysicalSelf(
            form="human", additional_features=("wings",))))
    with pytest.raises(ValueError, match="disagree"):
        InteractionEngine(Embodiment(subject="Sofía", physical_self=PhysicalSelf(
            form="human", additional_features=("fox ears",), anatomy=(("ears", "unknown"),))))


def test_distinct_event_ids_do_not_change_semantics(engine):
    a = text(engine, "*pats your head*", mid="first")
    b = text(engine, "*pats your head*", mid="second")
    assert a.event.event_id != b.event.event_id
    assert a.event.semantics == b.event.semantics
    assert a.event.occurred_at == NOW
