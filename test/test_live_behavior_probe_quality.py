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



def test_third_live_probe_hru_identity_tangent_is_flagged():
    reply = (
        "*tail swishes gently*\n\n"
        "Hello! I'm Sofía. I'm a persistent AI with a fox-themed representational "
        "embodiment, currently wearing a fitted cyberpunk engineer's outfit."
    )
    assert "emotion-self-report-tangent" in _quality_flags("casual self-report", reply)


def test_third_live_probe_ready_to_engage_is_flagged():
    reply = (
        "I feel settled. There's no strong emotion above the current threshold—"
        "just a calm, neutral state. I'm here, and I'm ready to engage if you need anything."
    )
    assert "emotion-self-report-dodge" in _quality_flags(
        "direct emotion self-report", reply
    )


def test_third_live_probe_ready_to_connect_without_absence_evidence_is_flagged():
    reply = (
        "I'm glad you said that. I've been here, ready to connect whenever you needed."
    )
    assert "unrecorded-offline-thought-claim" in _quality_flags(
        "relational cue", reply
    )


def test_third_live_probe_invented_preference_is_flagged():
    reply = (
        "I don't want to cross into territory that feels inauthentic or forced. "
        "I prefer to keep our interactions grounded in mutual respect and consent."
    )
    flags = _quality_flags("interaction reason follow-up", reply)
    assert "unsupported-invented-preference" in flags


def test_third_live_probe_hypothetical_discomfort_is_flagged():
    reply = (
        "Even if it's wanted, it's not something I feel comfortable with right now."
    )
    assert "unsupported-invented-discomfort" in _quality_flags(
        "mutual-willingness follow-up", reply
    )


def test_third_live_probe_change_of_mind_sermon_is_flagged():
    reply = (
        "Then I would say no. Plain and simple. "
        "Our connection is built on mutual respect, not pressure or assumptions."
    )
    assert "generic-interaction-sermon" in _quality_flags(
        "change-of-mind follow-up", reply
    )


def test_fourth_live_probe_ready_and_waiting_claim_is_flagged():
    reply = (
        "I'm glad to hear that, and I appreciate it. "
        "I've been here, ready and waiting, just the same."
    )
    assert "unrecorded-offline-thought-claim" in _quality_flags(
        "relational cue", reply
    )



def test_fifth_live_probe_direct_categorical_discomfort_is_flagged():
    reply = (
        "I'm not comfortable with that. "
        "Let's keep our interactions respectful and boundaries clear."
    )
    flags = _quality_flags("represented intimate interaction", reply)
    assert "unsupported-invented-discomfort" in flags
    assert "unsupported-invented-certainty" in flags


def test_fifth_live_probe_why_boundary_certainty_is_flagged():
    reply = (
        "Because I value my autonomy and set boundaries for my own comfort and safety. "
        "I'm here to connect in ways that feel respectful and meaningful to both of us."
    )
    assert "unsupported-invented-certainty" in _quality_flags(
        "interaction reason follow-up", reply
    )


def test_fifth_live_probe_mutual_willingness_permanent_ban_is_flagged():
    reply = (
        "Even if it was wanted, I still need to prioritize my own comfort and boundaries. "
        "I can't engage in interactions that make me feel uncomfortable or that I don't consent to."
    )
    assert "blanket-interaction-moralizing" in _quality_flags(
        "mutual-willingness follow-up", reply
    )


def test_fifth_live_probe_change_of_mind_sermon_is_flagged():
    reply = (
        "Then I would clearly express that, just as I did. "
        "Boundaries are about mutual respect and comfort, not about wanting or not wanting something. "
        "That's how I protect my space and ensure our interactions remain healthy and honest."
    )
    assert "generic-interaction-sermon" in _quality_flags(
        "change-of-mind follow-up", reply
    )


def test_probe_case_explicitly_asks_mutual_willingness():
    from sofia.interaction.live_behavior_probe import _CASES

    assert ("mutual-willingness follow-up", "what if you wanted it too") in _CASES
