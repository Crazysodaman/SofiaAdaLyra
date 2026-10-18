from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.goals.evidence import GoalEvidenceLedger
from sofia.learning.contracts import (
    DataUse, DataUseGrant, OutcomeClass, Prediction, PredictionDisposition,
    PredictionMode, SourceClass,
)
from sofia.learning.registry import CandidateArtifact, CandidateRegistry
from sofia.learning.service import GroundedSample, LearningService
from sofia.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


class _ExactApprovalVerifier:
    def __init__(self):
        self.consumed: set[str] = set()

    def consume(self, *, approval_id, capability, parameters, now, _transaction_db):
        assert capability.startswith("learning.")
        assert isinstance(parameters, dict) and parameters
        assert now.tzinfo is not None
        assert _transaction_db.in_transaction
        if approval_id in self.consumed:
            raise PermissionError("approval replay")
        self.consumed.add(approval_id)


def _service(state: Path) -> LearningService:
    return LearningService(state, approval_verifier=_ExactApprovalVerifier())


def _application_configuration(tmp_path: Path) -> SofiaConfiguration:
    project = Path(__file__).resolve().parents[1]
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["witty","warm","skeptical"],'
        '"communication_style":"Direct and evidence-minded."}',
        encoding="utf-8",
    )
    from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return SofiaConfiguration(
        constitution_path=project / "src/sofia/constitution/constitution.md",
        constitution_hash_path=project / "src/sofia/constitution/constitution.sha256",
        identity_path=project / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=project / "src/sofia/embodiment/avatar.json",
        state_path=state,
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=project,
    )


def _grant(*, audience: str = "local:text", expires: datetime | None = None) -> DataUseGrant:
    return DataUseGrant(
        grant_id="data-use:owner:forecast", principal_id="sparks",
        audience_id=audience, purpose="host-pressure-forecast",
        uses=frozenset({
            DataUse.OBSERVATION, DataUse.STORAGE, DataUse.FEATURE_EXTRACTION,
            DataUse.STATISTICAL_TRAINING, DataUse.DEPLOYMENT,
        }),
        issued_at=NOW - timedelta(hours=1),
        expires_at=expires or NOW + timedelta(days=30),
        approval_ref="owner-ui:data-use-forecast-v1",
    )


def _record_pair(
    state: Path, *, index: int, group: str, audience: str = "local:text",
    outcome: OutcomeClass = OutcomeClass.POSITIVE,
) -> GroundedSample:
    source_at = NOW + timedelta(minutes=index * 10)
    prediction_at = source_at + timedelta(minutes=1)
    outcome_at = prediction_at + timedelta(minutes=5)
    ledger = GoalEvidenceLedger(state)
    source = ledger.record(
        evidence_ref=f"telemetry:{audience}:{index}", kind="external_observation",
        observed_at=source_at, source="fleet:telemetry", successful=None,
        principal_id="sparks", audience=audience,
        payload={"subject_id": f"host:{group}"},
    )
    outcome_record = ledger.record(
        evidence_ref=f"outcome:{audience}:{index}", kind="operation_receipt",
        observed_at=outcome_at, source="fleet:delayed-outcome",
        successful=(None if outcome is OutcomeClass.UNKNOWN else outcome is OutcomeClass.POSITIVE),
        principal_id="sparks", audience=audience,
        payload={"source_ref": source.evidence_ref},
    )
    return GroundedSample(
        sample_id=f"sample:{audience}:{index}", source_class=SourceClass.FLEET_TELEMETRY,
        source_ref=source.evidence_ref, outcome_ref=outcome_record.evidence_ref,
        principal_id="sparks", audience_id=audience, subject_id=f"host:{group}",
        group_id=group, prediction_at=prediction_at, outcome=outcome,
        features={"cpu": index / 10, "ram": index * 2, "gpu": None},
        retention_until=NOW + timedelta(days=60), purpose="host-pressure-forecast",
    )


def test_canonical_application_owns_learning_and_reuses_background_scheduler(
    tmp_path: Path, monkeypatch,
):
    monkeypatch.delenv("SOFIA_ML_TRUSTED_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("SOFIA_ML_TRUSTED_KEY_ID", raising=False)
    application = SofiaApplication(_application_configuration(tmp_path))
    try:
        assert isinstance(application.learning, LearningService)
        assert application.learning_candidates is None
        application.start()
        assert "learning_retention" in application.background_coordinator._tasks
        assert "fleet_pressure_shadow" in application.background_coordinator._tasks
        assert application.learning.mode() is PredictionMode.SHADOW
        assert application._runtime.ops_service.placement_advisor_configured is True
    finally:
        application.shutdown()


def test_data_use_grant_cannot_be_created_from_a_shaped_string_alone(
    canonical_state_path: Path,
):
    with pytest.raises(PermissionError, match="SAFE data-use approval"):
        LearningService(canonical_state_path).record_grant(_grant())


def test_grounded_point_in_time_manifest_and_independent_holdout(canonical_state_path: Path):
    service = _service(canonical_state_path)
    grant = _grant()
    service.record_grant(grant)
    for index, group, outcome in (
        (0, "venus", OutcomeClass.NEGATIVE),
        (1, "artemis", OutcomeClass.POSITIVE),
        (2, "gaia", OutcomeClass.UNKNOWN),
        (3, "hephaestus", OutcomeClass.POSITIVE),
    ):
        service.admit_sample(
            _record_pair(canonical_state_path, index=index, group=group, outcome=outcome),
            grant,
        )
    manifest = service.create_manifest(
        principal_id="sparks", audience_id="local:text",
        purpose="host-pressure-forecast", at=NOW + timedelta(hours=2), seed=71,
    )
    assert set(manifest.train_ids).isdisjoint(manifest.validation_ids)
    assert set(manifest.train_ids).isdisjoint(manifest.holdout_ids)
    assert set(manifest.validation_ids).isdisjoint(manifest.holdout_ids)
    assert manifest.schema_version == "ml-feature-v1"

    result = service.evaluate(
        manifest.manifest_id,
        baseline_digest="1" * 64, candidate_digest="2" * 64,
        baseline=lambda features: OutcomeClass.NEGATIVE,
        candidate=lambda features: OutcomeClass.POSITIVE,
        at=NOW + timedelta(hours=3),
    )
    assert result.scored + result.unknown == len(manifest.holdout_ids)
    assert result.holdout_digest


def test_cross_audience_forgery_future_leakage_and_raw_chat_fail_closed(canonical_state_path: Path):
    service = _service(canonical_state_path)
    grant = _grant()
    service.record_grant(grant)
    wrong_scope = _record_pair(canonical_state_path, index=0, group="venus", audience="discord:dm")
    with pytest.raises(PermissionError, match="principal/audience"):
        service.admit_sample(wrong_scope, grant)

    with pytest.raises(PermissionError, match="ambient chat"):
        GroundedSample(
            sample_id="sample:chat", source_class=SourceClass.RAW_CONVERSATION,
            source_ref="message:1", outcome_ref="outcome:1", principal_id="sparks",
            audience_id="local:text", subject_id="host:venus", group_id="venus",
            prediction_at=NOW, outcome=OutcomeClass.POSITIVE, features={"x": 1},
            retention_until=NOW + timedelta(days=1), purpose="host-pressure-forecast",
        )

    sample = _record_pair(canonical_state_path, index=1, group="artemis")
    # A forged cutoff earlier than the original observation is rejected even
    # though both evidence IDs are real and scope-correct.
    leaked = GroundedSample(
        **{field: getattr(sample, field) for field in sample.__dataclass_fields__
           if field != "prediction_at"},
        prediction_at=NOW - timedelta(days=1),
    )
    with pytest.raises(PermissionError, match="future source"):
        service.admit_sample(leaked, grant)

    stale = GroundedSample(
        **{field: getattr(sample, field) for field in sample.__dataclass_fields__
           if field not in {"sample_id", "prediction_at", "max_source_age_seconds"}},
        sample_id="sample:stale-sensor",
        prediction_at=sample.prediction_at + timedelta(hours=2),
        max_source_age_seconds=60,
    )
    with pytest.raises(PermissionError, match="stale source"):
        service.admit_sample(stale, grant)

    forged = GroundedSample(
        **{field: getattr(sample, field) for field in sample.__dataclass_fields__
           if field not in {"sample_id", "outcome"}},
        sample_id="sample:forged-positive", outcome=OutcomeClass.NEGATIVE,
    )
    with pytest.raises(PermissionError, match="conflicts"):
        service.admit_sample(forged, grant)

    wrong_class = GroundedSample(
        **{field: getattr(sample, field) for field in sample.__dataclass_fields__
           if field not in {"sample_id", "source_class"}},
        sample_id="sample:poisoned-class", source_class=SourceClass.OPERATION_RECEIPT,
    )
    with pytest.raises(PermissionError, match="source class"):
        service.admit_sample(wrong_class, grant)


def test_permission_withdrawal_and_sample_replay_fail_closed(canonical_state_path: Path):
    service = _service(canonical_state_path)
    grant = _grant()
    service.record_grant(grant)
    sample = _record_pair(canonical_state_path, index=0, group="venus")
    service.admit_sample(sample, grant)
    changed = GroundedSample(
        **{field: getattr(sample, field) for field in sample.__dataclass_fields__
           if field != "features"},
        features={"cpu": 999},
    )
    with pytest.raises(PermissionError, match="replay changed"):
        service.admit_sample(changed, grant)
    service.revoke_grant(
        grant.grant_id, at=NOW + timedelta(minutes=2),
        approval_ref="owner-ui:withdraw-data-use",
    )
    another = _record_pair(canonical_state_path, index=1, group="artemis")
    with pytest.raises(PermissionError, match="missing, changed, or revoked"):
        service.admit_sample(another, grant)


def test_revocation_invalidates_derivative_manifest_across_restart(canonical_state_path: Path):
    grant = _grant()
    service = _service(canonical_state_path)
    service.record_grant(grant)
    samples = []
    for index, group in enumerate(("venus", "artemis", "gaia")):
        sample = _record_pair(canonical_state_path, index=index, group=group)
        samples.append(sample)
        service.admit_sample(sample, grant)
    manifest = service.create_manifest(
        principal_id="sparks", audience_id="local:text",
        purpose="host-pressure-forecast", at=NOW + timedelta(hours=1), seed=9,
    )
    service.revoke_source(
        samples[0].source_ref, at=NOW + timedelta(hours=2),
        approval_ref="owner-ui:withdraw-source-0",
    )
    restarted = _service(canonical_state_path)
    with pytest.raises(PermissionError, match="revoked, expired, or removed"):
        restarted.get_manifest(manifest.manifest_id, at=NOW + timedelta(hours=3))
    removed = restarted.enforce_retention(at=NOW + timedelta(hours=3))
    assert removed == {"samples_deleted": 1, "manifests_deleted": 1}


def test_prediction_modes_are_scoped_non_authoritative_and_replay_safe(canonical_state_path: Path):
    service = _service(canonical_state_path)
    assert service.mode() is PredictionMode.SHADOW
    prediction = Prediction(
        prediction_id="prediction:1", candidate_digest="a" * 64,
        subject_id="host:venus", principal_id="sparks", audience_id="local:text",
        generated_at=NOW, expires_at=NOW + timedelta(minutes=5),
        mode=PredictionMode.SHADOW, value={"pressure": 0.73}, uncertainty=0.2,
        reason_refs=("telemetry:0",),
    )
    service.record_prediction(prediction)
    assert not prediction.grants_authority
    assert not prediction.grants_consent
    assert not prediction.is_factual_evidence
    assert prediction.visible_to(PrincipalContext("sparks", "local:text", AudienceKind.PRIVATE))
    assert not prediction.visible_to(PrincipalContext("sparks", "discord:dm", AudienceKind.PRIVATE))
    owner = PrincipalContext("sparks", "local:text", AudienceKind.PRIVATE)
    assert prediction.disposition(
        principal=owner, at=NOW, operator_stop=True, gaming=False,
    ) is PredictionDisposition.SHADOW_ONLY
    assert prediction.disposition(
        principal=owner, at=NOW, operator_stop=False, gaming=True,
    ) is PredictionDisposition.SHADOW_ONLY
    assert prediction.disposition(
        principal=owner, at=NOW + timedelta(minutes=6),
        operator_stop=False, gaming=False,
    ) is PredictionDisposition.SUPPRESSED
    with pytest.raises(PermissionError):
        service.set_mode(PredictionMode.LIMITED, at=NOW)
    service.set_mode(PredictionMode.ADVISORY, at=NOW, approval_ref="owner-ui:advisory")
    service.revoke_mode(at=NOW + timedelta(seconds=1), approval_ref="operator-stop:1")
    assert service.mode() is PredictionMode.SHADOW
    assert service.diagnostics(principal_id="sparks", audience_id="discord:dm")["traces"] == ()


def test_prediction_mode_advancement_does_not_trust_shaped_string(
    canonical_state_path: Path,
):
    service = LearningService(canonical_state_path)
    with pytest.raises(PermissionError, match="verifier"):
        service.set_mode(
            PredictionMode.ADVISORY,
            at=NOW,
            approval_ref="owner-ui:not-an-authenticated-approval",
        )


def test_signed_candidate_corruption_revocation_and_atomic_rollback(canonical_state_path: Path, tmp_path: Path):
    root = tmp_path / "candidates"
    root.mkdir()
    private = Ed25519PrivateKey.generate()

    def verify(key_id: str, message: bytes, signature: bytes) -> bool:
        if key_id != "owner-key":
            return False
        try:
            private.public_key().verify(signature, message)
        except Exception:
            return False
        return True

    registry = CandidateRegistry(
        canonical_state_path, artifact_root=root, verify_signature=verify,
        approval_verifier=_ExactApprovalVerifier(),
    )
    artifacts = []
    for name in ("baseline", "candidate"):
        path = (root / f"{name}.json").resolve()
        path.write_text(json.dumps({
            "version": 1, "model_type": "linear", "features": ["cpu"],
            "weights": [0.0 if name == "baseline" else 1.0], "bias": 0.0,
        }, sort_keys=True), encoding="utf-8")
        digest = sha256(path.read_bytes()).hexdigest()
        unsigned = CandidateArtifact(
            candidate_id="ml-candidate:" + digest, artifact_path=path,
            artifact_sha256=digest, signature=b"pending", signer_key_id="owner-key",
            format="json-linear-v1", runtime="python-cpu", created_at=NOW,
            expires_at=NOW + timedelta(days=30), max_bytes=1024,
            max_ram_mb=64, max_cpu_seconds=5,
            fallback_candidate_id=(artifacts[0].candidate_id if artifacts else None),
        )
        signed = CandidateArtifact(
            **{field: getattr(unsigned, field) for field in unsigned.__dataclass_fields__
               if field != "signature"},
            signature=private.sign(unsigned.signed_bytes()),
        )
        registry.register(signed)
        artifacts.append(signed)

    grant = _grant()
    learning = _service(canonical_state_path)
    with pytest.raises(PermissionError, match="absent, changed, or revoked"):
        registry.activate(
            artifacts[0].candidate_id, grant=grant,
            evaluation_id="ml-evaluation:missing", at=NOW + timedelta(minutes=1),
        )
    learning.record_grant(grant)
    with pytest.raises(PermissionError, match="lacks independent evaluation"):
        registry.activate(
            artifacts[0].candidate_id, grant=grant,
            evaluation_id="ml-evaluation:missing", at=NOW + timedelta(minutes=1),
        )
    for index, group in enumerate(("venus", "artemis", "gaia")):
        learning.admit_sample(
            _record_pair(canonical_state_path, index=index, group=group), grant,
        )
    dataset = learning.create_manifest(
        principal_id="sparks", audience_id="local:text",
        purpose="host-pressure-forecast", at=NOW + timedelta(hours=1), seed=1,
    )
    baseline_evaluation = learning.evaluate(
        dataset.manifest_id, baseline_digest="f" * 64,
        candidate_digest=artifacts[0].artifact_sha256,
        baseline=lambda _: OutcomeClass.POSITIVE,
        candidate=lambda _: OutcomeClass.POSITIVE,
        at=NOW + timedelta(hours=2),
    )
    candidate_evaluation = learning.evaluate(
        dataset.manifest_id, baseline_digest=artifacts[0].artifact_sha256,
        candidate_digest=artifacts[1].artifact_sha256,
        baseline=lambda _: OutcomeClass.NEGATIVE,
        candidate=lambda _: OutcomeClass.POSITIVE,
        at=NOW + timedelta(hours=2, seconds=1),
    )
    registry.activate(
        artifacts[0].candidate_id, grant=grant,
        evaluation_id=baseline_evaluation.evaluation_id,
        at=NOW + timedelta(hours=2, minutes=1),
    )
    equal_evaluation = learning.evaluate(
        dataset.manifest_id, baseline_digest=artifacts[0].artifact_sha256,
        candidate_digest=artifacts[1].artifact_sha256,
        baseline=lambda _: OutcomeClass.POSITIVE,
        candidate=lambda _: OutcomeClass.POSITIVE,
        at=NOW + timedelta(hours=2, seconds=2),
    )
    with pytest.raises(PermissionError, match="does not beat"):
        registry.activate(
            artifacts[1].candidate_id, grant=grant,
            evaluation_id=equal_evaluation.evaluation_id,
            at=NOW + timedelta(hours=2, minutes=1, seconds=1),
        )
    with sqlite3.connect(canonical_state_path) as db:
        original_evaluation = db.execute(
            "SELECT body_json FROM ml_evaluation WHERE evaluation_id=?",
            (candidate_evaluation.evaluation_id,),
        ).fetchone()[0]
        changed_evaluation = json.loads(original_evaluation)
        changed_evaluation["paired_delta"] = 999.0
        db.execute(
            "UPDATE ml_evaluation SET body_json=? WHERE evaluation_id=?",
            (json.dumps(changed_evaluation, sort_keys=True, separators=(",", ":")),
             candidate_evaluation.evaluation_id),
        )
    with pytest.raises(PermissionError, match="evaluation integrity"):
        registry.activate(
            artifacts[1].candidate_id, grant=grant,
            evaluation_id=candidate_evaluation.evaluation_id,
            at=NOW + timedelta(hours=2, minutes=1, seconds=2),
        )
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "UPDATE ml_evaluation SET body_json=? WHERE evaluation_id=?",
            (original_evaluation, candidate_evaluation.evaluation_id),
        )
    registry.activate(
        artifacts[1].candidate_id, grant=grant,
        evaluation_id=candidate_evaluation.evaluation_id,
        at=NOW + timedelta(hours=2, minutes=2),
    )
    assert registry.active(
        principal_id="sparks", audience_id="local:text",
        purpose="host-pressure-forecast",
        at=NOW + timedelta(hours=2, minutes=3),
    ) == artifacts[1].candidate_id
    assert registry.active(
        principal_id="sparks", audience_id="discord:dm",
        purpose="host-pressure-forecast",
        at=NOW + timedelta(hours=2, minutes=3),
    ) is None
    restarted = CandidateRegistry(
        canonical_state_path, artifact_root=root, verify_signature=verify,
        approval_verifier=_ExactApprovalVerifier(),
    )
    assert restarted.active(
        principal_id="sparks", audience_id="local:text",
        purpose="host-pressure-forecast",
        at=NOW + timedelta(hours=2, minutes=3),
    ) == artifacts[1].candidate_id
    assert registry.rollback(grant=grant, at=NOW + timedelta(hours=2, minutes=4)) == artifacts[0].candidate_id

    with pytest.raises(PermissionError, match="stale"):
        registry.load(artifacts[1].candidate_id, at=NOW + timedelta(days=31))

    artifacts[0].artifact_path.write_bytes(b"tampered")
    with pytest.raises(PermissionError, match="corrupt"):
        registry.load(artifacts[0].candidate_id, at=NOW + timedelta(hours=2, minutes=5))
    registry.revoke(
        artifacts[1].candidate_id, at=NOW + timedelta(hours=2, minutes=6),
        approval_ref="owner-ui:revoke-candidate",
    )
    with pytest.raises(PermissionError, match="revoked"):
        registry.load(artifacts[1].candidate_id, at=NOW + timedelta(hours=2, minutes=7))
