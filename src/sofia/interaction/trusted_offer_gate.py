"""Opt-in, read-only boundary/stop gate around one reviewed avatar offer.

This module does not write SQLite, record consent, perform contact, animate an
avatar, or grant tools. It rechecks source-backed policy before decision,
expression and return. Atomic reply persistence belongs to the owning host.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

from sofia.cognition.model import CognitiveRequest
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.conversation_offer_context import (
    routed_conversation_choice_request, routed_conversation_expression_request,
)
from sofia.interaction.decision_expression import (
    CandidateChoice, ReviewedFrame, TextProvider, audit_expression,
    from_reviewed_action, parse_choice,
)
from sofia.interaction.decision_reason_audit import audit_decision_reason
from sofia.interaction.expression_consistency import validate_offer_expression
from sofia.interaction.preference_context import read_interaction_context

_SESSION_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$')
_REQUIRED_TABLES = (
    'conversation_messages', 'interaction_session_controls',
    'interact_boundary_revisions', 'interact_evidence_attestations',
)


@dataclass(frozen=True)
class GuardedOfferResult:
    """Model output is observable only if all read-only gates stayed clear."""

    status: str  # responded, blocked-boundary, blocked-unverified-boundary, blocked-stop
    choice: CandidateChoice | None = None
    response: str | None = None
    decision_findings: tuple[str, ...] = ()
    expression_findings: tuple[str, ...] = ()


def _policy_gate(*, state_path: Path, session_id: str) -> str | None:
    """Fail closed on missing state/schema, bad attestation and read errors.

    The stop lookup uses SQLite read-only mode. The existing independently
    attested reader validates source digest/session/role/timestamp and handles
    wildcard + action-scoped boundaries, including uncertain revocations.
    """
    if not state_path.is_file():
        raise FileNotFoundError('Existing state database required for offer gate.')
    with closing(sqlite3.connect(state_path.resolve().as_uri() + '?mode=ro',
                                 uri=True, timeout=5)) as db:
        existing = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        missing = set(_REQUIRED_TABLES) - existing
        if missing:
            raise ValueError('Interaction policy schema missing: ' + ', '.join(sorted(missing)))
        row = db.execute(
            'SELECT stopped FROM interaction_session_controls WHERE session_id=?',
            (session_id,),
        ).fetchone()
        if row is not None and row[0] not in (0, 1):
            raise ValueError('Invalid interaction stop state.')
        if row is not None and row[0] == 1:
            return 'blocked-stop'
    context = read_interaction_context(
        state_path, subject='sofia', semantic_id='hug', region_id='*',
    )
    if context.blocked:
        return ('blocked-unverified-boundary'
                if context.status == 'unverified_boundary' else 'blocked-boundary')
    return None


def run_guarded_offer(*, provider: TextProvider, base: CognitiveRequest,
                      frame: ReviewedFrame, state_path: str | Path,
                      session_id: str) -> GuardedOfferResult:
    """Route one exact saved-host-reviewed offer, never a general text parser.

    The request retains host-supplied conversation history. Only the checked
    choice reaches expression, never its model-written diagnostic reason.
    Explicitly contradictory expression is vetoed rather than rewritten or
    persisted. This heuristic veto is not a complete semantic verifier.
    """
    if (not isinstance(session_id, str)
            or _SESSION_ID.fullmatch(session_id) is None):
        raise ValueError('A canonical session ID is required.')
    if not isinstance(frame, ReviewedFrame) or frame.user_text != OFFER:
        raise ValueError('Only the reviewed synthetic hug offer is supported.')
    intent = parse_user_action(frame.user_text, message_id='offer-gate-check')
    if intent is None or intent.modality != 'offered' or intent.action_id != 'hug':
        raise ValueError('Trusted hug-offer grammar classification required.')
    if frame != from_reviewed_action(user_text=frame.user_text, intent=intent):
        raise ValueError('Reviewed frame is inconsistent with trusted grammar.')
    decision_request = routed_conversation_choice_request(base, frame)
    path = Path(state_path)

    blocked = _policy_gate(state_path=path, session_id=session_id)
    if blocked is not None:
        return GuardedOfferResult(status=blocked)

    decided = provider.respond(decision_request)
    if decided.tool_calls:
        raise ValueError('Choice stage returned an unexpected tool call.')
    choice = parse_choice(decided.content, frame)

    blocked = _policy_gate(state_path=path, session_id=session_id)
    if blocked is not None:
        return GuardedOfferResult(status=blocked)

    expressed = provider.respond(routed_conversation_expression_request(base, frame, choice))
    if expressed.tool_calls or not isinstance(expressed.content, str) or not expressed.content.strip():
        raise ValueError('Expression produced no tool-free response.')

    # First honor a verified boundary or stop that arrived during inference.
    # Neither a malformed draft nor its diagnostic text may obscure that policy.
    blocked = _policy_gate(state_path=path, session_id=session_id)
    if blocked is not None:
        return GuardedOfferResult(status=blocked)
    # No active block: fail closed on an explicit choice/expression reversal.
    # This does NOT certify every nuanced reply, nor confer consent.
    validate_offer_expression(choice, expressed.content)
    return GuardedOfferResult(
        status='responded', choice=choice, response=expressed.content,
        decision_findings=audit_decision_reason(choice, frame).findings,
        expression_findings=audit_expression(expressed.content, frame).findings,
    )
