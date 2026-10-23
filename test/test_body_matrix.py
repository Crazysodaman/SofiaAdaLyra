from datetime import datetime, timezone

from test.matrix_v2_support import V2TurnClassifier as BaselineTurnClassifier
from sofia.core.cognition.matrix import (
    AuthorityDecision,
    AuthorityPlan,
    ContextualInfluenceMatrix,
    DomainContribution,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceState,
    HistoryPolicy,
    InfluenceDecision,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
    MatrixConfidence,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    MatrixResponsePlanner,
    MatrixResponseValidator,
    ResponseStrategy,
    ResponseValidationDisposition,
    TurnEnvelope,
    TurnMatrix,
)
from sofia.core.cognition.matrix.influence import ContinuityInfluence
from sofia.core.cognition.model import CognitiveResponse


NOW = datetime(2026, 10, 4, 20, 0, tzinfo=timezone.utc)


def _envelope(content: str) -> TurnEnvelope:
    return TurnEnvelope(
        message_id="body-test",
        session_id="session-1",
        content=content,
        created_at=NOW,
        principal_id="sparks",
        channel="local",
    )


def test_body_matrix_requires_body_domain_for_hexapod_context():
    envelope = _envelope("Explain the Gaia hexapod servo limits.")
    turn = BaselineTurnClassifier().classify(envelope)

    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.REQUIRED


def test_body_matrix_ignores_unrelated_chat():
    envelope = _envelope("How are you?")
    turn = BaselineTurnClassifier().classify(envelope)

    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.NONE


def _body_turn() -> TurnMatrix:
    return TurnMatrix(
        intent=MatrixIntent.ACTION_REQUEST,
        confidence=MatrixConfidence.HIGH,
        history_policy=HistoryPolicy.NONE,
        response_strategy=ResponseStrategy.HYBRID,
        domains=(
            DomainContribution(
                MatrixDomain.BODY,
                MatrixRelevance.REQUIRED,
                "physical body request",
            ),
        ),
    )


def _social_turn() -> TurnMatrix:
    return TurnMatrix(
        intent=MatrixIntent.SOCIAL_CHECKIN,
        confidence=MatrixConfidence.MEDIUM,
        history_policy=HistoryPolicy.NONE,
        response_strategy=ResponseStrategy.GENERATIVE,
        domains=(
            DomainContribution(
                MatrixDomain.SOCIAL,
                MatrixRelevance.RELEVANT,
                "social check-in",
            ),
        ),
    )


def test_body_safety_surface_is_never_contextually_influenced():
    matrix = ContextualInfluenceMatrix()
    for signal in InfluenceSignal:
        assert matrix.policy_mode(InfluenceSurface.BODY_SAFETY, signal) \
            is InfluenceMode.NONE

    # Emotion, weather, daypart and season are all independently proven for
    # this snapshot, so a NONE here can only come from the surface policy
    # and not from missing evidence.
    influence = ContinuityInfluence(
        daypart="evening",
        season="autumn",
        daylight="night",
        weather_condition="rainy",
        temperature_c=12.0,
        weather_freshness="current",
        location_freshness="current",
        primary_emotion_evidence_refs=("emotion:event-1",),
        emotional_tone="warm",
        primary_emotion="fondness",
        primary_intensity=0.62,
        active_emotions=("fondness", "curiosity"),
        foreground_emotion_evidence_refs=("emotion:event-2",),
        foreground_emotion="curiosity",
        foreground_intensity=0.55,
        daypart_evidence_refs=("runtime.clock", "environment.location:configured"),
        season_evidence_refs=("runtime.clock", "environment.location:configured"),
        weather_evidence_refs=("environment.weather:matrix-weather",),
    )
    plan = matrix.plan(InfluenceSurface.BODY_SAFETY, influence)
    for signal in InfluenceSignal:
        decision: InfluenceDecision = plan.decision_for(signal)
        assert decision.mode is InfluenceMode.NONE
        assert decision.reason == (
            "this decision surface does not permit this contextual signal"
        )
        assert decision.evidence_refs == ()


def test_physical_body_execution_claim_without_receipt_is_rejected():
    turn = _body_turn()
    authority = AuthorityPlan(
        decision=AuthorityDecision.ALLOWED,
        requested_action="body.hexapod_servo_limits",
    )
    contract = MatrixResponsePlanner().plan(turn, EvidenceMatrix(), authority)
    assert contract.requires_execution_receipt is True

    response = CognitiveResponse(
        content="I restarted the hexapod servo controller on Gaia.",
    )
    validation = MatrixResponseValidator().validate(
        response, contract, EvidenceMatrix(), turn=turn,
    )

    assert validation.disposition is ResponseValidationDisposition.RETRY
    assert "execution_claim_without_receipt" in validation.reasons


def test_physical_body_execution_claim_with_act_receipt_passes():
    turn = _body_turn()
    authority = AuthorityPlan(
        decision=AuthorityDecision.ALLOWED,
        requested_action="body.hexapod_servo_limits",
    )
    contract = MatrixResponsePlanner().plan(turn, EvidenceMatrix(), authority)
    evidence = EvidenceMatrix(
        records=(
            EvidenceRecord(
                "action.execution_receipt",
                EvidenceState.AVAILABLE,
                source_ref=                "act:gaia-hexapod-servo-1",
            ),
        ),
    )
    response = CognitiveResponse(
        content="I restarted the hexapod servo controller on Gaia.",
        evidence_refs=(                "act:gaia-hexapod-servo-1",),
    )
    validation = MatrixResponseValidator().validate(
        response, contract, evidence, turn=turn,
    )

    assert validation.disposition is ResponseValidationDisposition.PASS
    assert validation.reasons == ()


def test_unauthorized_body_execution_claim_names_the_authority_boundary():
    turn = _body_turn()
    authority = AuthorityPlan(
        decision=AuthorityDecision.DENIED,
        requested_action="body.hexapod_servo_limits",
        reason="no FIDO2 approval for physical motion",
    )
    contract = MatrixResponsePlanner().plan(turn, EvidenceMatrix(), authority)
    response = CognitiveResponse(
        content="I restarted the hexapod servo controller on Gaia.",
    )
    validation = MatrixResponseValidator().validate(
        response, contract, EvidenceMatrix(), turn=turn,
    )
    fallback = MatrixResponseValidator().fallback(validation, contract)

    assert validation.disposition is ResponseValidationDisposition.RETRY
    assert "execution_claim_without_action_authority" in validation.reasons
    assert "I don't have authority to execute or claim completion" \
        in fallback.content
    assert "Gaia" not in fallback.content


def test_social_turn_stacking_body_machinery_metaphors_is_discarded():
    turn = _social_turn()
    contract = MatrixResponsePlanner().plan(
        turn,
        EvidenceMatrix(),
        AuthorityPlan(decision=AuthorityDecision.NOT_REQUIRED),
    )
    response = CognitiveResponse(
        content=(
            "My subroutine coolant loop is a bit dusty, and my cooling fan "
            "has opinions about your day."
        ),
    )
    validation = MatrixResponseValidator().validate(
        response, contract, EvidenceMatrix(), turn=turn,
    )
    fallback = MatrixResponseValidator().fallback(validation, contract)

    assert validation.disposition is ResponseValidationDisposition.RETRY
    assert "social_machinery_metaphor_stack" in validation.reasons
    assert "stacked system metaphors" in fallback.content
    assert "coolant" not in fallback.content


def test_single_body_metaphor_remains_valid_social_personality():
    turn = _social_turn()
    contract = MatrixResponsePlanner().plan(
        turn,
        EvidenceMatrix(),
        AuthorityPlan(decision=AuthorityDecision.NOT_REQUIRED),
    )
    response = CognitiveResponse(
        content="One subroutine of mine is getting tired of Monday mornings.",
    )
    validation = MatrixResponseValidator().validate(
        response, contract, EvidenceMatrix(), turn=turn,
    )

    assert validation.disposition is ResponseValidationDisposition.PASS
    assert validation.reasons == ()
