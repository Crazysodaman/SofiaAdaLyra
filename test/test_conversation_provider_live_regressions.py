"""Real application-to-Ollama regressions for production conversation routing."""

from dataclasses import replace

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration


def _application(monkeypatch, tmp_path, responses):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
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

        assert response.content == "I don't have current weather evidence."
        assert captured == []
    finally:
        application.shutdown()


def test_live_casual_network_status_does_not_invent_telemetry(
    monkeypatch, tmp_path
):
    application, captured = _application(monkeypatch, tmp_path, ())
    try:
        reply = application.conversation.respond("So hows the network")
        assert "don't have a fresh, verified network-health measurement" in (
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
        assert "current avatar presentation" in reply.content
        assert "cannot generate images containing nudity" not in reply.content
        assert captured == []
    finally:
        application.shutdown()
