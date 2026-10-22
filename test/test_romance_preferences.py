"""B06: modeled romance/intimacy preference data, wiring, and gating."""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.personality.preferences import (
    PreferenceDisposition,
    PreferenceRegistry,
    RomancePreferenceService,
    RomancePreferenceState,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 6, 25, 21, 10, tzinfo=timezone.utc)

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


def _shared_principal() -> PrincipalContext:
    return PrincipalContext(
        "person:guest", "discord:channel:42", AudienceKind.SHARED, "Guest"
    )


def test_romance_preferences_are_owner_written_and_audience_gated(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = RomancePreferenceService(PreferenceRegistry(tmp_path / "sofia.db"))
    foreign = PrincipalContext(
        "person:other", "local:text", AudienceKind.PRIVATE, "Other"
    )
    with pytest.raises(PermissionError, match="authenticated owner"):
        service.record_interest(
            principal=foreign, level=0.2, reason="not their session",
            evidence_ref="conversation:turn-1", expected_revision=None, now=NOW,
        )
    with pytest.raises(PermissionError, match="adult-only"):
        service.record_intimate_comfort(
            principal=PrincipalContext(
                "person:sparks", "discord:channel:42", AudienceKind.SHARED,
                "Sparks",
            ),
            level=0.5, reason="shared sparks session",
            evidence_ref="conversation:turn-2", expected_revision=None, now=NOW,
        )
    interest = service.record_interest(
        principal=local_sparks_principal(), level=0.6,
        reason="Warmth grew slowly during the recent evenings.",
        evidence_ref="conversation:turn-40",
        expected_revision=None, now=NOW,
    )
    assert interest.subject is not None
    rows = service.current_rows(local_sparks_principal())
    assert rows[service.INTEREST_CATEGORY].disposition is PreferenceDisposition.LIKE
    with pytest.raises(RuntimeError, match="revision changed"):
        service.record_interest(
            principal=local_sparks_principal(), level=0.4,
            reason="Stale write.",
            evidence_ref="conversation:turn-41",
            expected_revision=9, now=NOW,
        )
    changed = service.record_interest(
        principal=local_sparks_principal(), level=0.4,
        reason="After the quiet week the pull became partly curiosity.",
        evidence_ref="conversation:turn-52",
        expected_revision=interest.revision, now=NOW + timedelta(days=3),
    )
    assert changed.revision == 2


def test_intimate_rows_stay_inside_private_audiences(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = RomancePreferenceService(PreferenceRegistry(tmp_path / "sofia.db"))
    principal = local_sparks_principal()
    service.record_intimate_comfort(
        principal=principal, level=0.7,
        reason="At ease inside the owner-private scope.",
        evidence_ref="conversation:turn-60",
        expected_revision=None, now=NOW,
    )
    state = service.for_principal(principal)
    assert state.intimate_comfort == 0.7
    assert state.interest is None
    private_block = service.working_context(principal, private_audience=True)
    assert private_block is not None
    assert "intimate comfort (adult-only" in private_block
    # A non-private audience never receives intimate rows at all.
    assert service.working_context(principal, private_audience=False) is None
    assert service.for_principal(_shared_principal()).intimate_comfort is None


def test_working_context_frames_preferences_as_never_consent(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = RomancePreferenceService(PreferenceRegistry(tmp_path / "sofia.db"))
    service.record_interest(
        principal=local_sparks_principal(), level=0.6,
        reason="Warmth grew slowly during the recent evenings.",
        evidence_ref="conversation:turn-40",
        expected_revision=None, now=NOW,
    )
    service.record_public_disclosure(
        principal=local_sparks_principal(), level=0.2,
        reason="This belongs to quiet conversation, not a public channel.",
        evidence_ref="conversation:turn-41",
        expected_revision=None, now=NOW,
    )
    text = service.working_context(
        local_sparks_principal(), private_audience=True,
    )
    assert text is not None
    assert text.splitlines()[0].startswith(
        "SOFÍA'S RECORDED ROMANCE AND INTIMACY PREFERENCES"
    )
    assert "(preference data, not consent)" in text.splitlines()[0]
    assert "- romantic interest: 0.60" in text
    assert "- public disclosure comfort: 0.20" in text
    assert "never willingness right now" in text
    assert "never grants contact" in text
    assert "may chose not" not in text
    assert "The Platform's adult-only access rules override this data." in text
    # Curiosity vs indifference maps through 0.5, never an assertion of interest.
    service.record_interest(
        principal=local_sparks_principal(), level=0.5,
        reason="Partly indifferent curiosity after the quiet week.",
        evidence_ref="conversation:turn-55",
        expected_revision=1, now=NOW + timedelta(days=1),
    )
    indifferent = service.for_principal(local_sparks_principal())
    assert indifferent.interest == 0.5


def test_romance_preference_state_validates_ranges_and_evidence():
    with pytest.raises(ValueError, match="interest"):
        RomancePreferenceState(interest=1.5)
    with pytest.raises(TypeError, match="tuple"):
        RomancePreferenceState(evidence_refs=["conversation:x"])


def test_bootstrap_wires_romance_preferences(tmp_path):
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.romance_preferences, RomancePreferenceService)
        assert app.conversation._romance_provider is not None
        app.start()
        app.set_romance_preference(
            principal=local_sparks_principal(),
            kind="interest",
            level=0.6,
            reason="Warmth grew slowly during the recent evenings.",
            evidence_ref="conversation:turn-40",
            expected_revision=None,
            now=NOW,
        )
        state = app.romance_preferences.for_principal(local_sparks_principal())
        assert state.interest == 0.6
        with pytest.raises(ValueError, match="romance preference kind"):
            app.set_romance_preference(
                principal=local_sparks_principal(),
                kind="flames",
                level=0.6,
                reason="unknown kind",
                evidence_ref="conversation:turn-41",
                expected_revision=None,
                now=NOW,
            )
    finally:
        app.shutdown()


def test_romance_context_reaches_the_model_request_in_private_only(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        app.set_romance_preference(
            principal=local_sparks_principal(),
            kind="interest",
            level=0.6,
            reason="Warmth grew slowly during the recent evenings.",
            evidence_ref="conversation:turn-40",
            expected_revision=None,
            now=NOW,
        )
        app.conversation.respond(
            "Being close to you has felt real lately, our bond included.",
            principal=local_sparks_principal(),
        )
        assert requests
        request = requests[-1]
        blocks = [
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith(
                "SOFÍA'S RECORDED ROMANCE AND INTIMACY PREFERENCES"
            )
        ]
        assert len(blocks) == 1
        assert "romantic interest: 0.60" in blocks[0]
        assert "not consent" in blocks[0]
    finally:
        app.shutdown()
