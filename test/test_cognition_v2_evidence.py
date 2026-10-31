"""Subject, scope, freshness, correction, and acquisition evidence gates."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.capability.model import CapabilityResult, CapabilityResultKind
from sofia.core.cognition.v2 import (
    AcquisitionState,
    CapabilityEvidencePayload,
    CognitiveEvidenceLedger,
    EpistemicState,
    EvidenceAcquisitionCoordinator,
    EvidenceAtom,
    EvidenceConflict,
    EvidenceGraph,
    EvidenceNeed,
)
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


PROJECT_ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
SCOPE = "private:sparks"


def _need(subject="fleet-node:artemis", predicate="machine.cpu.model", **kwargs):
    return EvidenceNeed(
        need_id=f"need:{subject.rsplit(':', 1)[-1]}:cpu",
        subject_id=subject,
        predicate=predicate,
        scope_id=kwargs.pop("scope_id", SCOPE),
        max_age_seconds=kwargs.pop("max_age_seconds", 300.0),
        minimum_trust=kwargs.pop("minimum_trust", 0.8),
        **kwargs,
    )


def _atom(
    evidence_id,
    *,
    subject="fleet-node:artemis",
    predicate="machine.cpu.model",
    value="Ryzen",
    source="capability:remote.hardware.inspect",
    scope=SCOPE,
    observed_at=NOW,
    expires_at=None,
    trust=0.95,
    epistemic=EpistemicState.OBSERVED,
    acquisition=AcquisitionState.CURRENT,
):
    return EvidenceAtom(
        evidence_id=evidence_id,
        subject_id=subject,
        predicate=predicate,
        value_json=json.dumps(value),
        source_id=source,
        observed_at=observed_at,
        expires_at=expires_at,
        scope_id=scope,
        trust=trust,
        epistemic_state=epistemic,
        acquisition_state=acquisition,
    )


def test_venus_evidence_never_satisfies_artemis_need(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    ledger.append(_atom("evidence:venus-cpu", subject="fleet-node:venus"))

    resolution = EvidenceGraph(ledger).resolve(_need(), now=NOW)

    assert resolution.acquisition_state is AcquisitionState.NOT_SAMPLED
    assert resolution.atoms == ()


def test_evidence_is_scope_isolated_and_restart_durable(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    first = CognitiveEvidenceLedger(path)
    atom = _atom("evidence:artemis-private")
    first.append(atom)
    assert first.append(atom) == atom

    restarted = CognitiveEvidenceLedger(path)
    visible = EvidenceGraph(restarted).resolve(_need(), now=NOW)
    other = EvidenceGraph(restarted).resolve(
        _need(scope_id="private:someone-else"),
        now=NOW,
    )

    assert visible.atoms == (atom,)
    assert other.acquisition_state is AcquisitionState.NOT_SAMPLED


def test_conflicting_fresh_scoped_evidence_fails_closed(tmp_path):
    """Two independently current incompatible facts are not one known fact."""
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    ledger.append(_atom(
        "evidence:cpu-source-one", value="Ryzen",
        source="capability:local.cpu.inspect",
    ))
    ledger.append(_atom(
        "evidence:cpu-source-two", value="Xeon",
        source="capability:remote.cpu.inspect",
    ))

    decision = EvidenceGraph(ledger).resolve(_need(), now=NOW)

    assert decision.acquisition_state is AcquisitionState.CONTRADICTED
    assert decision.atoms == ()
    assert "conflicting" in decision.reason
    # Restart cannot turn a contradiction into a positive cached fact.
    assert EvidenceGraph(
        CognitiveEvidenceLedger(ledger.path)
    ).resolve(_need(), now=NOW).acquisition_state is AcquisitionState.CONTRADICTED


def test_equal_values_from_independent_sources_are_not_conflicted(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    first = ledger.append(_atom(
        "evidence:same-a", value={"model": "Ryzen", "cores": 8},
        source="capability:local.cpu.inspect",
    ))
    second = ledger.append(_atom(
        "evidence:same-b", value={"cores": 8, "model": "Ryzen"},
        source="capability:remote.cpu.inspect",
    ))
    decision = EvidenceGraph(ledger).resolve(_need(), now=NOW)
    assert decision.acquisition_state is AcquisitionState.CURRENT
    assert set(decision.atoms) == {first, second}


def test_stale_or_low_trust_conflict_cannot_override_current_fact(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    current = ledger.append(_atom("evidence:trusted-current", value="Ryzen"))
    ledger.append(_atom(
        "evidence:stale-other", value="Xeon",
        observed_at=NOW - timedelta(hours=2),
    ))
    ledger.append(_atom(
        "evidence:untrusted-other", value="EPYC", trust=0.1,
    ))
    decision = EvidenceGraph(ledger).resolve(_need(), now=NOW)
    assert decision.acquisition_state is AcquisitionState.CURRENT
    assert decision.atoms == (current,)


def test_evidence_id_cannot_be_reused_for_different_fact(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    ledger.append(_atom("evidence:stable-id"))

    with pytest.raises(EvidenceConflict):
        ledger.append(_atom("evidence:stable-id", value="Xeon"))


def test_evidence_id_cannot_be_reused_with_different_dependencies(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    first = _atom("evidence:first")
    second = _atom("evidence:second")
    derived = _atom(
        "evidence:derived-stable",
        source="inference:stable",
        epistemic=EpistemicState.INFERRED,
    )
    ledger.append(first)
    ledger.append(second)
    ledger.append(derived, depends_on=(first.evidence_id,))

    with pytest.raises(EvidenceConflict):
        ledger.append(derived, depends_on=(second.evidence_id,))


def test_stale_and_insufficient_trust_do_not_satisfy_need(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    ledger.append(_atom(
        "evidence:expired",
        observed_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=5),
    ))
    graph = EvidenceGraph(ledger)
    assert graph.resolve(_need(), now=NOW).acquisition_state is AcquisitionState.STALE

    weak_ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "weak.db"))
    weak_ledger.append(_atom("evidence:weak", trust=0.2))
    strict = _need(minimum_trust=0.9, max_age_seconds=30.0)
    assert (
        EvidenceGraph(weak_ledger).resolve(strict, now=NOW).acquisition_state
        is AcquisitionState.NOT_SAMPLED
    )


def test_future_dated_evidence_is_not_current(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    ledger.append(_atom(
        "evidence:from-the-future",
        observed_at=NOW + timedelta(hours=1),
    ))

    resolution = EvidenceGraph(ledger).resolve(_need(), now=NOW)

    assert resolution.acquisition_state is AcquisitionState.NOT_SAMPLED
    assert resolution.atoms == ()


def test_hypothesis_does_not_become_operational_fact(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    source = _atom("evidence:source")
    ledger.append(source)
    ledger.append(
        _atom(
            "evidence:hypothesis",
            value="Probably Ryzen",
            source="model-suggestion:primary",
            epistemic=EpistemicState.HYPOTHESIS,
        ),
        depends_on=(source.evidence_id,),
    )
    graph = EvidenceGraph(ledger)

    resolution = graph.resolve(_need(), now=NOW)

    assert tuple(atom.evidence_id for atom in resolution.atoms) == (
        "evidence:source",
    )


@pytest.mark.parametrize(
    "state",
    (AcquisitionState.UNAVAILABLE, AcquisitionState.FAILED),
)
def test_acquisition_failure_states_remain_separate_from_epistemic_unknown(
    tmp_path,
    state,
):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / f"{state.value}.db"))
    ledger.append(_atom(
        f"evidence:{state.value}",
        value=None,
        source="runtime:acquisition",
        epistemic=EpistemicState.UNKNOWN,
        acquisition=state,
    ))

    resolution = EvidenceGraph(ledger).resolve(_need(), now=NOW)

    assert resolution.acquisition_state is state
    assert resolution.atoms == ()


def test_evidence_value_must_be_valid_finite_json():
    with pytest.raises(ValueError, match="finite JSON"):
        EvidenceAtom(
            evidence_id="evidence:invalid-json",
            subject_id="fleet-node:artemis",
            predicate="machine.cpu.load",
            value_json="NaN",
            source_id="capability:remote.hardware.inspect",
            observed_at=NOW,
            scope_id=SCOPE,
            trust=0.9,
            epistemic_state=EpistemicState.OBSERVED,
            acquisition_state=AcquisitionState.CURRENT,
        )


def test_user_correction_invalidates_claim_and_dependent_conclusion(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    original = _atom("evidence:original")
    derived = _atom(
        "evidence:derived",
        predicate="machine.cpu.family",
        value="Zen",
        source="inference:cpu-family",
        epistemic=EpistemicState.INFERRED,
    )
    ledger.append(original)
    ledger.append(derived, depends_on=(original.evidence_id,))
    graph = EvidenceGraph(ledger)

    invalidated = graph.correct(
        correction_id="correction:user-1",
        need=_need(),
        target_ids=(original.evidence_id,),
        source_ref="user-report:message-1",
        reason="Sparks corrected the attributed CPU",
        corrected_at=NOW + timedelta(seconds=1),
    )

    assert invalidated == ("evidence:original", "evidence:derived")
    assert ledger.get("evidence:original").acquisition_state is AcquisitionState.CONTRADICTED
    assert ledger.get("evidence:derived").acquisition_state is AcquisitionState.REVOKED
    assert graph.resolve(_need(), now=NOW + timedelta(seconds=2)).atoms == ()


def test_g7a_derived_claim_expires_when_verified_premise_expires(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    ledger = CognitiveEvidenceLedger(path)
    original = _atom(
        "evidence:expiring-preset",
        expires_at=NOW + timedelta(seconds=10),
    )
    derived = _atom(
        "evidence:family-from-preset",
        predicate="machine.cpu.family",
        value="Zen",
        source="inference:family",
        epistemic=EpistemicState.INFERRED,
    )
    ledger.append(original)
    ledger.append(derived, depends_on=(original.evidence_id,))
    derived_need = _need(predicate="machine.cpu.family")
    graph = EvidenceGraph(ledger)
    assert graph.resolve(derived_need, now=NOW).atoms == (derived,)

    stale = graph.resolve(derived_need, now=NOW + timedelta(seconds=11))
    assert stale.acquisition_state is AcquisitionState.STALE
    assert stale.atoms == ()
    assert ledger.get(derived.evidence_id).acquisition_state is AcquisitionState.CURRENT

    restarted = EvidenceGraph(CognitiveEvidenceLedger(path))
    assert restarted.resolve(
        derived_need, now=NOW + timedelta(seconds=11)
    ).acquisition_state is AcquisitionState.STALE


def test_g7a_direct_revocation_blocks_existing_and_new_inferences(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    source = _atom("evidence:revoked-source")
    derived = _atom(
        "evidence:prior-inference", predicate="machine.cpu.family",
        value="Zen", source="inference:family",
        epistemic=EpistemicState.INFERRED,
    )
    ledger.append(source)
    ledger.append(derived, depends_on=(source.evidence_id,))
    derived_need = _need(predicate="machine.cpu.family")
    assert EvidenceGraph(ledger).resolve(derived_need, now=NOW).atoms == (derived,)

    ledger.record_status(
        source.evidence_id, AcquisitionState.REVOKED,
        reason="authenticated device consent revoked",
        source_ref="runtime:device-revocation",
        changed_at=NOW + timedelta(seconds=1),
    )
    resolution = EvidenceGraph(ledger).resolve(
        derived_need, now=NOW + timedelta(seconds=2)
    )
    assert resolution.acquisition_state is AcquisitionState.REVOKED
    assert resolution.atoms == ()
    with pytest.raises(ValueError, match="revoked or unavailable dependencies"):
        ledger.append(
            _atom(
                "evidence:new-inference", predicate="machine.cpu.family",
                value="Zen", source="inference:family",
                epistemic=EpistemicState.INFERRED,
            ),
            depends_on=(source.evidence_id,),
        )


def test_g7a_inference_cannot_upgrade_low_trust_premise(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    ledger = CognitiveEvidenceLedger(path)
    weak = _atom("evidence:weak-premise", trust=0.2)
    inferred = _atom(
        "evidence:unjustified-confidence",
        predicate="machine.cpu.family",
        value="Zen", source="inference:cpu-family",
        epistemic=EpistemicState.INFERRED,
        trust=0.99,
    )
    ledger.append(weak)
    ledger.append(inferred, depends_on=(weak.evidence_id,))
    need = _need(predicate="machine.cpu.family", minimum_trust=0.8)

    assert EvidenceGraph(ledger).resolve(
        need, now=NOW
    ).acquisition_state is AcquisitionState.NOT_SAMPLED
    assert EvidenceGraph(ledger).resolve(need, now=NOW).atoms == ()

    # A less demanding consumer can inspect the same unchanged provenance.
    low_threshold = _need(predicate="machine.cpu.family", minimum_trust=0.1)
    assert EvidenceGraph(ledger).resolve(low_threshold, now=NOW).atoms == (inferred,)
    restarted = EvidenceGraph(CognitiveEvidenceLedger(path))
    assert restarted.resolve(need, now=NOW).atoms == ()


def test_g7a_transitive_revocation_invalidates_multi_step_inference(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    observation = _atom("evidence:base")
    middle = _atom(
        "evidence:intermediate", predicate="machine.cpu.family",
        value="Zen", source="inference:family",
        epistemic=EpistemicState.INFERRED,
    )
    conclusion = _atom(
        "evidence:conclusion", predicate="machine.cpu.platform",
        value="AM5", source="inference:platform",
        epistemic=EpistemicState.INFERRED,
    )
    ledger.append(observation)
    ledger.append(middle, depends_on=(observation.evidence_id,))
    ledger.append(conclusion, depends_on=(middle.evidence_id,))
    need = _need(predicate="machine.cpu.platform")
    graph = EvidenceGraph(ledger)
    assert graph.resolve(need, now=NOW).atoms == (conclusion,)

    ledger.record_status(
        observation.evidence_id, AcquisitionState.REVOKED,
        reason="source revocation", source_ref="runtime:revocation",
        changed_at=NOW + timedelta(seconds=1),
    )
    result = graph.resolve(need, now=NOW + timedelta(seconds=2))
    assert result.atoms == ()
    assert result.acquisition_state is AcquisitionState.REVOKED


def test_g7a_new_inference_cannot_use_expired_or_future_evidence(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    expires = _atom(
        "evidence:expired-premise",
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW - timedelta(seconds=1),
    )
    future = _atom(
        "evidence:future-premise",
        observed_at=NOW + timedelta(minutes=1),
    )
    ledger.append(expires)
    ledger.append(future)
    inferred = _atom(
        "evidence:proposed-derived", predicate="machine.cpu.family",
        value="Zen", source="inference:family",
        epistemic=EpistemicState.INFERRED,
    )
    with pytest.raises(ValueError, match="future or expired dependencies"):
        ledger.append(inferred, depends_on=(expires.evidence_id,))
    with pytest.raises(ValueError, match="future or expired dependencies"):
        ledger.append(inferred, depends_on=(future.evidence_id,))
    assert ledger.get(inferred.evidence_id) is None


def test_derived_evidence_dependencies_cannot_cross_private_scopes(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    private = _atom("evidence:private-source")
    ledger.append(private)
    derived = _atom(
        "evidence:cross-scope-derived",
        predicate="machine.cpu.family",
        source="inference:cpu-family",
        scope="private:someone-else",
        epistemic=EpistemicState.INFERRED,
    )

    with pytest.raises(ValueError, match="cross scopes"):
        ledger.append(derived, depends_on=(private.evidence_id,))


def test_correction_rejects_wrong_subject_without_partial_invalidation(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    venus = _atom("evidence:venus", subject="fleet-node:venus")
    ledger.append(venus)

    with pytest.raises(ValueError, match="exact claim key"):
        EvidenceGraph(ledger).correct(
            correction_id="correction:wrong-subject",
            need=_need(),
            target_ids=(venus.evidence_id,),
            source_ref="user-report:message-2",
            reason="wrong target",
            corrected_at=NOW,
        )

    assert ledger.get(venus.evidence_id).acquisition_state is AcquisitionState.CURRENT


def test_correction_rejects_assistant_source(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    original = _atom("evidence:original")
    ledger.append(original)

    with pytest.raises(ValueError, match="authenticated user-report"):
        EvidenceGraph(ledger).correct(
            correction_id="correction:assistant",
            need=_need(),
            target_ids=(original.evidence_id,),
            source_ref="conversation:assistant-message",
            reason="model tried to correct itself",
            corrected_at=NOW,
        )

    assert ledger.get(original.evidence_id).acquisition_state is AcquisitionState.CURRENT


def test_assistant_prose_and_fake_execution_source_cannot_be_evidence(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    with pytest.raises(ValueError, match="reviewed host source"):
        ledger.append(_atom(
            "evidence:assistant-prose",
            source="conversation:assistant-message",
        ))
    with pytest.raises(ValueError, match="successful result receipt"):
        ledger.append(_atom(
            "evidence:fake-execution",
            predicate="execution.service.restart",
            source="runtime:assistant-claim",
        ))
    with pytest.raises(ValueError, match="matching successful"):
        ledger.append(_atom(
            "evidence:prefix-only-execution",
            predicate="execution.service.restart",
            source="execution-receipt:local.service.restart",
        ))


def test_execution_fact_requires_matching_successful_capability_result(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    acquisition = EvidenceAcquisitionCoordinator(ledger)
    need = _need(predicate="execution.service.restart")
    result = CapabilityResult(
        "local.service.restart",
        CapabilityResultKind.SUCCESS,
        evidence={"outcome": "restarted"},
    )
    payload = CapabilityEvidencePayload(
        evidence_id="evidence:restart-receipt",
        subject_id=need.subject_id,
        predicate=need.predicate,
        value={"outcome": "restarted"},
        source_id="execution-receipt:local.service.restart",
        observed_at=NOW,
        expires_at=None,
        scope_id=need.scope_id,
        trust=1.0,
    )

    atom = acquisition.record_execution(need, result, payload)

    assert atom.source_id == "execution-receipt:local.service.restart"
    assert EvidenceGraph(ledger).resolve(need, now=NOW).atoms == (atom,)


def test_capability_acquisition_requires_success_and_exact_requested_key(tmp_path):
    ledger = CognitiveEvidenceLedger(bootstrap_canonical_sqlite(tmp_path / "sofia.db"))
    acquisition = EvidenceAcquisitionCoordinator(ledger)
    need = _need()
    success = CapabilityResult(
        "remote.hardware.inspect",
        CapabilityResultKind.SUCCESS,
        evidence={"cpu": "Ryzen"},
    )
    payload = CapabilityEvidencePayload(
        evidence_id="evidence:capability-result",
        subject_id=need.subject_id,
        predicate=need.predicate,
        value="Ryzen",
        source_id="capability:remote.hardware.inspect",
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=2),
        scope_id=need.scope_id,
        trust=0.95,
    )

    atom = acquisition.record(need, success, payload)
    assert atom.subject_id == "fleet-node:artemis"

    with pytest.raises(ValueError, match="requested key"):
        acquisition.record(
            _need(subject="fleet-node:venus"),
            success,
            payload,
        )
    failed_payload = CapabilityEvidencePayload(
        evidence_id="evidence:capability-failed",
        subject_id=need.subject_id,
        predicate=need.predicate,
        value="ignored",
        source_id="capability:remote.hardware.inspect",
        observed_at=NOW,
        expires_at=None,
        scope_id=need.scope_id,
        trust=0.95,
    )
    failed = acquisition.record(
        need,
        CapabilityResult(
            "remote.hardware.inspect",
            CapabilityResultKind.FAILED,
        ),
        failed_payload,
    )
    assert failed.value_json == "null"
    assert failed.epistemic_state is EpistemicState.UNKNOWN
    assert failed.acquisition_state is AcquisitionState.FAILED

    with pytest.raises(ValueError, match="authority denial"):
        acquisition.record(
            need,
            CapabilityResult(
                "remote.hardware.inspect",
                CapabilityResultKind.DENIED,
            ),
            CapabilityEvidencePayload(
                evidence_id="evidence:capability-denied",
                subject_id=need.subject_id,
                predicate=need.predicate,
                value=None,
                source_id="capability:remote.hardware.inspect",
                observed_at=NOW,
                expires_at=None,
                scope_id=need.scope_id,
                trust=0.0,
            ),
        )


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
        '{"name":"Sofía","traits":["direct"],'
        '"communication_style":"Clear and direct."}',
        encoding="utf-8",
    )
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return SofiaConfiguration(
        constitution_path=PROJECT_ROOT / "src/sofia/core/constitution/constitution.md",
        constitution_hash_path=(
            PROJECT_ROOT / "src/sofia/core/constitution/constitution.sha256"
        ),
        identity_path=PROJECT_ROOT / "src/sofia/core/identity/identity.json",
        personality_path=personality_path,
        avatar_path=PROJECT_ROOT / "src/sofia/core/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def test_application_composes_one_canonical_evidence_ledger(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    assert app.cognitive_evidence.path == Path(app._configuration.state_path)
    assert app.cognitive_evidence_graph.ledger is app.cognitive_evidence
    assert app.cognitive_evidence_acquisition.ledger is app.cognitive_evidence
