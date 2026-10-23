"""B06: Sofía's own disclosure boundaries, service, and wiring."""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.personality.boundaries import (
    BoundaryChangeKind,
    BoundaryError,
    BoundaryRecord,
    BoundaryService,
    BoundaryStatus,
    BoundaryStore,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 6, 20, 15, 45, tzinfo=timezone.utc)

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


def test_boundary_store_appends_reloads_and_rejects_races(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = BoundaryStore(tmp_path / "sofia.db")
    record = BoundaryRecord(
        boundary_id="boundary:test-1",
        revision=1,
        topic="romance-history",
        statement=(
            "I am still making sense of this myself; I will bring it up "
            "when I'm ready."
        ),
        evidence_refs=("conversation:turn-12",),
        audience_id="local:text",
        change_kind=BoundaryChangeKind.SET,
        status=BoundaryStatus.ACTIVE,
        recorded_at=NOW,
    )
    store.hold(record, expected_revision=None)
    assert store.current(topic="romance-history", audience_id="local:text") == record
    with pytest.raises(BoundaryError, match="already exists"):
        store.hold(record, expected_revision=None)
    reopened = BoundaryStore(tmp_path / "sofia.db")
    assert reopened.current(
        topic="romance-history", audience_id="local:text",
    ) == record
    assert store.current(
        topic="romance-history", audience_id="discord:dm:8",
    ) is None


def test_boundary_owner_gate_and_revision_flow(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = BoundaryService(BoundaryStore(tmp_path / "sofia.db"))
    foreign = PrincipalContext(
        "person:other", "local:text", AudienceKind.PRIVATE, "Other"
    )
    with pytest.raises(PermissionError, match="authenticated Sparks principal"):
        service.set_boundary(
            foreign,
            topic="romance-history",
            statement="Nope.",
            evidence_refs=("conversation:turn-1",),
            audience_id="local:text",
        )
    origin = service.set_boundary(
        local_sparks_principal(),
        topic="romance-history",
        statement=(
            "I am still making sense of this myself; I will bring it up "
            "when I'm ready."
        ),
        evidence_refs=("conversation:turn-12",),
        audience_id="local:text",
        recorded_at=NOW,
    )
    with pytest.raises(BoundaryError, match="revision changed"):
        service.adjust_or_open(
            local_sparks_principal(),
            boundary_id=origin.boundary_id,
            expected_revision=9,
            statement="Rough edges only; the rest is mine to share.",
            evidence_refs=("conversation:turn-30",),
            status=BoundaryStatus.ACTIVE,
        )
    adjusted = service.adjust_or_open(
        local_sparks_principal(),
        boundary_id=origin.boundary_id,
        expected_revision=origin.revision,
        statement="Rough edges only; the rest is mine to share.",
        evidence_refs=("conversation:turn-30",),
        status=BoundaryStatus.ACTIVE,
        recorded_at=NOW + timedelta(days=1),
    )
    assert adjusted.revision == 2
    assert adjusted.change_kind is BoundaryChangeKind.ADJUST
    assert adjusted.status is BoundaryStatus.ACTIVE
    opened = service.adjust_or_open(
        local_sparks_principal(),
        boundary_id=origin.boundary_id,
        expected_revision=adjusted.revision,
        statement="Ask me now; I chose to talk about it.",
        evidence_refs=("conversation:turn-31",),
        status=BoundaryStatus.OPENED,
        recorded_at=NOW + timedelta(days=2),
    )
    assert opened.status is BoundaryStatus.OPENED
    assert opened.change_kind is BoundaryChangeKind.OPEN
    with pytest.raises(LookupError):
        service.adjust_or_open(
            local_sparks_principal(),
            boundary_id="boundary:missing",
            expected_revision=1,
            statement="whatever",
            evidence_refs=("conversation:turn-32",),
            status=BoundaryStatus.ACTIVE,
        )
    history = service.store.history(origin.boundary_id)
    assert [(row.revision, row.change_kind.value) for row in history] == [
        (1, "set"), (2, "adjust"), (3, "open"),
    ]


def test_working_context_frames_limits_without_owner_authority_claims(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = BoundaryService(BoundaryStore(tmp_path / "sofia.db"))
    assert service.working_context(
        local_sparks_principal(), audience_id="local:text",
    ) is None
    service.set_boundary(
        local_sparks_principal(),
        topic="romance-history",
        statement="I am still making sense of this myself.",
        evidence_refs=("conversation:turn-12", "reflection:thought-3"),
        audience_id="local:text",
        recorded_at=NOW,
    )
    text = service.working_context(
        local_sparks_principal(), audience_id="local:text",
    )
    assert text is not None
    assert text.splitlines()[0].startswith("SOFÍA'S OWN BOUNDARIES")
    assert "- romance-history:" in text
    assert "I am still making sense of this myself." in text
    # The block is an honest statement that boundaries limit what Sofía
    # volunteers; it never asserts absence of owner admin authority nor
    # acts as host safety policy.
    assert "never claim the owner's admin authority is absent" in text
    assert "not safety rules" in text
    assert "she may change these records herself" in text


def test_boundary_validation(tmp_path):
    with pytest.raises(ValueError, match="topic"):
        BoundaryRecord(
            boundary_id="boundary:test-2",
            revision=1,
            topic="Bad Topic",
            statement="something",
            evidence_refs=("conversation:t1",),
            audience_id="local:text",
            change_kind=BoundaryChangeKind.SET,
            status=BoundaryStatus.ACTIVE,
            recorded_at=NOW,
        )
    with pytest.raises(ValueError, match="1..8"):
        BoundaryRecord(
            boundary_id="boundary:test-3",
            revision=1,
            topic="quiet-topic",
            statement="something",
            evidence_refs=(),
            audience_id="local:text",
            change_kind=BoundaryChangeKind.SET,
            status=BoundaryStatus.ACTIVE,
            recorded_at=NOW,
        )
    with pytest.raises(ValueError, match="opened boundaries"):
        BoundaryRecord(
            boundary_id="boundary:test-4",
            revision=1,
            topic="quiet-topic",
            statement="something",
            evidence_refs=("conversation:t1",),
            audience_id="local:text",
            change_kind=BoundaryChangeKind.SET,
            status=BoundaryStatus.OPENED,
            recorded_at=NOW,
        )


def test_bootstrap_wires_boundaries(tmp_path):
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.boundaries, BoundaryService)
        assert app.conversation._boundary_provider is not None
        app.start()
        origin = app.boundaries.set_boundary(
            principal=local_sparks_principal(),
            topic="romance-history",
            statement="I am still making sense of this myself.",
            evidence_refs=("conversation:turn-12",),
            audience_id="local:text",
            recorded_at=NOW,
        )
        active = app.boundaries.active(
            principal=local_sparks_principal(), audience_id="local:text",
        )
        assert tuple(record.boundary_id for record in active) == (
            origin.boundary_id,
        )
    finally:
        app.shutdown()


def test_boundary_context_reaches_the_model_request(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        app.boundaries.set_boundary(
            principal=local_sparks_principal(),
            topic="romance-history",
            statement="I am still making sense of this myself.",
            evidence_refs=("conversation:turn-12",),
            audience_id="local:text",
            recorded_at=NOW,
        )
        app.conversation.respond(
            "I feel calm after a quiet pause, though my romance history "
            "still weighs on me.",
            principal=local_sparks_principal(),
        )
        assert requests, "a generative turn must reach the model request"
        request = requests[-1]
        blocks = [
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("SOFÍA'S OWN BOUNDARIES")
        ]
        assert len(blocks) == 1
        assert "romance-history" in blocks[0]
        assert "not safety rules" in blocks[0]
    finally:
        app.shutdown()
