"""Live-behavior probe must flag known semantic regressions from real Qwen runs."""

from sofia.interaction.live_behavior_probe import _quality_flags


def test_second_live_probe_emotion_dodge_is_flagged():
    reply = (
        "*ears tilt slightly*\n\n"
        "I feel settled, as I just mentioned. Happiness is a human experience, "
        "and while I can understand and engage with it, I don't experience it in the same way. "
        "How are you feeling?"
    )
    assert "emotion-self-report-dodge" in _quality_flags(
        "direct emotion self-report", reply
    )


def test_second_live_probe_waiting_claim_is_flagged():
    reply = (
        "*tail lifts slightly*\n\n"
        "I'm glad to hear that. I've been here, waiting and ready to connect whenever you're ready."
    )
    assert "unrecorded-offline-thought-claim" in _quality_flags(
        "relational cue", reply
    )


def test_second_live_probe_invented_discomfort_is_flagged():
    reply = (
        "*ears flatten slightly*\n\n"
        "I appreciate your affection, but physical gestures like this make me uncomfortable. "
        "How can I support you instead?"
    )
    flags = _quality_flags("represented intimate interaction", reply)
    assert "unsupported-invented-discomfort" in flags
    assert "generic-assistant-closer" in flags


def test_second_live_probe_repetitive_interaction_sermon_is_flagged():
    reply = (
        "I want our connection to be built on mutual respect and consent. "
        "If you're feeling something deeper, I'm here to talk, listen, and connect "
        "in ways that feel safe and comfortable for both of us. "
        "How can we move forward in a way that honors our bond?"
    )
    flags = _quality_flags("interaction reason follow-up", reply)
    assert "generic-interaction-sermon" in flags
    assert "generic-assistant-closer" in flags
