"""Real application-to-Ollama regressions for production conversation routing."""

from dataclasses import replace
from datetime import datetime, timezone

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration


def _application(monkeypatch, tmp_path, responses):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_MANAGE", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_INSTALL", "0")
    captured = []
    remaining = iter(responses)

    def fake_ollama_once(self, request):
        captured.append(request)
        return CognitiveResponse(content=next(remaining))

    monkeypatch.setattr(OllamaProvider, "_respond_once", fake_ollama_once)
    configuration = replace(
        create_default_configuration(),
        state_path=tmp_path / "isolated-sofia.db",
        filesystem_root=tmp_path,
    )
    application = SofiaApplication(configuration)
    application.start()
    captured.clear()
    return application, captured


def test_real_application_hru_is_tool_free_and_repairs_generic_assistant_reply(
    monkeypatch,
    tmp_path,
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        (
            "I'm settled and ready to help you with anything you need! "
            "How can I assist you today?",
            "I'm feeling pretty settled right now.",
        ),
    )
    try:
        response = application.conversation.respond("hru")

        assert response.content == "I'm feeling pretty settled right now."
        assert len(captured) == 2
        assert captured[0].allow_tools is False
        assert captured[0].tools == ()
        assert captured[1].allow_tools is False
        assert captured[1].tools == ()
        assert any(
            "RESPONSE QUALITY RETRY" in message.content
            for message in captured[1].messages
        )
    finally:
        application.shutdown()


def test_central_timezone_followup_does_not_expose_system_inspection_tools(
    monkeypatch,
    tmp_path,
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("Got it. Central timezone.",),
    )
    try:
        response = application.conversation.respond("Central timezone")

        assert response.content == "Got it. Central timezone."
        assert len(captured) == 1
        assert captured[0].allow_tools is False
        assert captured[0].tools == ()
    finally:
        application.shutdown()


def test_weather_today_is_answered_by_environment_resolver_without_llm(
    monkeypatch,
    tmp_path,
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("This response must never be used.",),
    )
    try:
        response = application.conversation.respond("what is the weather today")

        assert response.content.startswith(
            "I don't have current weather evidence."
        )
        assert (
            "No configured weather provider produced evidence for the effective location."
            in response.content
        )
        assert captured == []
    finally:
        application.shutdown()


def test_live_casual_network_status_does_not_invent_telemetry(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond("So hows the network")
        assert "don't have the required current measurement evidence" in (
            reply.content
        )
        assert captured == []
    finally:
        application.shutdown()


def test_live_model_status_uses_configured_primary_not_generated_avatar_prose(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond("What llm am i running rn")
        assert application.runtime.operational_state.model in reply.content
        assert "configured primary model" in reply.content
        assert "This configuration alone doesn't prove" in reply.content
        assert captured == []
    finally:
        application.shutdown()


def test_discord_hru_turn_excludes_previous_unrelated_assistant_history(
    monkeypatch, tmp_path
):
    from sofia.cognition.model import CognitiveRole

    application, captured = _application(
        monkeypatch, tmp_path,
        ("The robot is a hexapod.", "I'm feeling pretty settled today."),
    )
    try:
        application.conversation.respond("Tell me about a six-legged robot.")
        response = application.conversation.respond("Hru")
        assert "settled" in response.content
        assert len(captured) == 2
        second = captured[1]
        non_system = [
            message.content for message in second.messages
            if message.role in (CognitiveRole.USER, CognitiveRole.ASSISTANT)
        ]
        assert non_system == ["Hru"]
        assert len(application.conversation.messages()) == 4
    finally:
        application.shutdown()


def test_live_discord_panties_question_uses_current_avatar_projection(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond("show me ur panties")
        assert "current AVATAR wardrobe matrix" in reply.content
        assert "cannot generate images containing nudity" not in reply.content
        assert captured == []
    finally:
        application.shutdown()


def test_matrix_hru_provider_context_excludes_unrelated_avatar_and_runtime_facts(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("I'm feeling calm.",),
    )
    try:
        response = application.conversation.respond("Hru")

        assert response.content == "I'm feeling calm."
        assert len(captured) == 1
        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "Fitted breathable black technical shirt" not in system_text
        assert application.runtime.operational_state.model not in system_text
        assert "CLOTHING: UNKNOWN" in system_text
        assert "OPERATIONAL STATE: UNKNOWN" in system_text

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.context_active is True
        assert trace.context is not None
        assert trace.context.max_history_messages == 1
    finally:
        application.shutdown()


def test_matrix_hru_skips_memory_retrieval(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("I'm feeling calm.",),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Hru must not retrieve MEMORY domain state")

    monkeypatch.setattr(
        application.runtime._memory_system,
        "recall_relevant",
        forbidden,
    )
    monkeypatch.setattr(
        application.runtime._memory_system,
        "recall_historical_evidence",
        forbidden,
    )
    try:
        response = application.conversation.respond("Hru")

        assert response.content == "I'm feeling calm."
        assert len(captured) == 1
    finally:
        application.shutdown()


def test_matrix_general_conversation_keeps_full_context_during_safe_rollout(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("Hexapod gait planning uses coordinated leg phases.",),
    )
    try:
        response = application.conversation.respond(
            "Tell me about hexapod gait planning."
        )

        assert "coordinated leg phases" in response.content
        assert len(captured) == 1
        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "Fitted breathable black technical shirt" not in system_text
        assert application.runtime.operational_state.model not in system_text
        assert "CLOTHING: UNKNOWN" in system_text
        assert "OPERATIONAL STATE: UNKNOWN" in system_text

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.context_active is True
        assert trace.context is not None
        assert trace.context.max_history_messages == 12
    finally:
        application.shutdown()


def test_live_prefixed_outfit_question_is_deterministic(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond("so what are you wearing")

        projection = application.runtime.avatar_presentation_projection
        assert projection is not None
        assert projection.item_names
        assert all(name in reply.content for name in projection.item_names)
        assert "feel" not in reply.content.casefold()
        assert captured == []
    finally:
        application.shutdown()


def test_live_tonight_lounge_outfit_question_is_deterministic(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond(
            "what would tonights lounge outfit be?"
        )

        assert "late-night lounge outfit" in reply.content
        assert "not something I've already changed into" in reply.content
        assert "wool" not in reply.content.casefold()
        assert captured == []
    finally:
        application.shutdown()


def test_live_sofia_matrix_term_gets_project_architecture_context(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("Right, the Sofía matrix architecture is in the current project context.",),
    )
    try:
        reply = application.conversation.respond("We added matrixs")

        assert "matrix architecture" in reply.content
        assert len(captured) == 1
        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "TRUSTED SOFÍA PROJECT TERM CONTEXT" in system_text
        assert "not a mathematical or data matrix" in system_text
    finally:
        application.shutdown()


def test_live_tell_me_the_why_keeps_immediate_touch_context(
    monkeypatch, tmp_path
):
    from sofia.cognition.model import CognitiveRole

    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("Because willingness is contextual rather than a fixed body-region list.",),
    )
    try:
        first = application.conversation.respond(
            "so question what can I touch"
        )
        assert "isn't a fixed list" in first.content
        assert captured == []

        second = application.conversation.respond("tell me the why")
        assert "contextual" in second.content
        assert len(captured) == 1

        non_system = [
            message.content
            for message in captured[0].messages
            if message.role in (
                CognitiveRole.USER,
                CognitiveRole.ASSISTANT,
            )
        ]
        assert non_system == [
            "so question what can I touch",
            first.content,
            "tell me the why",
        ]

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.context is not None
        assert trace.context.max_history_messages == 3
    finally:
        application.shutdown()



def test_live_conversation_projects_and_rotates_embodied_expression(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        (
            "*Her ears perk.* I'm curious and pretty engaged right now.",
            "*Her tail stills for a beat.* Still curious, just more focused.",
        ),
    )
    try:
        now = datetime.now(timezone.utc)
        subject = application.conversation._relationship_subject()
        application.conversation.emotional_journal.record(
            event_id="test:embodied-expression:curiosity",
            source="observed",
            evidence_ref="test:embodied-expression:curiosity",
            description="Test fixture supplies grounded current curiosity.",
            emotions=("curiosity",),
            occurred_at=now,
            subject=subject,
            scope=application.conversation.relationship_scope,
        )

        first = application.conversation.respond("hru")
        assert "curious" in first.content
        assert len(captured) == 1
        first_system = "\n".join(
            message.content for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" in first_system
        assert "A fitting brief expression, if useful:" in first_system
        assert application.conversation.current_expression_plan is not None

        second = application.conversation.respond("hru")
        assert "curious" in second.content
        assert len(captured) == 2
        second_plan = application.conversation.current_expression_plan
        assert second_plan is not None
        assert "ear-perk" in second_plan.avoid_recent
        assert second_plan.primary != "ear-perk"
    finally:
        application.shutdown()



def test_live_avatar_why_followup_stays_on_presentation_state(
    monkeypatch, tmp_path
):
    from sofia.cognition.matrix import MatrixDomain, MatrixRelevance

    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("This provider response must never be used.",),
    )
    try:
        first = application.conversation.respond("what are you wearing?")
        projection = application.runtime.avatar_presentation_projection
        assert projection is not None
        assert projection.item_names
        assert all(name in first.content for name in projection.item_names)

        second = application.conversation.respond("why did you pick that?")

        if projection.reason.casefold() == "canonical_daily_bootstrap":
            assert "canonical daily default" in second.content
        else:
            assert projection.reason.casefold().startswith(
                "headless_daily_context:"
            )
            assert "I picked my" in second.content
        assert "tone" not in second.content.casefold()
        assert "cadence" not in second.content.casefold()
        assert captured == []

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.turn.relevance_for(MatrixDomain.AVATAR) is (
            MatrixRelevance.CONTEXTUAL
        )
        assert trace.context is not None
        assert trace.context.max_history_messages == 3
    finally:
        application.shutdown()



def test_live_hru_uses_primary_personality_route_and_hides_old_event_log(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("Doing pretty good. A little playful, actually.",),
    )
    try:
        reply = application.conversation.respond("hru")

        assert "playful" in reply.content
        assert len(captured) == 1

        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "MODELED EMOTIONAL CONTEXT" not in system_text
        assert "RECORDED REFLECTIONS" not in system_text

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.routing is not None
        assert trace.routing.route.value == "standard"
        assert trace.cognition_execution is not None
        assert trace.cognition_execution.actual_route == "standard"
        assert trace.cognition_execution.successful_steps
        assert trace.cognition_execution.successful_steps[0].role == "primary"
    finally:
        application.shutdown()


def test_live_weather_affect_turn_uses_primary_and_no_emotional_history_dump(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        (
            "The rain can make my delivery a little quieter, but it isn't physically "
            "touching me or manufacturing a new feeling.",
        ),
    )
    try:
        reply = application.conversation.respond(
            "how does that weather affect you?"
        )

        assert "isn't physically touching me" in reply.content
        assert len(captured) == 1
        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role.value == "system"
        )
        assert "MODELED EMOTIONAL CONTEXT" not in system_text
        assert "RECORDED REFLECTIONS" not in system_text

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.routing is not None
        assert trace.routing.route.value == "standard"
        assert trace.cognition_execution is not None
        assert trace.cognition_execution.successful_steps[0].role == "primary"
    finally:
        application.shutdown()



def test_live_social_turn_keeps_recent_gesture_avoidance_without_new_emotion(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        (
            "*My ears perk with a quick grin.* Hey.",
            "Nerd? Accurate. *My tail goes still for a beat.*",
        ),
    )
    try:
        first = application.conversation.respond("waves at you")
        assert "ears perk" in first.content

        second = application.conversation.respond("hey nerd")
        assert "Nerd? Accurate." in second.content
        assert len(captured) == 2

        second_system = "\n".join(
            message.content
            for message in captured[1].messages
            if message.role.value == "system"
        )
        assert "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" in second_system
        assert "No specific expression cue is required this turn." in second_system
        assert "let the fox ears perk with attention" in second_system

        plan = application.conversation.current_expression_plan
        assert plan is not None
        assert plan.primary is None
        assert "ear-perk" in plan.avoid_recent
    finally:
        application.shutdown()



def test_live_generic_what_is_your_outfit_bypasses_provider(
    monkeypatch, tmp_path
):
    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("THIS MUST NOT BE GENERATED",),
    )
    try:
        reply = application.conversation.respond("what is your outfit")

        projection = application.runtime.avatar_presentation_projection
        assert projection is not None
        assert projection.item_names
        assert all(name in reply.content for name in projection.item_names)
        assert "shock-absorbing" not in reply.content.casefold()
        assert captured == []
    finally:
        application.shutdown()


def test_live_system_inspection_preflights_read_only_host_tool(
    monkeypatch, tmp_path
):
    from sofia.cognition.model import CognitiveRole

    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("I inspected the host evidence and summarized only the observed fields.",),
    )
    try:
        reply = application.conversation.respond(
            "Inspect this computer's operating system, host identity, and uptime, "
            "then summarize the important points."
        )

        assert "inspected the host evidence" in reply.content
        assert len(captured) == 1
        tool_messages = [
            message for message in captured[0].messages
            if message.role is CognitiveRole.TOOL
        ]
        assert tool_messages
        assert any("Capability: system.inspect" in item.content for item in tool_messages)
        assert any("Result: success" in item.content for item in tool_messages)
        assert "capability:system.inspect" in reply.evidence_refs
    finally:
        application.shutdown()


def test_live_network_inspection_is_not_hijacked_by_filesystem_parser(
    monkeypatch, tmp_path
):
    from sofia.cognition.model import CognitiveRole

    application, captured = _application(
        monkeypatch,
        tmp_path,
        ("I summarized the current network tool evidence only.",),
    )
    try:
        reply = application.conversation.respond(
            "Inspect the local network interfaces, routes, and DNS configuration, "
            "then summarize the current network state."
        )

        assert "network tool evidence" in reply.content
        assert len(captured) == 1
        system_text = "\n".join(
            message.content
            for message in captured[0].messages
            if message.role is CognitiveRole.SYSTEM
        )
        assert "TRUSTED READ-ONLY TOOL REQUIREMENT" in system_text
        assert "filesystem inspection is not authorized" not in system_text.casefold()
        assert any(
            message.role is CognitiveRole.TOOL
            and "Capability: network.inspect" in message.content
            for message in captured[0].messages
        )
        assert "capability:network.inspect" in reply.evidence_refs
    finally:
        application.shutdown()
