"""B06: durable subject-scoped impressions and their provider wiring."""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.rel.impressions import (
    ImpressionChangeKind,
    ImpressionError,
    ImpressionKind,
    ImpressionRecord,
    ImpressionService,
    ImpressionStatus,
    ImpressionStore,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)

PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"
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


def _capture_runtime(monkeypatch: pytest.MonkeyPatch, app: SofiaApplication):
    requests = []

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(content="Captured.")

    monkeypatch.setattr(app.runtime, "respond", respond)
    return requests


def _quiet_background(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_HABIT_LEARNING", "0")


def impression_record(
    *,
    subject: str,
    kind: ImpressionKind = ImpressionKind.GUARDEDNESS,
    level: float = 0.4,
    audience: str = "local:text",
    revision: int = 1,
    change: ImpressionChangeKind = ImpressionChangeKind.ORIGIN,
    status: ImpressionStatus = ImpressionStatus.ACTIVE,
    impression_id: str = "impression:test-1",
    evidence: tuple[str, ...] = ("conversation:turn-9",),
    recorded_at: datetime = NOW,
):
    return ImpressionRecord(
        impression_id=impression_id,
        revision=revision,
        principal_id="person:sparks",
        subject=subject,
        kind=kind,
        level=level,
        reason="The lint review arguments were harsh and specific.",
        evidence_refs=evidence,
        audience_id=audience,
        change_kind=change,
        status=status,
        recorded_at=recorded_at,
    )


def test_store_appends_reloads_and_rejects_races(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ImpressionStore(tmp_path / "sofia.db")
    first = impression_record(subject="lint-reviews")
    store.hold(first, expected_revision=None)
    current = store.current(
        principal_id="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        audience_id="local:text",
    )
    assert current == first
    with pytest.raises(ImpressionError, match="already exists"):
        store.hold(first, expected_revision=None)
    with pytest.raises(ImpressionError, match="origin revision 1"):
        store.hold(
            impression_record(subject="lint-reviews-2", revision=2),
            expected_revision=None,
        )
    reopened = ImpressionStore(tmp_path / "sofia.db")
    assert reopened.current(
        principal_id="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        audience_id="local:text",
    ) == first


def test_store_rejects_stale_expected_revision(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ImpressionStore(tmp_path / "sofia.db")
    first = impression_record(subject="lint-reviews")
    store.hold(first, expected_revision=None)
    second = impression_record(subject="lint-reviews", revision=2)
    store.hold(second, expected_revision=1)
    with pytest.raises(ImpressionError, match="revision changed"):
        store.hold(second, expected_revision=1)
    with pytest.raises(ImpressionError, match="revision changed"):
        store.hold(
            impression_record(subject="lint-reviews", revision=2),
            expected_revision=9,
        )


def test_impressions_are_subject_and_audience_scoped(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ImpressionStore(tmp_path / "sofia.db")
    store.hold(impression_record(subject="lint-reviews"), expected_revision=None)
    assert store.current(
        principal_id="person:sparks",
        subject="code-review-kinetics",
        kind=ImpressionKind.GUARDEDNESS,
        audience_id="local:text",
    ) is None
    assert store.current(
        principal_id="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        audience_id="discord:dm:8",
    ) is None
    # A subject-scoped row must not poison an unrelated subject read.
    assert store.current(
        principal_id="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.TRUST,
        audience_id="local:text",
    ) is None


def test_service_owner_gate_and_scoped_writes(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ImpressionService(ImpressionStore(tmp_path / "sofia.db"))
    foreign = PrincipalContext(
        "person:other", "local:text", AudienceKind.PRIVATE, "Other"
    )
    with pytest.raises(PermissionError, match="authenticated Sparks principal"):
        service.observe(
            foreign,
            about="person:sparks",
            subject="lint-reviews",
            kind=ImpressionKind.GUARDEDNESS,
            level=0.4,
            reason="The lint review arguments were harsh.",
            evidence_refs=("conversation:turn-9",),
            audience_id="local:text",
        )
    origin = service.observe(
        local_sparks_principal(),
        about="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        level=0.4,
        reason="The lint review arguments were harsh.",
        evidence_refs=("conversation:turn-9",),
        audience_id="local:text",
        recorded_at=NOW,
    )
    with pytest.raises(ImpressionError, match="revision changed"):
        service.reconcile(
            local_sparks_principal(),
            impression_id=origin.impression_id,
            expected_revision=7,
            level=0.2,
            reason="The run-through lesson went well.",
            evidence_refs=("conversation:turn-21",),
        )
    reconciled = service.reconcile(
        local_sparks_principal(),
        impression_id=origin.impression_id,
        expected_revision=origin.revision,
        level=0.2,
        reason="The run-through lesson went well.",
        evidence_refs=("conversation:turn-21",),
        recorded_at=NOW + timedelta(days=1),
    )
    assert reconciled.revision == 2
    assert reconciled.change_kind is ImpressionChangeKind.RECONCILE
    history = service.store.history(origin.impression_id)
    assert [record.revision for record in history] == [1, 2]
    with pytest.raises(LookupError):
        service.reconcile(
            local_sparks_principal(),
            impression_id="impression:missing",
            expected_revision=1,
            level=0.2,
            reason="still fine",
            evidence_refs=("conversation:turn-22",),
        )
    with pytest.raises(TypeError):
        class NotAPrincipal:
            principal_id = "person:sparks"
            audience_id = "local:text"
        service.observe(
            NotAPrincipal(),  # type: ignore[arg-type]
            about="person:sparks",
            subject="lint-reviews",
            kind=ImpressionKind.TRUST,
            level=0.5,
            reason="Steady cooperation.",
            evidence_refs=("conversation:turn-30",),
            audience_id="local:text",
        )


def test_withdrawn_impressions_leave_active_scopes(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ImpressionService(ImpressionStore(tmp_path / "sofia.db"))
    origin = service.observe(
        local_sparks_principal(),
        about="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        level=0.4,
        reason="The lint review arguments were harsh.",
        evidence_refs=("conversation:turn-9",),
        audience_id="local:text",
        recorded_at=NOW,
    )
    active = service.active(local_sparks_principal(), about="person:sparks", audience_id="local:text")
    assert len(active) == 1
    withdrawn = service.withdraw(
        local_sparks_principal(),
        impression_id=origin.impression_id,
        expected_revision=origin.revision,
        reason="The lessons ended differently than they started.",
        evidence_refs=("conversation:turn-31",),
        recorded_at=NOW + timedelta(days=2),
    )
    assert withdrawn.status is ImpressionStatus.WITHDRAWN
    assert withdrawn.level == 0.0
    assert service.active(
        local_sparks_principal(), about="person:sparks", audience_id="local:text"
    ) == ()
    assert service.working_context(
        local_sparks_principal(), about="person:sparks", audience_id="local:text"
    ) is None


def test_working_context_projects_the_recorded_stance(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ImpressionService(ImpressionStore(tmp_path / "sofia.db"))
    assert service.working_context(
        local_sparks_principal(), about="person:sparks", audience_id="local:text"
    ) is None
    service.observe(
        local_sparks_principal(),
        about="person:sparks",
        subject="lint-reviews",
        kind=ImpressionKind.GUARDEDNESS,
        level=0.4,
        reason="The lint review arguments were harsh.",
        evidence_refs=("conversation:turn-9", "memory:session-42"),
        audience_id="local:text",
        recorded_at=NOW,
    )
    text = service.working_context(
        local_sparks_principal(), about="person:sparks", audience_id="local:text"
    )
    assert text is not None
    assert text.splitlines()[0].startswith("SUBJECT-SCOPED IMPRESSIONS")
    assert "- guardedness 0.40 about lint-reviews:" in text
    assert "evidence: conversation:turn-9, memory:session-42" in text
    assert "never generalized beyond the subject" in text
    other_audience = service.working_context(
        local_sparks_principal(),
        about="person:sparks",
        audience_id="discord:dm:8",
    )
    assert other_audience is None


def test_validation_rejects_bad_levels_and_evidence(tmp_path):
    with pytest.raises(ValueError, match="level"):
        impression_record(subject="lint-reviews", level=1.5)
    with pytest.raises(ValueError, match="1..8"):
        impression_record(subject="lint-reviews", evidence=())
    with pytest.raises(TypeError, match="tuple"):
        impression_record(subject="lint-reviews", evidence=["conversation:9"])


def test_bootstrap_wires_impressions_and_agency(tmp_path):
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.impressions, ImpressionService)
        assert app.conversation._impression_provider is not None
        assert app.agency.anticipations is not None
        app.start()
        origin = app.impressions.observe(
            principal=local_sparks_principal(),
            about="person:sparks",
            subject="lint-reviews",
            kind=ImpressionKind.GUARDEDNESS,
            level=0.4,
            reason="The lint review arguments were harsh.",
            evidence_refs=("conversation:turn-9",),
            audience_id="local:text",
            recorded_at=NOW,
        )
        active = app.impressions.active(
            principal=local_sparks_principal(),
            about="person:sparks",
            audience_id="local:text",
        )
        assert tuple(record.impression_id for record in active) == (
            origin.impression_id,
        )
    finally:
        app.shutdown()


def test_impression_context_reaches_the_model_request(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        app.impressions.observe(
            principal=local_sparks_principal(),
            about="person:sparks",
            subject="lint-reviews",
            kind=ImpressionKind.GUARDEDNESS,
            level=0.4,
            reason="The lint review arguments were harsh.",
            evidence_refs=("conversation:turn-9",),
            audience_id="local:text",
            recorded_at=NOW,
        )
        app.conversation.respond(
            "I want to be honest about our working relationship after the "
            "lint review arguments.",
            principal=local_sparks_principal(),
        )
        assert requests, "a generative turn must reach the model request"
        request = requests[-1]
        blocks = [
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("SUBJECT-SCOPED IMPRESSIONS")
        ]
        assert len(blocks) == 1
        assert "guardedness 0.40 about lint-reviews" in blocks[0]
        assert "conversation:turn-9" in blocks[0]
    finally:
        app.shutdown()
