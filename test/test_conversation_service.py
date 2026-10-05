from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application import (
    ConversationService,
    SofiaApplication,
)
from sofia.authority.model import Authority
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.conversation.model import (
    ConversationRole,
)
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.providers.test_provider import TestLLMProvider
from sofia.cognition.routing import (
    CognitiveEngineRegistry,
    RoutingCognitiveEngine,
)
from sofia.safe.permissions import (
    PermissionLevel,
    capability_permission_policy,
)
from sofia.social.principals import local_sparks_principal
from sofia.social.store import SocialSessionStore
from sofia.cognition.matrix import (
    AuthorityDecision,
    EvidenceState,
    HistoryPolicy,
    MatrixDomain,
    MatrixRelevance,
    MatrixRoute,
    ResponseValidationDisposition,
)


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "embodiment"
    / "avatar.json"
)


def create_configuration(
    personality_path: Path,
    state_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def create_personality(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "personality.json"

    path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return path


def create_application(
    tmp_path: Path,
) -> SofiaApplication:
    return SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )


def test_conversation_service_is_application_boundary(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    assert isinstance(
        application.conversation,
        ConversationService,
    )

    assert application.conversation.session is None
    assert application.conversation.session_id is None

    application.start()

    assert application.conversation.session is not None
    assert application.conversation.session_id is not None

    application.shutdown()


def test_conversation_service_creates_session_on_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    session = application.conversation.session

    assert session is not None
    assert session.id == application.conversation.session_id

    application.shutdown()


def test_conversation_service_persists_user_and_assistant_messages(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "Hello, Sofía."
    )

    messages = application.conversation.messages()

    assert response.content == "Test cognitive response."

    assert len(messages) == 2

    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "Hello, Sofía."

    assert messages[1].role is ConversationRole.ASSISTANT
    assert messages[1].content == "Test cognitive response."

    application.shutdown()


def _dual_test_router():
    primary = LLMCognitiveEngine(
        configuration=ProviderConfiguration(
            provider="test-llm",
            model="primary-test-model",
        ),
        provider=TestLLMProvider(
            CognitiveResponse(content="primary response")
        ),
    )
    secondary = LLMCognitiveEngine(
        configuration=ProviderConfiguration(
            provider="test-llm",
            model="secondary-test-model",
        ),
        provider=TestLLMProvider(
            CognitiveResponse(content="secondary response")
        ),
    )
    return RoutingCognitiveEngine(
        CognitiveEngineRegistry(
            primary=primary,
            secondary=secondary,
        )
    )


def test_social_matrix_trace_records_actual_primary_model_execution(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    application.runtime.cognitive_system.engine = _dual_test_router()
    try:
        response = application.conversation.respond("Hru")

        assert response.content == "primary response"
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.cognition_execution is not None
        assert trace.cognition_execution.actual_route == "standard"
        assert tuple(
            step.role for step in trace.cognition_execution.successful_steps
        ) == ("primary",)
        assert (
            trace.cognition_execution.last_successful_step.model
            == "primary-test-model"
        )
    finally:
        application.shutdown()


def test_verify_matrix_trace_proves_primary_secondary_primary_execution(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    application.runtime.cognitive_system.engine = _dual_test_router()
    try:
        response = application.conversation.respond(
            "Please verify your answer before replying."
        )

        assert response.content == "primary response"
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.cognition_execution is not None
        assert trace.cognition_execution.actual_route == "verify"
        assert tuple(
            step.role for step in trace.cognition_execution.successful_steps
        ) == ("primary", "secondary", "primary")
        assert trace.cognition_execution.verification_passes == 2
        assert tuple(
            step.model for step in trace.cognition_execution.successful_steps
        ) == (
            "primary-test-model",
            "secondary-test-model",
            "primary-test-model",
        )
    finally:
        application.shutdown()


def test_conversation_service_can_respond_from_worker_thread(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()

    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(
            application.conversation.respond,
            "Hello from a worker thread.",
        ).result(timeout=5)

    assert response.content == "Test cognitive response."

    messages = application.conversation.messages()
    assert len(messages) == 2
    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "Hello from a worker thread."
    assert messages[1].role is ConversationRole.ASSISTANT
    assert messages[1].content == "Test cognitive response."

    application.shutdown()


def test_conversation_service_preserves_conversation_history(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "First message."
    )

    application.conversation.respond(
        "Second message."
    )

    messages = application.conversation.messages()

    assert len(messages) == 4

    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "First message."

    assert messages[1].role is ConversationRole.ASSISTANT
    assert messages[1].content == "Test cognitive response."

    assert messages[2].role is ConversationRole.USER
    assert messages[2].content == "Second message."

    assert messages[3].role is ConversationRole.ASSISTANT
    assert messages[3].content == "Test cognitive response."

    application.shutdown()


def test_conversation_service_rejects_response_before_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="ConversationService must be started before responding.",
    ):
        application.conversation.respond(
            "Hello, Sofía."
        )


def test_conversation_service_rejects_empty_response(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        ValueError,
        match="ConversationService content must not be empty.",
    ):
        application.conversation.respond("   ")

    application.shutdown()


def test_conversation_service_rejects_non_string_response(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        TypeError,
        match="ConversationService content must be a string.",
    ):
        application.conversation.respond(None)

    application.shutdown()


def test_conversation_service_rejects_second_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        RuntimeError,
        match="ConversationService already has an active session.",
    ):
        application.conversation.start()

    application.shutdown()
def test_conversation_service_processes_filesystem_authorization(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "you are allowed to check your own files",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    assert response.content == "Test cognitive response."

    assert (
        application.runtime.filesystem_authorization
        is not None
    )

    assert (
        application.runtime.filesystem_inspector.authorized
        is True
    )

    application.shutdown()


def test_conversation_service_processes_filesystem_request(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "you are allowed to check your own files",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    response = application.conversation.respond(
        "read src/sofia/filesystem/model.py",
        principal=local_sparks_principal(),
        channel="desktop",
    )

    assert response.content == "Test cognitive response."

    messages = application.conversation.messages()

    assert messages[-2].content == (
        "read src/sofia/filesystem/model.py"
    )

    assert messages[-1].content == (
        "Test cognitive response."
    )

    application.shutdown()


def test_filesystem_request_without_authorization_remains_denied(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "read src/sofia/filesystem/model.py"
    )

    assert response.content == "Test cognitive response."

    assert (
        application.runtime.filesystem_inspector.authorized
        is False
    )

    application.shutdown()

def test_live_conversation_request_uses_matrix_tool_exposure(tmp_path: Path):
    application = create_application(tmp_path)
    application.start()
    try:
        application.conversation.respond("hru")
        social_request = application.conversation._build_request()
        assert social_request.allow_tools is False
        assert social_request.capability_allowlist == ()

        application.conversation.respond("check current CPU usage")
        operational_request = application.conversation._build_request()
        assert operational_request.allow_tools is True
        assert "hardware.inspect" in operational_request.capability_allowlist
        assert all(
            capability_permission_policy(capability).level
            <= PermissionLevel.SAFE_AUTONOMOUS
            for capability in operational_request.capability_allowlist
        )
    finally:
        application.shutdown()


def test_unapproved_operational_action_is_tool_free(tmp_path: Path):
    application = create_application(tmp_path)
    application.start()
    try:
        application.conversation.respond("restart the service")
        request = application.conversation._build_request()
        assert request.allow_tools is True
        assert "service.inspect" in request.capability_allowlist
        assert "local.service.restart" not in request.capability_allowlist
        assert all(
            capability_permission_policy(capability).level
            <= PermissionLevel.SAFE_AUTONOMOUS
            for capability in request.capability_allowlist
        )
    finally:
        application.shutdown()


def test_normal_reply_finalizes_before_assistant_message_is_persisted(
    tmp_path, monkeypatch
):
    """A rejected or rewritten interaction cannot leak into durable history."""
    from sofia.cognition.model import CognitiveResponse

    application = create_application(tmp_path)
    application.start()
    seen = []

    def finalize(request, response, *, principal):
        seen.append((request, response, principal))
        return CognitiveResponse(content="Grounded revised response.")

    monkeypatch.setattr(
        application.conversation,
        "_finalize_response",
        finalize,
    )
    try:
        result = application.conversation.respond("pats your head")
        history = application.conversation.messages()

        assert len(seen) == 1
        assert seen[0][2] is None
        assert result.content == "Grounded revised response."
        assert history[-1].role is ConversationRole.ASSISTANT
        assert history[-1].content == "Grounded revised response."
    finally:
        application.shutdown()


@pytest.mark.parametrize(
    "latest",
    (
        "Hru",
        "how are you",
        "So hows the network",
        "so how's the network",
        "What llm am i running rn",
    ),
)
def test_standalone_question_does_not_replay_prior_clothing_chat(
    tmp_path, latest
):
    from sofia.application.conversation_service import (
        _conversation_cognitive_window,
    )
    from sofia.conversation.model import ConversationMessage
    from datetime import datetime, timezone

    session = "discord-session"
    def message(role, content, index):
        return ConversationMessage(
            id=str(index),
            session_id=session,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
    history = (
        message(ConversationRole.USER, "show me your panties", 1),
        message(ConversationRole.ASSISTANT, "Prior wardrobe discussion.", 2),
        message(ConversationRole.USER, latest, 3),
    )
    window = _conversation_cognitive_window(history)
    assert len(window) == 1
    assert window[0].content == latest
    assert len(history) == 3


def test_followup_keeps_recent_history_but_has_bounded_window():
    from sofia.application.conversation_service import (
        _conversation_cognitive_window,
    )
    from sofia.conversation.model import ConversationMessage
    from datetime import datetime, timezone

    history = tuple(
        ConversationMessage(
            id=str(i),
            session_id="discord-session",
            role=(
                ConversationRole.USER
                if i % 2 == 0
                else ConversationRole.ASSISTANT
            ),
            content=f"message-{i}",
            created_at=datetime.now(timezone.utc),
        )
        for i in range(24)
    )
    latest = ConversationMessage(
        id="24",
        session_id="discord-session",
        role=ConversationRole.USER,
        content="how did you feel doing it",
        created_at=datetime.now(timezone.utc),
    )
    window = _conversation_cognitive_window((*history, latest))
    assert len(window) == 12
    assert window[-1] is latest
    assert window[-2] is history[-1]
    assert window[0].id == "13"


def test_conversation_records_active_matrix_trace_before_persistence(
    tmp_path: Path,
):
    from sofia.cognition.matrix import (
        HistoryPolicy,
        MatrixDomain,
        MatrixIntent,
        MatrixRelevance,
    )

    application = create_application(tmp_path)
    application.start()
    try:
        response = application.conversation.respond("Hru")

        assert response.content == "Test cognitive response."

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.shadow is False
        assert trace.envelope.session_id == application.conversation.session_id
        assert trace.turn.intent is MatrixIntent.SOCIAL_CHECKIN
        assert trace.turn.history_policy is HistoryPolicy.NONE
        assert trace.turn.relevance_for(MatrixDomain.SOCIAL) is (
            MatrixRelevance.REQUIRED
        )
        assert trace.context is not None
        assert trace.context_active is True
        assert trace.context.max_history_messages == 1
        assert application.conversation.last_matrix_error is None
    finally:
        application.shutdown()


def test_matrix_shadow_failure_never_breaks_conversation(
    tmp_path: Path,
    monkeypatch,
):
    application = create_application(tmp_path)
    application.start()

    def fail(_envelope):
        raise RuntimeError("synthetic shadow failure")

    monkeypatch.setattr(
        application.conversation._matrix_coordinator,
        "evaluate",
        fail,
    )
    try:
        response = application.conversation.respond("Hello")

        assert response.content == "Test cognitive response."
        assert application.conversation.last_matrix_error == "RuntimeError"
    finally:
        application.shutdown()


def test_channel_propagates_through_full_conversation_stack_to_matrix_trace(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    try:
        response = application.conversation.respond(
            "Hru",
            channel="discord",
        )

        assert response.content == "Test cognitive response."
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.envelope.channel == "discord"
        assert application.conversation.last_matrix_error is None
    finally:
        application.shutdown()


def test_matrix_context_window_applies_typed_history_limits():
    from datetime import datetime, timezone

    from sofia.application.conversation_service import _matrix_context_window
    from sofia.cognition.matrix import (
        ContextPlan,
        HistoryPolicy,
        MatrixDomain,
    )
    from sofia.conversation.model import ConversationMessage

    history = tuple(
        ConversationMessage(
            id=str(i),
            session_id="matrix-session",
            role=(
                ConversationRole.USER
                if i % 2 == 0
                else ConversationRole.ASSISTANT
            ),
            content=f"message-{i}",
            created_at=datetime.now(timezone.utc),
        )
        for i in range(10)
    )
    plan = ContextPlan(
        included_domains=(MatrixDomain.INTERACTION,),
        excluded_domains=tuple(
            domain
            for domain in MatrixDomain
            if domain is not MatrixDomain.INTERACTION
        ),
        history_policy=HistoryPolicy.LAST_TURN,
        max_history_messages=3,
    )

    window = _matrix_context_window(history, plan)

    assert tuple(item.id for item in window) == ("7", "8", "9")


def test_matrix_context_failure_fails_closed_to_current_turn(
    tmp_path: Path,
    monkeypatch,
):
    application = create_application(tmp_path)
    application.start()

    def fail(_turn):
        raise RuntimeError("synthetic context planning failure")

    monkeypatch.setattr(
        application.conversation._matrix_context_planner,
        "plan",
        fail,
    )
    try:
        response = application.conversation.respond("Hello")

        assert response.content == "Test cognitive response."
        assert (
            application.conversation.last_matrix_error
            == "planning:RuntimeError"
        )
        plan = application.conversation._current_context_plan
        assert plan is not None
        assert plan.included_domains == ()
        assert plan.max_history_messages == 1
        assert plan.history_policy is HistoryPolicy.NONE
    finally:
        application.shutdown()


def test_matrix_trace_records_privacy_projection_for_bound_principal(tmp_path: Path):
    application = create_application(tmp_path)
    application.start()
    try:
        application.conversation.respond(
            "Hru",
            principal=local_sparks_principal(),
            channel="desktop",
        )
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.privacy is not None
        assert trace.privacy.allow_audience_scope is True
        assert trace.privacy.principal_id
        assert trace.privacy.audience_id
    finally:
        application.shutdown()


def test_matrix_hru_routes_standard_and_records_validation(
    tmp_path: Path,
    monkeypatch,
):
    application = create_application(tmp_path)
    application.start()
    requests = []

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(content="I'm feeling settled.")

    monkeypatch.setattr(application.runtime, "respond", respond)
    try:
        result = application.conversation.respond("Hru")

        assert result.content == "I'm feeling settled."
        assert len(requests) == 1
        assert requests[0].route_hint == "standard"

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.routing is not None
        assert trace.routing.route is MatrixRoute.STANDARD
        assert trace.evidence is not None
        assert all(
            not item.key.startswith("environment.")
            for item in trace.evidence.requirements
        )
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.PASS
        )
    finally:
        application.shutdown()


def test_matrix_network_no_evidence_is_recorded_without_fake_health(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    try:
        result = application.conversation.respond("So hows the network")

        normalized = result.content.casefold()
        assert "don't have" in normalized
        assert "measurement" in normalized or "network-health" in normalized
        assert "no packet loss" not in normalized
        assert "all systems green" not in normalized
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.evidence is not None
        assert trace.evidence.state_for("operational.measurement") is (
            EvidenceState.MISSING
        )
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.FALLBACK
        )
        assert (
            "measured_operational_claim_without_evidence"
            in trace.response_validation.reasons
        )
    finally:
        application.shutdown()


def test_runtime_promotes_host_execution_receipt_evidence(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    try:
        evidence = application.runtime.matrix_evidence_availability(
            required_keys=("action.execution_receipt",),
            response=CognitiveResponse(
                content="Completed.",
                evidence_refs=(
                    "execution-receipt:local.service.restart",
                ),
            ),
        )

        record = evidence["action.execution_receipt"]
        assert record.state is EvidenceState.AVAILABLE
        assert record.source_ref == (
            "execution-receipt:local.service.restart"
        )

        unreceipted = application.runtime.matrix_evidence_availability(
            required_keys=("action.execution_receipt",),
            response=CognitiveResponse(
                content="Completed.",
                evidence_refs=("capability:local.service.restart",),
            ),
        )
        assert unreceipted["action.execution_receipt"] is (
            EvidenceState.MISSING
        )
    finally:
        application.shutdown()


def test_allowed_receipt_backed_action_claim_persists(
    tmp_path: Path,
    monkeypatch,
):
    application = create_application(tmp_path)
    application.start()
    requests = []

    monkeypatch.setattr(
        application.runtime,
        "current_authority",
        lambda: Authority(
            can_respond=True,
            can_propose_actions=True,
            can_execute_actions=True,
        ),
    )

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(
            content="I restarted Plex on Dionysus.",
            evidence_refs=(
                "execution-receipt:local.service.restart",
            ),
        )

    monkeypatch.setattr(application.runtime, "respond", respond)
    try:
        result = application.conversation.respond(
            "restart the plex service on Dionysus"
        )

        assert result.content == "I restarted Plex on Dionysus."
        assert requests[0].allow_tools is True
        assert requests[0].route_hint == "verify"

        history = application.conversation.messages()
        assert history[-1].content == "I restarted Plex on Dionysus."

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.authority is not None
        assert trace.authority.decision is AuthorityDecision.ALLOWED
        assert trace.evidence is not None
        assert trace.evidence.state_for(
            "action.execution_receipt"
        ) is EvidenceState.AVAILABLE
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.PASS
        )
    finally:
        application.shutdown()


def test_matrix_action_claim_is_rewritten_before_persistence(
    tmp_path: Path,
    monkeypatch,
):
    application = create_application(tmp_path)
    application.start()
    requests = []
    responses = iter(
        (
            CognitiveResponse(content="I restarted Plex on Dionysus."),
            CognitiveResponse(
                content=(
                    "I can plan the Plex restart, but execution still "
                    "requires approval."
                )
            ),
        )
    )

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return next(responses)

    monkeypatch.setattr(application.runtime, "respond", respond)
    try:
        result = application.conversation.respond(
            "restart Plex on Dionysus"
        )

        assert "requires approval" in result.content
        assert "I restarted" not in result.content
        assert len(requests) == 2
        assert requests[0].allow_tools is False
        assert requests[0].route_hint == "verify"
        assert requests[1].allow_tools is False
        assert requests[1].route_hint == "verify"

        history = application.conversation.messages()
        assert "I restarted Plex" not in history[-1].content

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.authority is not None
        assert trace.authority.decision is (
            AuthorityDecision.REQUIRES_APPROVAL
        )
        assert trace.routing is not None
        assert trace.routing.route is MatrixRoute.VERIFY
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.PASS
        )
    finally:
        application.shutdown()


def test_interaction_stop_completes_active_matrix_trace_without_llm(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    try:
        result = application.conversation.respond(
            "Sofía, stop interactions"
        )

        assert "paused" in result.content
        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.shadow is False
        assert trace.turn.relevance_for(MatrixDomain.INTERACTION) is (
            MatrixRelevance.REQUIRED
        )
        assert trace.turn.relevance_for(MatrixDomain.OPS) is (
            MatrixRelevance.NONE
        )
        assert trace.authority is not None
        assert trace.authority.decision is AuthorityDecision.ALLOWED
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.PASS
        )
    finally:
        application.shutdown()


def test_touch_scope_question_is_host_grounded_and_persisted(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    try:
        response = application.conversation.respond(
            "so question what can I touch"
        )

        assert "isn't a fixed list" in response.content
        assert "no touch happened just by asking" in response.content

        history = application.conversation.messages()
        assert history[-2].content == "so question what can I touch"
        assert history[-1].content == response.content

        trace = application.conversation.latest_matrix_trace()
        assert trace is not None
        assert trace.shadow is False
        assert trace.turn.relevance_for(MatrixDomain.INTERACTION) is (
            MatrixRelevance.REQUIRED
        )
        assert trace.response_validation is not None
        assert trace.response_validation.disposition is (
            ResponseValidationDisposition.PASS
        )
    finally:
        application.shutdown()


@pytest.mark.parametrize(
    "history_policy",
    (
        HistoryPolicy.LAST_TURN,
        HistoryPolicy.TOPIC_WINDOW,
        HistoryPolicy.BOUNDED_RECENT,
    ),
)
def test_matrix_context_window_filters_excluded_domains_across_history_policies(
    history_policy,
):
    from datetime import datetime, timezone

    from sofia.application.conversation_service import _matrix_context_window
    from sofia.cognition.matrix import ContextPlan, MatrixDomain
    from sofia.conversation.model import ConversationMessage

    now = datetime(2026, 10, 2, 23, 0, tzinfo=timezone.utc)
    history = (
        ConversationMessage(
            id="env-u",
            session_id="domain-filter",
            role=ConversationRole.USER,
            content="what's the weather?",
            created_at=now,
        ),
        ConversationMessage(
            id="env-a",
            session_id="domain-filter",
            role=ConversationRole.ASSISTANT,
            content="Weather answer",
            created_at=now,
        ),
        ConversationMessage(
            id="social-u",
            session_id="domain-filter",
            role=ConversationRole.USER,
            content="hru",
            created_at=now,
        ),
        ConversationMessage(
            id="social-a",
            session_id="domain-filter",
            role=ConversationRole.ASSISTANT,
            content="Social answer",
            created_at=now,
        ),
        ConversationMessage(
            id="current-u",
            session_id="domain-filter",
            role=ConversationRole.USER,
            content="tell me more",
            created_at=now,
        ),
    )
    plan = ContextPlan(
        included_domains=(MatrixDomain.SOCIAL,),
        excluded_domains=tuple(
            domain
            for domain in MatrixDomain
            if domain is not MatrixDomain.SOCIAL
        ),
        history_policy=history_policy,
        max_history_messages=5,
    )
    traced_domains = {
        "env-u": (MatrixDomain.ENVIRONMENT,),
        "social-u": (MatrixDomain.SOCIAL,),
    }

    visible = _matrix_context_window(
        history,
        plan,
        domain_lookup=lambda message_id: traced_domains.get(message_id, ()),
        current_message_id="current-u",
    )

    assert tuple(message.id for message in visible) == (
        "social-u",
        "social-a",
        "current-u",
    )


def test_last_turn_followup_inherits_prior_semantic_domains_as_context_only():
    from datetime import datetime, timezone

    from sofia.application.conversation_matrix import _inherit_last_turn_domains
    from sofia.cognition.matrix import (
        MatrixContextPlanner,
        MatrixCoordinator,
        MatrixDomain,
        MatrixRelevance,
        TurnEnvelope,
    )
    from sofia.cognition.matrix.defaults import default_matrix_registry

    coordinator = MatrixCoordinator(registry=default_matrix_registry())
    now = datetime(2026, 10, 2, 23, 0, tzinfo=timezone.utc)
    prior = coordinator.evaluate(
        TurnEnvelope(
            message_id="prior",
            session_id="followup",
            content="Move Gaia's left leg",
            created_at=now,
            principal_id="sparks",
            channel="desktop",
        )
    )
    followup = coordinator.evaluate(
        TurnEnvelope(
            message_id="followup",
            session_id="followup",
            content="tell me more",
            created_at=now,
            principal_id="sparks",
            channel="desktop",
        )
    )

    merged = _inherit_last_turn_domains(followup, prior)
    plan = MatrixContextPlanner().plan(merged)

    assert merged.relevance_for(MatrixDomain.BODY) is MatrixRelevance.CONTEXTUAL
    assert merged.relevance_for(MatrixDomain.SOCIAL) is not MatrixRelevance.NONE
    assert plan.allows(MatrixDomain.BODY) is True



def test_secondary_continuity_hook_failures_do_not_break_current_reply(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    service = application.conversation

    class BrokenLearning:
        @staticmethod
        def observe_user_message(**kwargs):
            raise RuntimeError("learning unavailable")

    class BrokenHabit:
        patterns = SimpleNamespace(
            patterns=lambda **kwargs: (),
        )

        @staticmethod
        def observe_conversation(**kwargs):
            raise RuntimeError("habit unavailable")

    class BrokenRelationship:
        @staticmethod
        def observe(**kwargs):
            raise RuntimeError("relationship unavailable")

        @staticmethod
        def history(*args, **kwargs):
            return ()

    service._learning_coordinator = BrokenLearning()
    service._habit_continuity = BrokenHabit()
    service._relationship_store = BrokenRelationship()

    try:
        response = service.respond(
            "Hello, Sofía.",
            principal=local_sparks_principal(),
        )
        assert response.content == "Test cognitive response."
        assert service.last_post_persistence_errors == (
            "learning:RuntimeError",
            "habit:RuntimeError",
            "relationship:RuntimeError",
        )
        messages = service.messages()
        assert messages[-2].role is ConversationRole.USER
        assert messages[-1].role is ConversationRole.ASSISTANT
    finally:
        application.shutdown()



def test_pre_response_refresh_failure_is_nonfatal_and_reported(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    service = application.conversation

    def broken_refresh(**kwargs):
        raise RuntimeError("synthetic live-state refresh failure")

    service.set_pre_response_hook(broken_refresh)

    try:
        response = service.respond("Hello, Sofía.")
        assert response.content == "Test cognitive response."
        assert service.last_pre_response_error == "RuntimeError"
        messages = service.messages()
        assert messages[-2].role is ConversationRole.USER
        assert messages[-1].role is ConversationRole.ASSISTANT
    finally:
        application.shutdown()



def test_blank_input_does_not_bind_session_principal(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()
    session_id = application.conversation.session_id
    assert session_id is not None

    try:
        with pytest.raises(ValueError, match="must not be empty"):
            application.conversation.respond(
                "   ",
                principal=local_sparks_principal(),
            )

        bindings = SocialSessionStore(
            application.runtime.configuration.state_path
        )
        assert bindings.get(session_id) is None
    finally:
        application.shutdown()
