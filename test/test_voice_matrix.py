from sofia.cognition.matrix import EvidenceRecord
from datetime import datetime,timezone
from sofia.authority.model import Authority
from sofia.cognition.matrix import AuthorityDecision,EvidenceKind,EvidenceState,MatrixAuthorityPlanner,MatrixCoordinator,MatrixDomain,MatrixEvidencePlanner,MatrixEvidenceResolver,MatrixIntent,MatrixRelevance,MatrixResponsePlanner,MatrixResponseValidator,ResponseValidationDisposition,TurnEnvelope
from sofia.cognition.matrix.defaults import default_matrix_registry
from sofia.cognition.model import CognitiveResponse
NOW=datetime(2026,10,2,18,0,tzinfo=timezone.utc)
def env(c): return TurnEnvelope(message_id="voice-matrix",session_id="voice-session",content=c,created_at=NOW,principal_id="sparks",channel="desktop")
def test_voice_runtime_question_activates_voice_domain():
    t=MatrixCoordinator(registry=default_matrix_registry()).evaluate(env("is your voice working?"));assert t.relevance_for(MatrixDomain.VOICE) is MatrixRelevance.REQUIRED
def test_voice_control_is_action_owned_by_voice_not_generic_ops():
    e=env("turn voice off");t=MatrixCoordinator(registry=default_matrix_registry()).evaluate(e);assert t.intent is MatrixIntent.ACTION_REQUEST;assert t.relevance_for(MatrixDomain.AUTHORITY) is MatrixRelevance.REQUIRED;assert t.relevance_for(MatrixDomain.VOICE) is MatrixRelevance.REQUIRED;assert t.relevance_for(MatrixDomain.OPS) is MatrixRelevance.NONE
def test_voice_query_requires_current_runtime_evidence():
    e=env("is your microphone and voice working?");t=MatrixCoordinator(registry=default_matrix_registry()).evaluate(e);m=MatrixEvidencePlanner().plan(t,e);r=next(x for x in m.requirements if x.key=="voice.runtime.current");assert r.kind is EvidenceKind.CURRENT and r.required
def test_missing_voice_runtime_evidence_blocks_working_claim():
    e=env("is your voice working?");t=MatrixCoordinator(registry=default_matrix_registry()).evaluate(e);ev=MatrixEvidenceResolver().resolve(MatrixEvidencePlanner().plan(t,e),{"voice.runtime.current":EvidenceState.MISSING});a=MatrixAuthorityPlanner().plan(e,t,Authority());c=MatrixResponsePlanner().plan(t,ev,a);v=MatrixResponseValidator().validate(CognitiveResponse(content="My voice is working and ready."),c,ev);assert a.decision is AuthorityDecision.NOT_REQUIRED;assert v.disposition is ResponseValidationDisposition.RETRY;assert "voice_runtime_claim_without_evidence" in v.reasons


def test_current_disabled_tts_evidence_blocks_working_claim():
    e=env("is your voice working?")
    t=MatrixCoordinator(registry=default_matrix_registry()).evaluate(e)
    ev=MatrixEvidenceResolver().resolve(
        MatrixEvidencePlanner().plan(t,e),
        {
            "voice.runtime.current": EvidenceRecord(
                "voice.runtime.current",
                EvidenceState.AVAILABLE,
                "voice:tts:windows-sapi:disabled",
            )
        },
    )
    a=MatrixAuthorityPlanner().plan(e,t,Authority())
    c=MatrixResponsePlanner().plan(t,ev,a)
    v=MatrixResponseValidator().validate(
        CognitiveResponse(content="My voice is working and ready."),
        c,
        ev,
    )
    assert v.disposition is ResponseValidationDisposition.RETRY
    assert "voice_runtime_claim_contradicts_evidence" in v.reasons
