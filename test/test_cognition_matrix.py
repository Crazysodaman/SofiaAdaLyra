from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.cognition.matrix.defaults import default_matrix_registry
from sofia.cognition.matrix import (
    BaselineTurnClassifier,
    DomainContribution,
    HistoryPolicy,
    MatrixCoordinator,
    MatrixDomain,
    MatrixIntent,
    MatrixRegistry,
    MatrixRelevance,
    MatrixTrace,
    MatrixTraceStore,
    ResponseStrategy,
    TurnEnvelope,
)


NOW = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)


def envelope(content: str, *, message_id: str = "m1") -> TurnEnvelope:
    return TurnEnvelope(
        message_id=message_id,
        session_id="session-1",
        content=content,
        created_at=NOW,
        principal_id="sparks",
        channel="discord",
    )


@pytest.mark.parametrize(
    ("content", "intent", "history", "strategy", "required_domain"),
    (
        (
            "Hru",
            MatrixIntent.SOCIAL_CHECKIN,
            HistoryPolicy.NONE,
            ResponseStrategy.GENERATIVE,
            MatrixDomain.SOCIAL,
        ),
        (
            "what's the weather?",
            MatrixIntent.ENVIRONMENT_QUERY,
            HistoryPolicy.NONE,
            ResponseStrategy.DETERMINISTIC,
            MatrixDomain.ENVIRONMENT,
        ),
        (
            "what are you wearing",
            MatrixIntent.AVATAR_QUERY,
            HistoryPolicy.NONE,
            ResponseStrategy.HYBRID,
            MatrixDomain.AVATAR,
        ),
        (
            "how did u feel doing it",
            MatrixIntent.INTERACTION_FOLLOWUP,
            HistoryPolicy.LAST_TURN,
            ResponseStrategy.GENERATIVE,
            MatrixDomain.INTERACTION,
        ),
        (
            "what did I say earlier about Artemis?",
            MatrixIntent.MEMORY_QUERY,
            HistoryPolicy.RETRIEVE_SPECIFIC,
            ResponseStrategy.HYBRID,
            MatrixDomain.MEMORY,
        ),
        (
            "what model are you running?",
            MatrixIntent.OPERATIONAL_QUERY,
            HistoryPolicy.NONE,
            ResponseStrategy.DETERMINISTIC,
            MatrixDomain.COGNITION,
        ),
        (
            "restart Plex on Dionysus",
            MatrixIntent.ACTION_REQUEST,
            HistoryPolicy.BOUNDED_RECENT,
            ResponseStrategy.TOOL_ASSISTED,
            MatrixDomain.AUTHORITY,
        ),
    ),
)
def test_baseline_turn_classifier(
    content,
    intent,
    history,
    strategy,
    required_domain,
):
    result = BaselineTurnClassifier().classify(envelope(content))

    assert result.intent is intent
    assert result.history_policy is history
    assert result.response_strategy is strategy
    assert result.relevance_for(required_domain) is MatrixRelevance.REQUIRED


def test_general_turn_keeps_bounded_recent_context():
    result = BaselineTurnClassifier().classify(
        envelope("Tell me about hexapod gait planning.")
    )

    assert result.intent is MatrixIntent.GENERAL
    assert result.history_policy is HistoryPolicy.BOUNDED_RECENT
    assert result.relevance_for(MatrixDomain.SOCIAL) is (
        MatrixRelevance.CONTEXTUAL
    )


def test_domain_evaluator_can_raise_but_not_lower_relevance():
    class EmotionEvaluator:
        domain = MatrixDomain.EMOTION

        def evaluate(self, envelope, turn):
            return DomainContribution(
                MatrixDomain.EMOTION,
                MatrixRelevance.REQUIRED,
                "test evaluator requires emotion",
            )

    coordinator = MatrixCoordinator(
        registry=MatrixRegistry((EmotionEvaluator(),))
    )
    result = coordinator.evaluate(envelope("Hru"))

    assert result.relevance_for(MatrixDomain.EMOTION) is (
        MatrixRelevance.REQUIRED
    )


def test_registry_rejects_duplicate_domain_evaluators():
    class One:
        domain = MatrixDomain.AVATAR

        def evaluate(self, envelope, turn):
            return None

    class Two:
        domain = MatrixDomain.AVATAR

        def evaluate(self, envelope, turn):
            return None

    with pytest.raises(ValueError, match="duplicate matrix evaluator"):
        MatrixRegistry((One(), Two()))


def test_trace_store_does_not_duplicate_message_text(tmp_path):
    store = MatrixTraceStore(tmp_path / "sofia.db")
    turn = MatrixCoordinator().evaluate(
        envelope("Hru", message_id="message-1")
    )
    trace = MatrixTrace(
        envelope=envelope(
            "SECRET TEXT SHOULD NOT BE COPIED",
            message_id="message-1",
        ),
        turn=turn,
        created_at=NOW,
        shadow=True,
    )

    store.record(trace)

    loaded = store.get("message-1")
    assert loaded is not None
    assert loaded.turn.intent is MatrixIntent.SOCIAL_CHECKIN
    assert loaded.shadow is True
    assert loaded.envelope.content == "[not stored in matrix trace]"

    with sqlite3.connect(tmp_path / "sofia.db") as db:
        row = db.execute(
            """
            SELECT domains_json FROM cognition_matrix_trace
            WHERE message_id='message-1'
            """
        ).fetchone()
        dump = row[0]

    assert "SECRET TEXT SHOULD NOT BE COPIED" not in dump


def test_latest_trace_is_scoped_by_session(tmp_path):
    store = MatrixTraceStore(tmp_path / "sofia.db")
    coordinator = MatrixCoordinator()

    first = envelope("Hru", message_id="one")
    store.record(
        MatrixTrace(
            envelope=first,
            turn=coordinator.evaluate(first),
            created_at=NOW,
        )
    )
    second = TurnEnvelope(
        message_id="two",
        session_id="session-2",
        content="what's the weather?",
        created_at=NOW.replace(second=1),
        channel="desktop",
    )
    store.record(
        MatrixTrace(
            envelope=second,
            turn=coordinator.evaluate(second),
            created_at=NOW.replace(second=1),
        )
    )

    assert store.latest(session_id="session-1").envelope.message_id == "one"
    assert store.latest(session_id="session-2").envelope.message_id == "two"
    assert store.latest().envelope.message_id == "two"


def test_state_changing_avatar_request_is_action_not_read_only_avatar_query():
    result = MatrixCoordinator(
        registry=default_matrix_registry()
    ).evaluate(envelope("change your outfit"))

    assert result.intent is MatrixIntent.ACTION_REQUEST
    assert result.relevance_for(MatrixDomain.AUTHORITY) is (
        MatrixRelevance.REQUIRED
    )
    assert result.relevance_for(MatrixDomain.AVATAR) is MatrixRelevance.NONE


def test_default_registry_has_one_owner_per_registered_domain():
    registry = default_matrix_registry()
    domains = tuple(evaluator.domain for evaluator in registry.evaluators)

    assert len(domains) == len(set(domains))
    assert set(domains) == {
        MatrixDomain.SOCIAL,
        MatrixDomain.EMOTION,
        MatrixDomain.ENVIRONMENT,
        MatrixDomain.AVATAR,
        MatrixDomain.INTERACTION,
        MatrixDomain.MEMORY,
        MatrixDomain.COGNITION,
        MatrixDomain.MACHINE,
        MatrixDomain.OPS,
        MatrixDomain.AUTHORITY,
    }


def test_machine_domain_can_strengthen_operational_relevance():
    result = MatrixCoordinator(
        registry=default_matrix_registry()
    ).evaluate(envelope("how is the network"))

    assert result.intent is MatrixIntent.OPERATIONAL_QUERY
    assert result.relevance_for(MatrixDomain.MACHINE) is (
        MatrixRelevance.REQUIRED
    )
