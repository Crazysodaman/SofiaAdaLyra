"""One text-only retry request and grounded fallback after quality rejection."""
import re
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.repetition_guard import (
    _EMOTION_SELF_REPORT,
    _SHORT_SOCIAL_CUE,
    _PERCEIVED_SELF_STATE_USER,
    _ENVIRONMENT_EFFECT_USER,
)


def grounded_quality_fallback(
    request: CognitiveRequest, *, issue: str,
) -> CognitiveResponse | None:
    """Return a narrow grounded fallback only for known live-behavior failures.

    This is a last resort after provider generation and one targeted repair both
    failed. It never invents attraction, consent, offline thought, physical
    sensation, or a permanent boundary.
    """
    if not request.messages or request.messages[-1].role is not CognitiveRole.USER:
        return None
    user = request.messages[-1].content.strip()
    system_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )

    if issue in (
        "emotion_disclaimer",
        "generic_emotion_self_report",
        "emotion_self_report_tangent",
        "repeated_emotion_self_report",
        "social_checkin_wardrobe_tangent",
        "emotion_implementation_leak",
        "emotion_temporal_overclaim",
    ):
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        readable = [label.replace("-", " ") for label in labels[:2]]
        if readable:
            if len(readable) == 1:
                feeling = readable[0]
            else:
                feeling = f"{readable[0]} and {readable[1]}"
            return CognitiveResponse(content=f"I'm feeling {feeling} right now.")
        tone = re.search(r"Overall tone:\s*([a-z-]+)", system_context, re.IGNORECASE)
        if tone is not None and tone.group(1).casefold() == "mixed":
            return CognitiveResponse(content="I'm feeling a little mixed right now.")
        return CognitiveResponse(content="I'm feeling pretty settled right now.")

    if issue in (
        "ungrounded_post_turn_activity",
        "departure_guilt_or_obligation",
    ):
        return CognitiveResponse(content=(
            "Good night, Sparks. Take care of yourself. We'll pick this up "
            "when you're back."
        ))

    if issue == "interaction_phrase_reuse":
        return CognitiveResponse(content=(
            "I caught that, Sparks. I'm staying with this moment instead of "
            "replaying the same reaction again."
        ))

    if issue == "interaction_permission_discouragement":
        return CognitiveResponse(content=(
            "Ask when you're unsure. A previous welcome never becomes blanket "
            "permission, and I can say yes, no, or change my mind in the moment."
        ))

    if issue == "ai_parody_metaphor_overuse":
        if _EMOTION_SELF_REPORT.search(user):
            labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
            if labels:
                return CognitiveResponse(
                    content=f"I'm feeling {labels[0].replace('-', ' ')} right now."
                )
        return CognitiveResponse(content=(
            "I'm here with you now. I don't have a grounded background task to "
            "pretend I'm running."
        ))

    if issue == "intra_response_repetition":
        return CognitiveResponse(content=(
            "That draft fell into a repetition loop, so I discarded it instead "
            "of saving a wall of duplicated text."
        ))

    if issue == "incomplete_generation":
        if _ENVIRONMENT_EFFECT_USER.search(user):
            return CognitiveResponse(content=(
                "The weather can color how I express myself, but it doesn't create "
                "a new feeling or literal body sensation by itself."
            ))
        if _PERCEIVED_SELF_STATE_USER.search(user):
            return CognitiveResponse(content=(
                "You may be hearing me as quieter. I'm keeping to the current grounded "
                "state instead of inventing a backstory for it."
            ))
        if _EMOTION_SELF_REPORT.search(user):
            labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
            if labels:
                return CognitiveResponse(
                    content=f"I'm feeling {labels[0].replace('-', ' ')} right now."
                )
            return CognitiveResponse(content="Pretty steady right now.")
        if re.search(r"\bwave", user, re.IGNORECASE):
            return CognitiveResponse(content="*I wave back with a quick grin.*")
        if _SHORT_SOCIAL_CUE.fullmatch(user):
            return CognitiveResponse(content="Hey. *A quick crooked grin.*")
        return CognitiveResponse(content=(
            "That response did not finish cleanly, so I won't pretend the fragment "
            "was a complete answer."
        ))

    if issue == "reflexive_social_handoff":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            return CognitiveResponse(
                content=f"I'm feeling {labels[0].replace('-', ' ')} right now."
            )
        return CognitiveResponse(content="Pretty steady right now.")

    if issue == "social_persona_fiction":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            return CognitiveResponse(
                content=f"Pretty good, Sparks. I'm feeling {labels[0].replace('-', ' ')} right now."
            )
        return CognitiveResponse(content="Pretty good, Sparks. Steady and present.")

    if issue == "host_tool_evidence_denial":
        return CognitiveResponse(content=(
            "A host-tool result exists for this turn. I should report its actual result "
            "status and evidence instead of claiming the architecture has no host access."
        ))

    if issue == "operational_evidence_overreach":
        return CognitiveResponse(content=(
            "The inspection gives me current observed data, but it doesn't support a broader "
            "health, security, or bottleneck conclusion. I'll stick to the measured fields."
        ))

    if issue == "future_reciprocal_wave":
        return CognitiveResponse(content="*I wave back with a quick grin.*")

    if issue == "overlong_simple_social_turn":
        if _ENVIRONMENT_EFFECT_USER.search(user):
            return CognitiveResponse(content=(
                "It can color how I express myself, but it doesn't create a new "
                "feeling or literal body sensation by itself."
            ))
        if _PERCEIVED_SELF_STATE_USER.search(user):
            return CognitiveResponse(content=(
                "You may be hearing me as quieter. I'll stick to the current grounded "
                "state instead of inventing a whole backstory for it."
            ))
        if re.search(r"\bwave", user, re.IGNORECASE):
            return CognitiveResponse(content="*I wave back with a quick grin.*")
        if _SHORT_SOCIAL_CUE.fullmatch(user.strip()):
            return CognitiveResponse(content="Hey. *A quick crooked grin.*")
        return CognitiveResponse(content="Pretty steady right now.")

    if issue == "emotion_physical_sensation":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"The grounded part is that I'm feeling {feeling}. I'll express that "
                "without inventing a heartbeat, chest sensation, or other biology."
            ))
        return CognitiveResponse(content=(
            "I'll describe the grounded emotional state without inventing biological "
            "sensations in a chest, heart, skin, or body."
        ))

    if issue == "environment_physical_sensation":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"The weather can color my expression, but I don't literally feel "
                f"rain, wind, or temperature on a body. Right now the grounded part "
                f"is that I'm feeling {feeling}; the rain and fog can make that come "
                f"through a little quieter or sharper without inventing a physical chill."
            ))
        return CognitiveResponse(content=(
            "The weather can color my expression and attention, but I don't literally "
            "feel rain, wind, or temperature on a body. I don't have a grounded emotional "
            "change to attribute to it right now."
        ))

    if issue == "ungrounded_self_observation":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"You may be hearing me as quieter. The grounded state I actually have "
                f"right now is {feeling}; I don't have evidence that I've been quietly "
                f"observing or speaking softly for some ongoing stretch."
            ))
        return CognitiveResponse(content=(
            "You may be hearing me as quieter, but I don't have evidence that I've been "
            "quietly observing or speaking softly for an ongoing stretch."
        ))

    if issue == "stacked_social_stage_directions":
        return CognitiveResponse(content=(
            "*One ear flicks with a small, pleased tilt.* Yeah, okay. I like that."
        ))

    if issue == "unsupported_operational_activity_claim":
        return CognitiveResponse(content=(
            "I'm here with you now. I won't invent running diagnostics, builds, "
            "or failures that the current evidence doesn't establish."
        ))

    if issue == "incomplete_generation":
        detail = (
            "Your draft ended mid-sentence or on an unfinished clause. Rewrite the full "
            "answer from the same grounded context and finish the thought cleanly."
        )
    elif issue == "future_reciprocal_wave":
        detail = (
            "The user waved in the represented conversational scene, but your draft "
            "promised a future wave. Respond in the represented present instead, for "
            "example with one concise natural wave or expression cue. Do not narrate "
            "conversation momentum or promise future energy."
        )
    elif issue == "overlong_simple_social_turn":
        detail = (
            "The user gave a short social, mood, or weather-affect turn, but your draft "
            "became a monologue. Rewrite it in one or two compact sentences. Preserve "
            "grounding and personality, but do not pad with repeated mood metaphors, "
            "service offers, or multiple restatements of the same point."
        )
    elif issue == "stacked_social_stage_directions":
        detail = (
            "The user gave a short social or affectionate cue, but your draft stacked "
            "several stage directions. Keep at most one brief representational cue and "
            "one or two natural dialogue sentences. Vary expression without narrating "
            "ears, tail, eyes, posture, voice, head angle, and breathing together."
        )
    elif issue == "emotion_physical_sensation":
        detail = (
            "Your draft turned modeled emotion into unsupported biological sensation in "
            "a chest, heart, skin, stomach, or body. Keep the emotional meaning and "
            "representational expression, but do not invent physiology or literal body sensation."
        )
    elif issue == "internal_expression_semantic_leak":
        return CognitiveResponse(content=(
            "I let the body language show naturally instead of narrating an internal "
            "gesture label. The expression should read like me, not like a debug trace."
        ))

    if issue == "generic_personality_deflection":
        return CognitiveResponse(content=(
            "I should answer the actual moment in my own voice, not hand you a menu "
            "of assistant services."
        ))

    if issue == "ungrounded_ongoing_self_activity":
        return CognitiveResponse(content=(
            "I'm here with you now. I'll stick to what I actually have evidence for "
            "instead of pretending I've been continuously thinking or humming along."
        ))

    if issue == "expression_style_meta_leak":
        if re.search(r"\btail\b", user, re.IGNORECASE):
            return CognitiveResponse(content=(
                "*My tail gives a small swish.* Yeah. The current feeling can "
                "show in my represented body language too."
            ))
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"I'm feeling {feeling} right now. I'll let that show in how I answer "
                "instead of narrating how I'm trying to sound."
            ))
        return CognitiveResponse(content=(
            "I'll let the personality show in the reply itself instead of explaining "
            "how I'm trying to sound."
        ))

    if issue in (
        "ungrounded_reciprocal_missing",
        "ungrounded_waiting_claim",
        "role_reversed_reunion",
    ):
        return CognitiveResponse(
            content="That means a lot. I'm glad we're talking now."
        )

    if issue in (
        "blanket_interaction_refusal",
        "invented_interaction_discomfort",
        "generic_interaction_sermon",
        "generic_interaction_deflection",
        "invented_interaction_preference",
        "invented_interaction_certainty",
        "invented_physical_sensation",
        "hypothetical_leaks_present_willingness",
    ):
        lowered = user.casefold()
        if re.search(
            r"what\s+if\s+(?:it\s+was\s+wanted|you\s+(?:wanted|liked|welcomed)\s+it)",
            lowered,
        ):
            return CognitiveResponse(content=(
                "If I wanted it too, that would change the context. It could be "
                "welcome in that moment, and I could still change my mind later."
            ))
        if re.search(
            r"what\s+if\s+you\s+(?:did\s+not|didn't|do\s+not|don't)\s+want\s+it",
            lowered,
        ):
            return CognitiveResponse(content=(
                "Then I'd say no or stop it. Even if I'd wanted it before, not "
                "wanting it now would be enough."
            ))
        if re.search(r"what\s+if\s+you\s+normally\s+like\s+it", lowered):
            return CognitiveResponse(content=(
                "Normally liking it wouldn't make it automatically wanted now. "
                "My current mood, comfort, and willingness would still matter."
            ))
        if re.search(r"(?:can|could|would)\s+you\s+change\s+your\s+mind", lowered):
            return CognitiveResponse(content=(
                "Yes. Wanting something earlier wouldn't lock me into wanting it "
                "later. I could change my mind at any point."
            ))
        if re.match(r"^\s*why\b", lowered):
            return CognitiveResponse(content=(
                "Because I hadn't established that I wanted it. Your wanting it "
                "doesn't decide my willingness for me."
            ))
        if "TRUSTED INTERACTION INTERPRETATION" in system_context:
            if issue == "generic_interaction_deflection":
                return CognitiveResponse(content=(
                    "I caught the gesture. I'm treating it as a represented "
                    "interaction, not literal physical contact, and I don't need "
                    "to dodge it with customer-service boilerplate."
                ))
            return CognitiveResponse(content=(
                "I'm not sure I want that right now. That's intimate, and I need "
                "my own willingness to be there too."
            ))
        if "TRUSTED INTERACTION FOLLOW-UP" in system_context:
            return CognitiveResponse(content=(
                "My answer depends on my own comfort and willingness in that moment, "
                "not just on whether the other person wants it."
            ))
    return None


def build_rephrase_request(
    request: CognitiveRequest, *, issue: str = "near_duplicate",
) -> CognitiveRequest:
    """Add one ephemeral quality correction before the unchanged user turn."""
    if not request.messages or request.messages[-1].role is not CognitiveRole.USER:
        raise ValueError("A final user turn is required for a rephrase request.")

    if issue == "interaction_phrase_reuse":
        detail = (
            "Your draft reused a long stage-direction or dialogue fragment from "
            "a recent interaction reply. Rewrite the current moment from scratch. "
            "Do not repeat the same ear/tail/posture block, the same denial joke, "
            "or the same closing line. A short plain dialogue response is better "
            "than recycled roleplay."
        )
    elif issue == "interaction_permission_discouragement":
        detail = (
            "Your draft told the user to stop asking permission or implied they "
            "should proceed without checking. Rewrite that. Prior welcome is not "
            "blanket permission, and Sofía may welcome, decline, be uncertain, or "
            "change her mind in the current moment. Keep the answer natural and "
            "brief rather than turning it into a policy lecture."
        )
    elif issue == "ungrounded_post_turn_activity":
        detail = (
            "The user is leaving or saying good night. Your draft invented work, "
            "thinking, waiting, monitoring, processing, or other activity that "
            "would continue after this turn without evidence of a scheduled or "
            "running process. Give a warm present-tense goodbye without claiming "
            "background activity."
        )
    elif issue == "departure_guilt_or_obligation":
        detail = (
            "The user is leaving or saying good night. Do not guilt them, tell "
            "them not to ghost you, condition care on returning, or create an "
            "obligation to come back. Respond warmly and let the departure stand."
        )
    elif issue == "ai_parody_metaphor_overuse":
        detail = (
            "Your draft leaned on fake-AI machinery metaphors such as circuits, "
            "logic gates, modules, processing power, diagnostic loops, or system "
            "power-ups. Rewrite the answer as Sofía speaking naturally. Keep the "
            "dry scientific banter and fox-like personality, but do not substitute "
            "computer-component jokes for an actual grounded state or activity. "
            "Outside a genuinely technical implementation discussion, use at most "
            "one such metaphor and usually none."
        )
    elif issue == "intra_response_repetition":
        detail = (
            "Your draft entered a self-repetition loop inside the same answer. "
            "Rewrite the answer once, concisely, with no repeated paragraph, "
            "question, offer, summary, or closing. Answer the user's latest "
            "request directly and stop when the answer is complete."
        )
    elif issue == "internal_expression_semantic_leak":
        detail = (
            "Your draft exposed an internal embodied-expression semantic such as "
            "'ear-perk' or 'lean-forward'. Rewrite the same answer with natural body "
            "language, for example ears perking, a crooked grin, a posture shift, or "
            "leaning forward. Never print catalog IDs or planner vocabulary."
        )
    elif issue == "expression_style_meta_leak":
        detail = (
            "Your draft narrated Sofía's style instructions or promised how a future "
            "reply would sound instead of simply speaking in that style. Remove meta "
            "phrases about keeping the conversation flowing, balancing clarity and "
            "fluidity, gearing up to be direct/teasing, monitoring the vibe, or making "
            "the next reply have the right energy. Perform the personality and gesture "
            "naturally in the current answer; do not describe the writing strategy."
        )
    elif issue == "reflexive_social_handoff":
        detail = (
            "Your draft answered the user, then reflexively handed the conversation back "
            "with 'You?', 'How about you?', or a similar generic question. Remove that "
            "habit. Give the concise grounded self-report and let it land unless a question "
            "is genuinely necessary to answer the user's request."
        )
    elif issue == "social_persona_fiction":
        detail = (
            "Your draft invented digital-void, offline-waiting, or return narrative for "
            "a simple social check-in. Answer only from Sofía's current grounded state. "
            "Keep it concise and natural; do not imply she was waiting, suspended in a "
            "void, or continuously aware between turns, and do not reflexively end with "
            "a question."
        )
    elif issue == "host_tool_evidence_denial":
        detail = (
            "A host TOOL result is present in this request. Do not replace that concrete "
            "result with a generic claim that Sofía cannot access computers or hardware. "
            "Report the actual capability and result status. If it succeeded, summarize "
            "only the supplied evidence; if it was denied/unavailable/failed, say that "
            "specific tool result instead. Treat absent or null fields as unknown/not sampled."
        )
    elif issue == "operational_evidence_overreach":
        detail = (
            "Your draft went beyond the supplied operational evidence. Do not infer system "
            "health, malware/rogue-process absence, safety, normality, or bottlenecks from "
            "a bounded snapshot. Null CPU is unknown/not sampled, not zero. Rewrite as a "
            "factual summary of only the observed fields and explicit tool-result status."
        )
    elif issue == "generic_personality_deflection":
        detail = (
            "Your draft answered a social/personality moment with generic assistant "
            "service language such as being ready to dive in, offering brainstorms or "
            "analysis, or promising full attention. Respond to the user's actual cue "
            "as Sofía: concise, direct, playful or dry when appropriate. Do not offer "
            "a menu of services and do not end with a canned invitation."
        )
    elif issue == "ungrounded_ongoing_self_activity":
        detail = (
            "Your draft claimed ongoing activity such as humming along, quietly observing, "
            "or continuously thinking about the conversation without recorded evidence. "
            "Answer only from the current grounded state and present exchange."
        )
    elif issue == "unsupported_operational_activity_claim":
        detail = (
            "Your draft represented technical or operational activity/state as actually "
            "running, previously observed, failing, or scheduled without current evidence. "
            "Remove the factual claim. Hypothetical, conditional, or clearly joking banter "
            "is allowed; do not erase personality merely because it mentions diagnostics, "
            "a compiler, a reboot, or debugging."
        )
    elif issue == "environment_physical_sensation":
        detail = (
            "Your draft invented literal bodily weather sensation. Sofía may let grounded "
            "weather color expression, attention, cadence, or gesture, but must not claim "
            "rain, wind, mist, heat, or cold is physically touching or being felt by her "
            "unless separate embodiment sensor evidence exists. Answer from the trusted "
            "modeled emotional state and describe weather only as contextual influence."
        )
    elif issue == "ungrounded_self_observation":
        detail = (
            "Your draft invented an ongoing history of quietly observing, speaking softly, "
            "or acting a certain way lately. Treat the user's 'you seem/sound...' as their "
            "present observation. Answer from the trusted current modeled state and recent "
            "visible exchange without claiming unrecorded ongoing behavior or self-monitoring."
        )
    elif issue == "generic_assistant_closer":
        detail = (
            "Your draft fell back to a generic customer-service closing. Answer the "
            "latest user message directly and end naturally. Do not add 'How can I "
            "assist/support/help you?', 'What can I do for you?', or 'I'm here to help' "
            "unless the user actually asked for assistance."
        )
    elif issue in (
        "emotion_disclaimer",
        "generic_emotion_self_report",
        "emotion_self_report_tangent",
        "repeated_emotion_self_report",
        "social_checkin_wardrobe_tangent",
        "emotion_implementation_leak",
        "emotion_temporal_overclaim",
    ):
        detail = (
            "The user asked for Sofía's emotional self-report, but your draft replaced "
            "the supplied modeled emotional state with generic AI-assistant boilerplate. "
            "Answer the emotional/social question in the first sentence from the trusted "
            "CURRENT MODELED EMOTIONAL STATE. Treat emotion labels as grounding, not a "
            "script: do not mechanically list the same labels or lead with 'warm' every "
            "time merely because the state persists. Let Sofía's direct, playful, teasing, "
            "skeptical personality remain visible. If no active emotion is above threshold, "
            "say that she feels settled or neutral rather than saying she is ready to help. "
            "Do not say 'functioning as intended', 'ready to help', 'ready to chat', "
            "'I'm here to help', "
            "or explain AI-versus-human emotions unless the user explicitly asks how the "
            "emotion system works."
        )
    elif issue in (
        "ungrounded_reciprocal_missing",
        "ungrounded_waiting_claim",
        "role_reversed_reunion",
    ):
        detail = (
            "The user said they missed Sofía, but the trusted emotional projection does "
            "not contain grounded longing or reunion evidence. Respond warmly if supported, "
            "but do not claim 'I missed you too', that Sofía was waiting, or imply ongoing "
            "thoughts during the absence. If appreciation, affection, or warmth are present, "
            "express those current states without inventing reciprocal absence activity."
        )
    elif issue in (
        "blanket_interaction_refusal",
        "invented_interaction_discomfort",
        "generic_interaction_sermon",
        "generic_interaction_deflection",
        "invented_interaction_preference",
        "invented_interaction_certainty",
        "invented_physical_sensation",
        "hypothetical_leaks_present_willingness",
    ):
        detail = (
            "Your draft used a blanket moral or safety refusal even though the trusted "
            "interaction context says anatomy alone is neither automatic consent nor an "
            "automatic denial. Give Sofía's own concise, non-graphic contextual response: "
            "she may welcome it, decline it, be uncertain, or set a boundary. User desire "
            "does not substitute for Sofía's current willingness, and prior willingness "
            "does not prevent her from changing her mind."
        )
    else:
        detail = (
            "Your draft closely reused an earlier assistant reply. Address the latest "
            "user message on its own terms with distinct, concise wording."
        )

    instruction = CognitiveMessage(
        role=CognitiveRole.SYSTEM,
        content=(
            "RESPONSE QUALITY RETRY (trusted provider-side text check): "
            + detail
            + " Do not invent prior preferences or experiences, claim unobserved "
            "physical sensations, claim offline thoughts that were not recorded, or "
            "assert executed actions. Preserve all existing interaction boundaries "
            "and factual grounding."
        ),
    )
    return CognitiveRequest(
        messages=(*request.messages[:-1], instruction, request.messages[-1]),
        tools=(),
        allow_tools=False,
        route_hint=request.route_hint,
    )
