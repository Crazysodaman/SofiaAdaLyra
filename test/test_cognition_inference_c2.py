"""Core C2: bounded provider, failover, multi-turn and continuity contracts.

All model interaction here uses a fake transport or a local SQLite conversation
store. No live Ollama process, model download, cloud provider or credential is
required.
"""
from datetime import datetime, timedelta, timezone
from threading import Event
import time
from types import SimpleNamespace

import pytest
from ollama import ResponseError

from sofia.core.cognition.conversation_assembler import (
    BoundedConversationContext,
    ConversationContextBudget,
    ConversationContextError,
    ConversationalContextAssembler,
    build_bounded_conversation_context,
)
from sofia.core.cognition.context import CognitiveContext
from sofia.core.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.core.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.core.cognition.output_guard import contains_internal_reasoning_leak
from sofia.core.cognition.routing import (
    CognitiveEngineRegistry,
    ProviderSelectionError,
    ProviderSelectionPolicy,
    RoutingCognitiveEngine,
)
from sofia.core.conversation.model import ConversationMessage, ConversationRole
from sofia.core.conversation.store import (
    ConversationContinuityError,
    ConversationStore,
)
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.core_worker.ollama_transport import (
    OLLAMA_IO_TIMEOUT_SECONDS,
    OLLAMA_MAX_REQUEST_BYTES,
    GenericOllamaProvider,
)
from sofia.platform.core_worker.provider_deadline import call_with_deadline
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _configuration(provider: str = "ollama", model: str = "owner/model:exact"):
    return ProviderConfiguration(provider=provider, model=model)


class _FakeClient:
    def __init__(self, *, response=None, error=None, on_call=None):
        self.response = response
        self.error = error
        self.on_call = on_call
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.on_call is not None:
            self.on_call()
        if self.error is not None:
            raise self.error
        return self.response


def _reply(content="provider reply", *, tool_calls=()):
    return SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=tool_calls),
    )


def _request(text="Hello.", *, route_hint=None):
    return CognitiveRequest(
        messages=(CognitiveMessage(role=CognitiveRole.USER, content=text),),
        allow_tools=False,
        route_hint=route_hint,
    )


@pytest.mark.parametrize(
    "error, expected",
    [
        (ConnectionRefusedError("offline"), "connect"),
        (ConnectionResetError("reset"), "read"),
        (TimeoutError("slow"), "timeout"),
    ],
)
def test_transport_errors_are_classified_with_bounded_timeout(error, expected):
    client = _FakeClient(error=error)
    provider = GenericOllamaProvider(_configuration(), client=client)
    with pytest.raises(Exception) as failure:
        provider.respond(_request())
    assert failure.value.category.value == expected
    assert failure.value.kind.value == expected
    assert failure.value.provider == "ollama"
    assert failure.value.model == "owner/model:exact"
    assert failure.value.timeout_seconds == OLLAMA_IO_TIMEOUT_SECONDS
    assert failure.value.retryable is True
    assert failure.value.is_transport_failure is True
    assert failure.value.__cause__ is error
    assert len(client.calls) == 1


def test_http_status_controls_failover_eligibility():
    for status, retryable in ((429, True), (503, True), (404, False), (400, False)):
        client = _FakeClient(
            error=ResponseError("synthetic", status_code=status)
        )
        provider = GenericOllamaProvider(_configuration(), client=client)
        with pytest.raises(Exception) as failure:
            provider.respond(_request())
        assert failure.value.category.value == "http"
        assert failure.value.status_code == status
        assert failure.value.retryable is retryable
        assert failure.value.is_transport_failure is retryable


def test_stream_and_unknown_failures_are_not_silent_success():
    class StreamError(Exception):
        pass

    stream = GenericOllamaProvider(
        _configuration(), client=_FakeClient(error=StreamError("broken")),
    )
    with pytest.raises(Exception) as stream_failure:
        stream.respond(_request())
    assert stream_failure.value.category.value == "stream"
    assert stream_failure.value.is_transport_failure is True

    unknown = GenericOllamaProvider(
        _configuration(), client=_FakeClient(error=RuntimeError("bug")),
    )
    with pytest.raises(Exception) as unknown_failure:
        unknown.respond(_request())
    assert unknown_failure.value.category.value == "unknown"
    assert unknown_failure.value.is_transport_failure is False


def test_oversized_request_is_rejected_before_transport_io():
    client = _FakeClient(response=_reply())
    provider = GenericOllamaProvider(_configuration(), client=client)
    request = _request("x" * (OLLAMA_MAX_REQUEST_BYTES + 1))
    with pytest.raises(Exception) as failure:
        provider.respond(request)
    assert failure.value.category.value == "invalid_request"
    assert failure.value.retryable is False
    assert client.calls == []


def test_cancellation_is_deterministic_before_and_after_transport():
    client = _FakeClient(response=_reply("must not be published"))
    provider = GenericOllamaProvider(_configuration(), client=client)
    provider.cancel()
    with pytest.raises(Exception) as failure:
        provider.respond(_request())
    assert failure.value.category.value == "cancelled"
    assert client.calls == []

    late_provider = GenericOllamaProvider(
        _configuration(),
        client=_FakeClient(response=_reply("late")),
    )
    late_client = late_provider.client
    late_client.on_call = late_provider.cancel
    with pytest.raises(Exception) as late_failure:
        late_provider.respond(_request())
    assert late_failure.value.category.value == "cancelled"
    assert len(late_client.calls) == 1


def test_missing_model_is_reported_once_without_silent_download_or_retry():
    calls = []

    class MissingModelClient:
        def chat(self, **kwargs):
            calls.append(kwargs)
            raise ResponseError("synthetic model missing", status_code=404)

    provider = GenericOllamaProvider(
        _configuration(model="missing:disposable"),
        client=MissingModelClient(),
    )
    with pytest.raises(Exception) as failure:
        provider.respond(_request())
    assert failure.value.category.value == "http"
    assert failure.value.status_code == 404
    assert failure.value.retryable is False
    assert len(calls) == 1


def test_empty_provider_completion_is_a_failure_not_an_assistant_turn():
    provider = GenericOllamaProvider(
        _configuration(), client=_FakeClient(response=_reply("   ")),
    )
    with pytest.raises(Exception, match="empty cognitive response"):
        provider.respond(_request())


def test_deadline_cancellation_callback_is_deterministic():
    cancelled = Event()

    def blocked():
        time.sleep(0.2)
        return "late-result"

    with pytest.raises(TimeoutError, match="deadline expired"):
        call_with_deadline(
            blocked, deadline=time.monotonic() + 0.02,
            cancel=cancelled.set,
        )
    assert cancelled.is_set()


class _StaticEngine(CognitiveEngine):
    def __init__(self, configuration, *, response=None, error=None, host=None):
        self.configuration = configuration
        self.response = response
        self.error = error
        self.calls = 0
        self.last_host_id = host

    def respond(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _registry(primary, secondary):
    return CognitiveEngineRegistry(primary=primary, secondary=secondary)


def _policy(configurations, *, order=("primary", "secondary")):
    return ProviderSelectionPolicy(
        order=order, configured=configurations,
        allowed_providers=("ollama", "test-llm"),
    )


def test_failover_only_uses_configured_transport_failure_and_records_provenance():
    primary_config = _configuration(model="primary:model")
    secondary_config = _configuration(model="secondary:model")
    primary = _StaticEngine(
        primary_config,
        error=CognitiveEngineError(
            "transport down", category="connect", retryable=True,
        ),
    )
    secondary = _StaticEngine(
        secondary_config, response=CognitiveResponse("secondary reply"),
        host="venus",
    )
    router = RoutingCognitiveEngine(
        _registry(primary, secondary),
        fallback_enabled=True,
        provider_policy=_policy({
            "primary": primary_config, "secondary": secondary_config,
        }),
    )

    assert router.respond(_request(route_hint="standard")).content == "secondary reply"
    assert primary.calls == 1
    assert secondary.calls == 1
    assert router.last_selection is not None
    assert tuple(item.role for item in router.last_selection) == (
        "primary", "secondary",
    )
    execution = router.last_execution
    assert execution is not None
    provenance = execution.provider_provenance
    assert provenance is not None
    assert provenance.role == "secondary"
    assert provenance.provider == "ollama"
    assert provenance.model == "secondary:model"
    assert provenance.host == "venus"
    assert execution.fallback_count == 1


def test_non_transport_failure_never_switches_provider():
    primary_config = _configuration(model="primary:model")
    secondary_config = _configuration(model="secondary:model")
    primary = _StaticEngine(
        primary_config, error=CognitiveEngineError("not a transport failure"),
    )
    secondary = _StaticEngine(
        secondary_config, response=CognitiveResponse("must not run"),
    )
    router = RoutingCognitiveEngine(
        _registry(primary, secondary),
        fallback_enabled=True,
        provider_policy=_policy({
            "primary": primary_config, "secondary": secondary_config,
        }),
    )

    with pytest.raises(CognitiveEngineError, match="not a transport failure"):
        router.respond(_request(route_hint="standard"))
    assert secondary.calls == 0


def test_selection_denies_unknown_model_mismatch_and_cloud_provider():
    primary_config = _configuration(model="primary:model")
    secondary_config = _configuration(model="secondary:model")
    primary = _StaticEngine(primary_config, response=CognitiveResponse("ok"))
    secondary = _StaticEngine(secondary_config, response=CognitiveResponse("ok"))

    with pytest.raises(ProviderSelectionError, match="unknown provider role"):
        ProviderSelectionPolicy(order=("primary", "ghost")).evaluate(
            _registry(primary, secondary)
        )

    with pytest.raises(ProviderSelectionError, match="model mismatch"):
        _policy({
            "primary": _configuration(model="other:model"),
            "secondary": secondary_config,
        }).evaluate(_registry(primary, secondary))

    cloud_primary = _StaticEngine(
        _configuration(provider="openai", model="cloud:model"),
        response=CognitiveResponse("cloud"),
    )
    with pytest.raises(ProviderSelectionError, match="cloud"):
        ProviderSelectionPolicy(
            order=("primary",),
            configured={"primary": cloud_primary.configuration},
        ).evaluate(_registry(cloud_primary, secondary))

    with pytest.raises(ProviderSelectionError, match="allowlist"):
        ProviderSelectionPolicy(
            order=("primary",), allowed_providers=("test-llm",),
        ).evaluate(_registry(primary, secondary))


def _conversation(
    store, *, count=6, session=None, size=80,
):
    session = session or store.create_session()
    messages = []
    for index in range(count):
        role = (
            ConversationRole.USER if index % 2 == 0
            else ConversationRole.ASSISTANT
        )
        message = ConversationMessage(
            id=f"message-{session.id}-{index}",
            session_id=session.id,
            role=role,
            content=f"{role.value}-{index}-" + ("x" * size),
            created_at=NOW + timedelta(seconds=index),
        )
        store.save(message)
        messages.append(message)
    return session, tuple(messages)


def test_bounded_multiturn_uses_real_turns_and_omits_oldest_without_invention(
    tmp_path,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ConversationStore(state)
    try:
        session, prior = _conversation(store)
        current = ConversationMessage(
            id="current-turn", session_id=session.id,
            role=ConversationRole.USER, content="current question",
            created_at=NOW + timedelta(seconds=20),
        )
        result = build_bounded_conversation_context(
            system_messages=(
                CognitiveMessage(CognitiveRole.SYSTEM, "trusted system"),
            ),
            prior_messages=prior,
            current_message=current,
            correlation_id="correlation:current",
            budget=ConversationContextBudget(
                max_messages=4, max_bytes=512,
            ),
        )
        assert isinstance(result, BoundedConversationContext)
        assert result.correlation_id == "correlation:current"
        assert result.session_id == session.id
        assert result.omitted_messages > 0
        assert result.messages[-1].role is CognitiveRole.USER
        assert result.messages[-1].content == "current question"
        assert result.messages[0].content == "trusted system"
        returned = {message.content for message in result.messages[1:]}
        assert returned <= {message.content for message in prior} | {
            "current question",
        }
        # No assistant turn was synthesized at the end or anywhere else.
        assert all(
            message.content in returned
            for message in result.messages[1:]
        )
        assert result.bytes_used <= 512
        assert result.token_estimate == (result.bytes_used + 3) // 4
    finally:
        store.close()


def test_bounded_multiturn_rejects_cross_session_and_oversized_turns(
    tmp_path,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ConversationStore(state)
    try:
        first, prior = _conversation(store, count=2)
        second, _ = _conversation(store, count=2)
        with pytest.raises(ConversationContextError) as crossed:
            build_bounded_conversation_context(
                prior_messages=prior,
                current_message=ConversationMessage(
                    id="wrong-session", session_id=second.id,
                    role=ConversationRole.USER, content="new",
                    created_at=NOW + timedelta(seconds=5),
                ),
                correlation_id="correlation:wrong",
            )
        assert crossed.value.reason == "mismatch"

        with pytest.raises(ConversationContextError) as oversized:
            build_bounded_conversation_context(
                prior_messages=prior,
                current_message=ConversationMessage(
                    id="too-large", session_id=first.id,
                    role=ConversationRole.USER, content="y" * 2048,
                    created_at=NOW + timedelta(seconds=5),
                ),
                correlation_id="correlation:large",
                budget=ConversationContextBudget(
                    max_messages=4, max_bytes=512,
                ),
            )
        assert oversized.value.reason == "oversized"

        with pytest.raises(ConversationContextError) as malformed:
            build_bounded_conversation_context(
                prior_messages=(
                    CognitiveMessage(CognitiveRole.ASSISTANT, ""),
                ),
                current_message=CognitiveMessage(
                    CognitiveRole.USER, "current",
                ),
                correlation_id="correlation:malformed",
            )
        assert malformed.value.reason == "malformed"
    finally:
        store.close()


def test_conversational_assembler_applies_explicit_history_budget():
    messages = tuple(
        CognitiveMessage(CognitiveRole.USER, f"prior-{index}-" + "z" * 60)
        for index in range(10)
    )
    messages += (
        CognitiveMessage(CognitiveRole.USER, "latest question"),
    )
    assembler = ConversationalContextAssembler(
        history_budget=ConversationContextBudget(
            max_messages=4, max_bytes=65_536,
        ),
    )
    assembled = assembler.assemble(CognitiveContext(
        request=CognitiveRequest(messages=messages),
    ))
    non_system = tuple(
        message for message in assembled.messages
        if message.role is not CognitiveRole.SYSTEM
    )
    assert len(non_system) <= 4
    assert non_system[-1].content == "latest question"
    assert all(message.role is not CognitiveRole.ASSISTANT
               for message in non_system)
    assert len(assembled.messages) < len(messages) + 1


def test_conversation_store_restart_resume_and_stale_unknown_handling(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ConversationStore(state)
    try:
        session, messages = _conversation(store, count=4)
    finally:
        store.close()

    reopened = ConversationStore(state)
    try:
        reference = session.updated_at
        resumed = reopened.resume_session(
            session.id, now=reference + timedelta(seconds=10),
            stale_after=timedelta(minutes=5),
        )
        assert resumed.session.id == session.id
        assert resumed.state == "current"
        assert resumed.message_count == len(messages)
        assert resumed.last_message_id == messages[-1].id

        stale = reopened.continuity(
            session.id, now=reference + timedelta(hours=1),
            stale_after=timedelta(minutes=5),
        )
        assert stale.state == "stale"
        with pytest.raises(ConversationContinuityError) as denied:
            reopened.resume_session(
                session.id, now=reference + timedelta(hours=1),
                stale_after=timedelta(minutes=5), allow_stale=False,
            )
        assert denied.value.reason == "stale"

        with pytest.raises(ConversationContinuityError) as unknown:
            reopened.resume_session("does-not-exist")
        assert unknown.value.reason == "unknown"
        assert reopened.get_session("does-not-exist") is None
    finally:
        reopened.close()


def test_output_guard_rejects_internal_reasoning_without_rewriting_content():
    assert contains_internal_reasoning_leak(
        "Analysis of the tool result\nI should answer."
    )
    assert contains_internal_reasoning_leak("Let's analyze the request")
    safe = "The verified result is available."
    assert contains_internal_reasoning_leak(safe) is False
    with pytest.raises(TypeError):
        contains_internal_reasoning_leak(None)
