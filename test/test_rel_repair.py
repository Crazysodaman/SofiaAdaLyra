"""B06: relationship-repair offers — vulnerable, never coercive."""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.core.rel.repair import (
    RepairChangeKind,
    RepairError,
    RepairService,
    RepairStatus,
    RepairStore,
)
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 6, 28, 10, 5, tzinfo=timezone.utc)

PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "core" / "constitution" / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "core" / "constitution" / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "core" / "identity" / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "core" / "embodiment" / "avatar.json"
)


def configuration(tmp_path: Path) -> SofiaConfiguration:
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
    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def test_repair_offer_scope_and_outcomes(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = RepairStore(tmp_path / "sofia.db")
    service = RepairService(store)
    principal = local_sparks_principal()
    origin = service.offer(
        principal,
        about="person:sparks",
        subject="lint-reviews",
        message=(
            "I aim to keep the review friction honest but light; the tone "
            "I used earlier was harsher than the point needed."
        ),
        evidence_refs=("conversation:turn-70",),
        audience_id="local:text",
        impression_ref="impression:test-1",
        recorded_at=NOW,
    )
    assert origin.status is RepairStatus.OPEN
    assert store.current(
        principal_id="person:sparks", subject="lint-reviews",
        audience_id="local:text",
    ) == origin
    with pytest.raises(RepairError, match="already exists"):
        service.offer(
            principal, about="person:sparks", subject="lint-reviews",
            message="Parallel offer.", evidence_refs=("conversation:turn-71",),
            audience_id="local:text", recorded_at=NOW + timedelta(hours=1),
        )
    reopened = RepairStore(tmp_path / "sofia.db")
    assert reopened.current(
        principal_id="person:sparks", subject="lint-reviews",
        audience_id="local:text",
    ) == origin
    accepted = service.observe_outcome(
        principal,
        repair_id=origin.repair_id,
        expected_revision=origin.revision,
        outcome=RepairChangeKind.ACCEPT,
        message="They read the rephrase and joined for a calmer pass.",
        evidence_refs=("conversation:turn-76",),
        recorded_at=NOW + timedelta(days=1),
    )
    assert accepted.status is RepairStatus.ACCEPTED
    assert accepted.revision == 2
    with pytest.raises(ValueError, match="only open repair offers"):
        service.observe_outcome(
            principal,
            repair_id=origin.repair_id,
            expected_revision=accepted.revision,
            outcome=RepairChangeKind.DECLINE,
            message="Impossible after acceptance.",
            evidence_refs=("conversation:turn-77",),
            recorded_at=NOW + timedelta(days=2),
        )
    assert [
        (row.revision, row.change_kind.value)
        for row in store.history(origin.repair_id)
    ] == [(1, "offer"), (2, "accept")]


def test_decline_and_withdraw_are_recorded_without_pressure(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = RepairService(RepairStore(tmp_path / "sofia.db"))
    principal = local_sparks_principal()
    origin = service.offer(
        principal,
        about="person:sparks",
        subject="lint-reviews",
        message=("I'd like to redo that review exchange calmly."),
        evidence_refs=("conversation:turn-80",),
        audience_id="local:text",
        recorded_at=NOW,
    )
    declined = service.observe_outcome(
        principal,
        repair_id=origin.repair_id,
        expected_revision=origin.revision,
        outcome=RepairChangeKind.DECLINE,
        message="They asked to leave it; no further offers planned.",
        evidence_refs=("conversation:turn-81",),
        recorded_at=NOW + timedelta(days=1),
    )
    assert declined.status is RepairStatus.DECLINED
    assert service.store.open_offers(audience_id="local:text") == ()
    withdrawn_scope = service.offer(
        principal,
        about="person:sparks",
        subject="milestone-train",
        message=("I will re-check the notes before asserting again."),
        evidence_refs=("conversation:turn-90",),
        audience_id="discord:dm:8",
        recorded_at=NOW + timedelta(days=2),
    )
    withdrawn = service.observe_outcome(
        principal,
        repair_id=withdrawn_scope.repair_id,
        expected_revision=withdrawn_scope.revision,
        outcome=RepairChangeKind.WITHDRAW,
        message="Withdrew after realizing the premise was wrong.",
        evidence_refs=("conversation:turn-91",),
        recorded_at=NOW + timedelta(days=3),
    )
    assert withdrawn.status is RepairStatus.WITHDRAWN
    assert service.store.open_offers(audience_id="discord:dm:8") == ()
    with pytest.raises(LookupError):
        service.observe_outcome(
            principal,
            repair_id="repair:missing",
            expected_revision=1,
            outcome=RepairChangeKind.DECLINE,
            message="n/a",
            evidence_refs=("conversation:turn-92",),
        )
    with pytest.raises(ValueError, match="outcomes are accept"):
        service.observe_outcome(
            principal,
            repair_id=origin.repair_id,
            expected_revision=declined.revision,
            outcome=RepairChangeKind.OFFER,
            message="n/a",
            evidence_refs=("conversation:turn-93",),
        )


def test_repair_owner_gate(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = RepairService(RepairStore(tmp_path / "sofia.db"))
    foreign = PrincipalContext(
        "person:other", "local:text", AudienceKind.PRIVATE, "Other"
    )
    with pytest.raises(PermissionError, match="authenticated Sparks principal"):
        service.offer(
            foreign,
            about="person:sparks",
            subject="lint-reviews",
            message="Not their call.",
            evidence_refs=("conversation:turn-1",),
            audience_id="local:text",
        )


def test_bootstrap_wires_relationship_repair(tmp_path):
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.relationship_repair, RepairService)
        app.start()
        origin = app.relationship_repair.offer(
            principal=local_sparks_principal(),
            about="person:sparks",
            subject="lint-reviews",
            message=(
                "I aim to keep the review friction honest but the words "
                "kind."
            ),
            evidence_refs=("conversation:turn-70",),
            audience_id="local:text",
            recorded_at=NOW,
        )
        assert origin.status is RepairStatus.OPEN
    finally:
        app.shutdown()
