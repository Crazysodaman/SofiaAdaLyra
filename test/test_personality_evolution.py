"""Tests for trait-level personality evolution store and service.

The store is an append-only CAS revision log; the service is owner-gated
and projects influence-only context. The static seed profile and identity
floor are never touched by evolution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.platform.application.personality_evolution import (
    PersonalityEvolutionService,
)
from sofia.core.personality.evolution import (
    TraitChangeKind,
    TraitDriftEntry,
    TraitEvolutionError,
    TraitEvolutionStore,
)
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import local_sparks_principal
from sofia.core.goals.evidence import GoalEvidenceLedger
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

EVIDENCE = ("memory:session-2026-02-01",)


def aware(year: int = 2026, month: int = 4, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def guest_principal() -> PrincipalContext:
    return PrincipalContext(
        principal_id="person:guest",
        audience_id="local:guest",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Guest",
    )


@pytest.fixture()
def sofia_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(db_path)
    return db_path


@pytest.fixture()
def store(sofia_db: Path) -> TraitEvolutionStore:
    return TraitEvolutionStore(sofia_db)


@pytest.fixture()
def service(store: TraitEvolutionStore) -> PersonalityEvolutionService:
    return PersonalityEvolutionService(store)


def _origin_payload(**overrides) -> dict:
    payload = {
        "trait": "self-verification",
        "weight": 0.7,
        "confidence": 0.85,
        "reason": "Recurring reviewed corrections of unverified claims.",
        "evidence_refs": EVIDENCE,
        "expected_revision": None,
        "now": aware(),
    }
    payload.update(overrides)
    return payload


def _service_origin(**overrides) -> dict:
    payload = dict(_origin_payload())
    payload.pop("expected_revision")
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- store level


def test_hold_creates_origin_and_readback(store: TraitEvolutionStore) -> None:
    record = store.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(),
    )
    assert record.revision == 1
    assert record.change_kind is TraitChangeKind.ORIGIN
    assert record.recorded_at == aware()
    current = store.current(record.trait)
    assert current == record
    assert store.current_all() == (record,)


def test_duplicate_trait_origin_is_rejected(store: TraitEvolutionStore) -> None:
    store.hold(change_kind=TraitChangeKind.ORIGIN, **_origin_payload())
    with pytest.raises(TraitEvolutionError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(weight=0.9),
        )


def test_cas_revision_requires_matching_expected_revision(
    store: TraitEvolutionStore,
) -> None:
    origin = store.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(),
    )
    adjusted = store.hold(
        trait=origin.trait,
        weight=0.85,
        confidence=0.9,
        change_kind=TraitChangeKind.ADJUST,
        reason="Reinforced by verified audit outcomes.",
        evidence_refs=EVIDENCE,
        expected_revision=origin.revision,
        now=aware(2026, 4, 20),
    )
    assert adjusted.revision == 2
    assert adjusted.change_kind is TraitChangeKind.ADJUST
    history = store.history(origin.trait)
    assert [record.revision for record in history] == [1, 2]
    assert history[0] == origin
    with pytest.raises(TraitEvolutionError):
        store.hold(
            trait=origin.trait,
            weight=0.9,
            confidence=0.9,
            change_kind=TraitChangeKind.ADJUST,
            reason="Stale revision attempt.",
            evidence_refs=EVIDENCE,
            expected_revision=1,
            now=aware(2026, 4, 21),
        )


def test_retire_requires_zero_weight(store: TraitEvolutionStore) -> None:
    origin = store.hold(change_kind=TraitChangeKind.ORIGIN, **_origin_payload())
    retired = store.hold(
        trait=origin.trait,
        weight=0.0,
        confidence=1.0,
        change_kind=TraitChangeKind.RETIRE,
        reason="The owner reviewed and retired this trait influence.",
        evidence_refs=EVIDENCE,
        expected_revision=origin.revision,
        now=aware(2026, 4, 10),
    )
    assert retired.weight == 0.0
    assert store.active_influences() == ()
    with pytest.raises(ValueError):
        store.hold(
            trait=origin.trait,
            weight=0.4,
            confidence=1.0,
            change_kind=TraitChangeKind.RETIRE,
            reason="Invalid retire attempt with nonzero weight.",
            evidence_refs=EVIDENCE,
            expected_revision=1,
            now=aware(2026, 4, 11),
        )


def test_active_influences_filters_deterministically(
    store: TraitEvolutionStore,
) -> None:
    store.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(trait="self-verification"),
    )
    store.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(
            trait="precision-demonstration",
            weight=0.4,
            confidence=0.5,
        ),
    )
    influences = store.active_influences()
    assert [influence.trait for influence in influences] == [
        "self-verification"
    ]
    broader = store.active_influences(
        minimum_confidence=0.4,
        minimum_weight=0.2,
    )
    assert [influence.trait for influence in broader] == [
        "self-verification",
        "precision-demonstration",
    ]


def test_reopen_continuity(sofia_db: Path) -> None:
    first = TraitEvolutionStore(sofia_db)
    origin = first.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(),
    )
    second = TraitEvolutionStore(sofia_db)
    assert second.current(origin.trait) == origin


def test_drift_entries_report_window_movement(store: TraitEvolutionStore) -> None:
    store.hold(
        change_kind=TraitChangeKind.ORIGIN,
        **_origin_payload(now=aware()),
    )
    store.hold(
        trait="self-verification",
        weight=0.9,
        confidence=0.95,
        change_kind=TraitChangeKind.ADJUST,
        reason="Reviewed evidence reinforced the trait.",
        evidence_refs=EVIDENCE,
        expected_revision=1,
        now=aware(2026, 4, 29),
    )
    entries = store.drift_entries(
        window_days=7,
        now=aware(2026, 4, 30),
    )
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, TraitDriftEntry)
    assert entry.trait == "self-verification"
    assert entry.previous_weight == 0.7
    assert entry.current_weight == 0.9
    assert entry.delta == 0.2
    assert entry.revisions_in_window == 1
    later = store.drift_entries(window_days=1, now=aware(2026, 4, 6))
    assert len(later) == 1
    assert later[0].previous_weight == 0.7
    assert later[0].current_weight == 0.9
    assert later[0].revisions_in_window == 0


def test_weight_before_observation_boundary(store: TraitEvolutionStore) -> None:
    store.hold(change_kind=TraitChangeKind.ORIGIN, **_origin_payload())
    assert store.weight_before("self-verification", at=aware()) == 0.7
    assert store.weight_before("self-verification", at=aware(2025, 1, 1)) is None


def test_invalid_records_are_rejected(store: TraitEvolutionStore) -> None:
    with pytest.raises(ValueError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(now=datetime(2026, 4, 1)),
        )
    with pytest.raises(ValueError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(trait="2short"),
        )
    with pytest.raises(ValueError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(trait="self verification"),
        )
    with pytest.raises(ValueError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(evidence_refs=("not-a-valid-ref",)),
        )
    with pytest.raises(ValueError):
        store.hold(
            change_kind=TraitChangeKind.ORIGIN,
            **_origin_payload(weight=1.5),
        )


def test_second_revision_cannot_be_origin(store: TraitEvolutionStore) -> None:
    origin = store.hold(change_kind=TraitChangeKind.ORIGIN, **_origin_payload())
    with pytest.raises(ValueError):
        store.hold(
            trait=origin.trait,
            weight=0.8,
            confidence=0.9,
            change_kind=TraitChangeKind.ORIGIN,
            reason="An illegitimate re-origin attempt.",
            evidence_refs=EVIDENCE,
            expected_revision=origin.revision,
            now=aware(2026, 4, 10),
        )


# ------------------------------------------------------------- service level


def test_service_is_owner_gated(service: PersonalityEvolutionService) -> None:
    with pytest.raises(PermissionError):
        service.record_trait(
            principal=guest_principal(),
            **_service_origin(),
        )
    with pytest.raises(TypeError):
        service.record_trait(
            principal=None,
            **_service_origin(),
        )
    assert service.expression_influences() == ()


def test_service_records_reviewed_traits(
    service: PersonalityEvolutionService,
) -> None:
    service.record_trait(
        principal=local_sparks_principal(),
        **_service_origin(),
    )
    adjusted = service.adjust_trait(
        principal=local_sparks_principal(),
        trait="self-verification",
        weight=0.9,
        confidence=0.95,
        reason="Reinforced by verified audit outcomes.",
        evidence_refs=EVIDENCE,
        expected_revision=1,
        correct=False,
        now=aware(2026, 4, 15),
    )
    assert adjusted.revision == 2
    assert adjusted.change_kind is TraitChangeKind.ADJUST
    context = service.influence_context()
    assert context is not None
    assert "EVIDENCE-REVIEWED EVOLVED TRAITS" in context
    assert "self-verification" in context
    assert "non-authoritative" in context


def test_influence_context_limits_and_empty_state(
    service: PersonalityEvolutionService,
) -> None:
    assert service.influence_context() is None
    for index in range(9):
        service.record_trait(
            principal=local_sparks_principal(),
            trait=f"trait-{index:02d}",
            weight=0.5 + index * 0.01,
            confidence=0.9,
            reason=f"Reviewed observation {index}.",
            evidence_refs=EVIDENCE,
            now=aware(),
        )
    context = service.influence_context(limit=4)
    assert context is not None
    assert len(context.splitlines()) == 4 + 2


def test_evidence_verifier_gates_traits(sofia_db: Path) -> None:
    service = PersonalityEvolutionService(
        TraitEvolutionStore(sofia_db),
        evidence_verifier=lambda ref: ref.startswith("memory:"),
    )
    with pytest.raises(ValueError):
        service.record_trait(
            principal=local_sparks_principal(),
            trait="self-verification",
            weight=0.7,
            confidence=0.85,
            reason="Recurring reviewed corrections.",
            evidence_refs=("conversation:turn-11",),
            now=aware(),
        )
    accepted = service.record_trait(
        principal=local_sparks_principal(),
        trait="self-verification",
        weight=0.7,
        confidence=0.85,
        reason="Recurring reviewed corrections.",
        evidence_refs=("memory:session-2026-02-01",),
        now=aware(),
    )
    assert accepted.evidence_refs == ("memory:session-2026-02-01",)


def test_retire_flow_removes_influence(service: PersonalityEvolutionService) -> None:
    principal = local_sparks_principal()
    origin = service.record_trait(
        principal=principal,
        **_service_origin(),
    )
    assert service.influence_context() is not None
    service.retire_trait(
        principal=principal,
        trait=origin.trait,
        reason="The owner reviewed and retired this trait.",
        evidence_refs=EVIDENCE,
        expected_revision=origin.revision,
        now=aware(2026, 4, 12),
    )
    assert service.influence_context() is None
    assert service.expression_influences() == ()
    history = service.history(origin.trait)
    assert [record.change_kind for record in history] == [
        TraitChangeKind.ORIGIN,
        TraitChangeKind.RETIRE,
    ]


def test_service_drift_entries_delegate_window(
    service: PersonalityEvolutionService,
) -> None:
    principal = local_sparks_principal()
    service.record_trait(
        principal=principal,
        **_service_origin(),
    )
    entries = service.drift_entries(window_days=14, now=aware(2026, 4, 2))
    assert len(entries) == 1
    assert entries[0].delta == 0.7


# ------------------------------------------------------------- wiring level


def test_evolved_traits_reach_the_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timezone as _timezone
    from pathlib import Path as _Path

    from sofia.platform.application import SofiaApplication
    from sofia.core.cognition.model import CognitiveResponse, CognitiveRole
    from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
    from sofia.core.social.principals import local_sparks_principal
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

    project_root = _Path(__file__).parent.parent

    configuration = SofiaConfiguration(
        constitution_path=str(
            project_root / "src" / "sofia" / "core" / "constitution" / "constitution.md"
        ),
        constitution_hash_path=str(
            project_root
            / "src"
            / "sofia" / "core" / "constitution"
            / "constitution.sha256"
        ),
        identity_path=str(project_root / "src" / "sofia" / "core" / "identity" / "identity.json"),
        personality_path=str(tmp_path / "personality.json"),
        avatar_path=str(project_root / "src" / "sofia" / "core" / "embodiment" / "avatar.json"),
        state_path=str(tmp_path / "sofia.db"),
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=project_root,
    )
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    personality = tmp_path / "personality.json"
    personality.write_text(
        """{
  "name": "Sofía Ada Lyra",
  "traits": ["rigorous", "curious", "direct"],
  "communication_style": "Clear, direct, warm and natural."
}""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_HABIT_LEARNING", "0")

    app = SofiaApplication(configuration)
    requests = []

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(content="Captured.")

    monkeypatch.setattr(app.runtime, "respond", respond)
    app.start()
    try:
        with pytest.raises(ValueError, match="could not be verified"):
            app.personality_evolution.record_trait(
                principal=local_sparks_principal(),
                trait="unsupported-drift",
                weight=0.8,
                confidence=0.9,
                reason="No canonical evidence exists.",
                evidence_refs=("evidence:missing",),
                now=datetime.now(_timezone.utc),
            )
        GoalEvidenceLedger(configuration.state_path).record(
            kind="reviewed_evidence",
            observed_at=datetime.now(_timezone.utc),
            source="test-reviewed-observation",
            assertion="Recurring reviewed corrections of unverified claims.",
            evidence_ref="memory:session-2026-02-01",
        )
        app.personality_evolution.record_trait(
            principal=local_sparks_principal(),
            trait="self-verification",
            weight=0.8,
            confidence=0.9,
            reason="Recurring reviewed corrections of unverified claims.",
            evidence_refs=("memory:session-2026-02-01",),
            now=datetime.now(_timezone.utc),
        )
        app.conversation.respond(
            "How should we think about reviewing your claims?",
            principal=local_sparks_principal(),
        )
        assert requests, "the turn must reach the model request"
        request = requests[-1]
        evolution = tuple(
            message.content
            for message in request.messages
            if (
                message.role is CognitiveRole.SYSTEM
                and "EVIDENCE-REVIEWED EVOLVED TRAITS" in message.content
            )
        )
        assert len(evolution) == 1
        assert "self-verification" in evolution[0]
        assert "weight=0.80" in evolution[0]
        assert "non-authoritative" in evolution[0]
    finally:
        app.shutdown()
