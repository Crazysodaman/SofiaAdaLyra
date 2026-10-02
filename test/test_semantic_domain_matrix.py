"""Semantic DEV/KNOW/INTEGRATE/BODY matrix routing tests."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.cognition.matrix import (
    AuthorityDecision,
    AuthorityPlan,
    MatrixCoordinator,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    MatrixToolExposurePlanner,
    TurnEnvelope,
)
from sofia.cognition.matrix.defaults import default_matrix_registry


NOW = datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc)


def evaluate(content: str):
    envelope = TurnEnvelope(
        message_id="semantic-turn",
        session_id="semantic-session",
        content=content,
        created_at=NOW,
        principal_id="sparks",
    )
    turn = MatrixCoordinator(
        registry=default_matrix_registry()
    ).evaluate(envelope)
    return envelope, turn


def allowed_tools(envelope, turn):
    return MatrixToolExposurePlanner().plan(
        envelope,
        turn,
        AuthorityPlan(
            AuthorityDecision.ALLOWED,
            requested_action=envelope.content,
            reason="test-only allowed authority fixture",
        ),
    )


def test_code_edit_is_dev_not_generic_ops():
    envelope, turn = evaluate(
        "Edit the Python code in this repo to fix the test"
    )

    assert turn.intent is MatrixIntent.ACTION_REQUEST
    assert turn.relevance_for(MatrixDomain.DEV) is MatrixRelevance.REQUIRED
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.AUTHORITY) is MatrixRelevance.REQUIRED

    exposure = allowed_tools(envelope, turn)
    assert "codebase.inspect" in exposure.capabilities
    assert "dev.status" in exposure.capabilities
    assert "dev.build" in exposure.capabilities
    assert not any(
        capability.startswith("local.service.")
        for capability in exposure.capabilities
    )


def test_project_document_write_is_know_not_generic_ops():
    envelope, turn = evaluate(
        "Write the project documentation file"
    )

    assert turn.intent is MatrixIntent.ACTION_REQUEST
    assert turn.relevance_for(MatrixDomain.KNOW) is MatrixRelevance.REQUIRED
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE

    exposure = allowed_tools(envelope, turn)
    assert "knowledge.document" in exposure.capabilities
    assert "knowledge.document.write" in exposure.capabilities


def test_jmri_power_control_is_integrate_action_not_generic_ops():
    envelope, turn = evaluate(
        "Turn JMRI track power on"
    )

    assert turn.intent is MatrixIntent.ACTION_REQUEST
    assert (
        turn.relevance_for(MatrixDomain.INTEGRATE)
        is MatrixRelevance.REQUIRED
    )
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.AUTHORITY) is MatrixRelevance.REQUIRED

    exposure = allowed_tools(envelope, turn)
    assert "jmri.power" in exposure.capabilities
    assert "jmri.power.set" in exposure.capabilities


def test_gaia_motion_is_body_action_and_does_not_fall_into_ops():
    envelope, turn = evaluate(
        "Move Gaia's left leg"
    )

    assert turn.intent is MatrixIntent.ACTION_REQUEST
    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.REQUIRED
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.AUTHORITY) is MatrixRelevance.REQUIRED

    # BODY has no cognitive physical-motion tool binding yet. Semantic routing
    # must not compensate by exposing unrelated OPS controls.
    exposure = allowed_tools(envelope, turn)
    assert exposure.capabilities == ()


def test_reading_a_pdf_is_know_without_action_authority():
    _, turn = evaluate(
        "What does this PDF documentation say?"
    )

    assert turn.intent is MatrixIntent.GENERAL
    assert turn.relevance_for(MatrixDomain.KNOW) is MatrixRelevance.REQUIRED
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.AUTHORITY) is MatrixRelevance.NONE


def test_ordinary_service_restart_remains_ops():
    _, turn = evaluate(
        "Restart the Plex service"
    )

    assert turn.intent is MatrixIntent.ACTION_REQUEST
    assert turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.RELEVANT
    assert turn.relevance_for(MatrixDomain.DEV) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.KNOW) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.INTEGRATE) is MatrixRelevance.NONE
    assert turn.relevance_for(MatrixDomain.BODY) is MatrixRelevance.NONE
