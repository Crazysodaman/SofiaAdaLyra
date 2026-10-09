from datetime import datetime, timezone

from test.matrix_v2_support import V2TurnClassifier as BaselineTurnClassifier
from sofia.cognition.matrix import (
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

    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.REQUIRED


def test_body_matrix_ignores_unrelated_chat():
    envelope = _envelope("How are you?")
    turn = BaselineTurnClassifier().classify(envelope)

    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.NONE
