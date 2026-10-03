"""First-class REL + HABIT matrix domain and scoped projection tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.cognition.matrix import (
    ContextPlan,
    EvidenceKind,
    HistoryPolicy,
    MatrixContextPlanner,
    MatrixCoordinator,
    MatrixDomain,
    MatrixEvidencePlanner,
    MatrixPrivacyPlanner,
    MatrixRelevance,
    TurnEnvelope,
)
from sofia.cognition.matrix.defaults import default_matrix_registry
from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
)
from sofia.habits.patterns import (
    CadenceKind,
    HabitCategory,
    HabitLifecycle,
    HabitPattern,
)
from sofia.rel.model import RelationshipContact
from sofia.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)


def envelope(content: str) -> TurnEnvelope:
    return TurnEnvelope(
        message_id="turn-1",
        session_id="session-1",
        content=content,
        created_at=NOW,
        principal_id="sparks",
    )


def coordinator() -> MatrixCoordinator:
    return MatrixCoordinator(registry=default_matrix_registry())


def principal() -> PrincipalContext:
    return PrincipalContext(
        principal_id="sparks",
        audience_id="owner-private",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )


def pattern() -> HabitPattern:
    return HabitPattern(
        pattern_id="habit-1",
        principal_id="sparks",
        audience_id="owner-private",
        category=HabitCategory.CONVERSATION_ROUTINE,
        cadence=CadenceKind.DAILY,
        context={
            "observation_kind": "conversation.user_message",
            "daypart": "evening",
            "day_type": "weekday",
        },
        support_count=4,
        contradiction_count=0,
        observable_count=4,
        first_seen=NOW - timedelta(days=7),
        last_seen=NOW - timedelta(days=1),
        confidence=0.6,
        lifecycle=HabitLifecycle.ESTABLISHED,
        evidence_refs=("habit-evidence-1",),
    )


def test_relationship_question_is_first_class_required_domain():
    turn = coordinator().evaluate(
        envelope("How long was I gone?")
    )

    assert turn.relevance_for(MatrixDomain.REL) is MatrixRelevance.REQUIRED
    plan = MatrixContextPlanner().plan(turn)
    assert MatrixDomain.REL in plan.included_domains

    evidence = MatrixEvidencePlanner().plan(
        turn,
        envelope("How long was I gone?"),
    )
    requirement = next(
        item
        for item in evidence.requirements
        if item.key == "relationship.prior_contact"
    )
    assert requirement.kind is EvidenceKind.REMEMBERED
    assert requirement.required is True


def test_social_checkin_can_use_relationship_context_without_requiring_history():
    turn = coordinator().evaluate(envelope("hru"))

    assert turn.relevance_for(MatrixDomain.REL) is MatrixRelevance.CONTEXTUAL
    evidence = MatrixEvidencePlanner().plan(turn, envelope("hru"))
    requirement = next(
        item
        for item in evidence.requirements
        if item.key == "relationship.prior_contact"
    )
    assert requirement.required is False


def test_explicit_routine_language_is_first_class_habit_domain():
    turn = coordinator().evaluate(
        envelope("You know I normally get home around 5")
    )

    assert turn.relevance_for(MatrixDomain.HABIT) is MatrixRelevance.REQUIRED
    plan = MatrixContextPlanner().plan(turn)
    assert MatrixDomain.HABIT in plan.included_domains

    evidence = MatrixEvidencePlanner().plan(
        turn,
        envelope("You know I normally get home around 5"),
    )
    requirement = next(
        item
        for item in evidence.requirements
        if item.key == "habit.patterns"
    )
    assert requirement.kind is EvidenceKind.REMEMBERED
    assert requirement.required is True


class _Social:
    def get(self, session_id):
        assert session_id == "session-1"
        return principal()


class _Relationship:
    def history(self, principal_id):
        assert principal_id == "sparks"
        return (
            RelationshipContact(
                principal_id="sparks",
                audience_id="owner-private",
                evidence_ref="prior-message",
                occurred_at=NOW - timedelta(days=3),
                display_name="Sparks",
            ),
            RelationshipContact(
                principal_id="sparks",
                audience_id="shared-room",
                evidence_ref="shared-message",
                occurred_at=NOW - timedelta(days=1),
                display_name="Sparks",
            ),
            RelationshipContact(
                principal_id="other-principal",
                audience_id="owner-private",
                evidence_ref="other-principal-message",
                occurred_at=NOW - timedelta(hours=12),
                display_name="Other",
            ),
            RelationshipContact(
                principal_id="sparks",
                audience_id="owner-private",
                evidence_ref="current-message",
                occurred_at=NOW,
                display_name="Sparks",
            ),
        )


class _Patterns:
    def patterns(self, *, principal_id, audience_id):
        assert principal_id == "sparks"
        assert audience_id == "owner-private"
        return (pattern(),)


def _service_for_projection() -> ConversationService:
    service = object.__new__(ConversationService)
    service._session = SimpleNamespace(id="session-1")
    service._social_store = _Social()
    service._relationship_store = _Relationship()
    service._habit_continuity = SimpleNamespace(patterns=_Patterns())
    service._current_context_plan = ContextPlan(
        included_domains=(MatrixDomain.REL, MatrixDomain.HABIT),
        excluded_domains=tuple(
            domain
            for domain in MatrixDomain
            if domain not in {MatrixDomain.REL, MatrixDomain.HABIT}
        ),
        history_policy=HistoryPolicy.BOUNDED_RECENT,
    )
    service._current_privacy_plan = MatrixPrivacyPlanner().plan(principal())
    return service


def test_scoped_projection_uses_previous_relationship_contact_not_current_turn():
    service = _service_for_projection()
    current = ConversationMessage(
        id="current-message",
        session_id="session-1",
        role=ConversationRole.USER,
        content="How long was I gone?",
        created_at=NOW,
    )

    messages = service._matrix_person_scoped_context_messages(
        current_user=current,
    )
    text = "\n".join(message.content for message in messages)

    assert "TRUSTED RELATIONSHIP CONTACT EVIDENCE" in text
    assert "prior-message" in text
    assert "other-principal-message" not in text
    assert "current-message" not in text
    assert (NOW - timedelta(days=3)).isoformat() in text


def test_habit_projection_preserves_lifecycle_and_confidence_instead_of_overclaiming():
    service = _service_for_projection()
    current = ConversationMessage(
        id="current-message",
        session_id="session-1",
        role=ConversationRole.USER,
        content="What do I normally do?",
        created_at=NOW,
    )

    messages = service._matrix_person_scoped_context_messages(
        current_user=current,
    )
    text = "\n".join(message.content for message in messages)

    assert "TRUSTED HABIT PATTERN EVIDENCE" in text
    assert "lifecycle=established" in text
    assert "confidence=0.6000" in text
    assert "Tentative patterns must not be described as established" in text


def test_rel_habit_evidence_is_principal_scoped_and_excludes_current_contact():
    service = _service_for_projection()

    evidence = service._matrix_person_scoped_evidence(
        principal=principal(),
        current_message_id="current-message",
    )

    assert evidence["relationship.prior_contact"].source_ref == "prior-message"
    assert evidence["habit.patterns"].source_ref == "habit-pattern:habit-1"


def test_shared_audience_does_not_receive_private_history_or_private_avatar_scope():
    shared = PrincipalContext(
        principal_id="sparks",
        audience_id="shared-room",
        audience_kind=AudienceKind.SHARED,
        display_name="Sparks",
    )

    plan = MatrixPrivacyPlanner().plan(shared)

    assert plan.allow_audience_scope is True
    assert plan.allow_relationship_scope is True
    assert plan.allow_historical_private_scope is False
    assert plan.allow_private_presentation_candidate is False
