from datetime import datetime, timezone

from sofia.body.matrix import BodyMatrixEvaluator
from sofia.cognition.matrix import (
    BaselineTurnClassifier,
    MatrixDomain,
    MatrixRelevance,
    TurnEnvelope,
)


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

    contribution = BodyMatrixEvaluator().evaluate(envelope, turn)

    assert contribution is not None
    assert contribution.domain is MatrixDomain.BODY
    assert contribution.relevance is MatrixRelevance.REQUIRED


def test_body_matrix_ignores_unrelated_chat():
    envelope = _envelope("How are you?")
    turn = BaselineTurnClassifier().classify(envelope)

    assert BodyMatrixEvaluator().evaluate(envelope, turn) is None
