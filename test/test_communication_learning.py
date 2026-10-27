"""B05: owner-taught shorthand interpretation store, service and wiring."""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.core.communication import (
    CommunicationLearningService,
    ShorthandConcurrencyError,
    ShorthandRecord,
    ShorthandStatus,
    ShorthandStore,
)
from sofia.core.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import (
    local_sparks_principal,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 5, 20, 9, 30, tzinfo=timezone.utc)

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


def taught_record(
    token: str,
    expansion: str,
    *,
    audience: str = "local:text",
    evidence: str = "conversation:msg-1",
    revision: int = 1,
    status: ShorthandStatus = ShorthandStatus.ACTIVE,
):
    return ShorthandRecord(
        token=token,
        principal_id="person:sparks",
        audience_id=audience,
        expansion=expansion,
        note=None,
        evidence_ref=evidence,
        status=status,
        revision=revision,
        recorded_at=NOW,
    )


def test_store_holds_appends_and_rejects_races(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ShorthandStore(tmp_path / "sofia.db")
    store.hold(taught_record("ppl", "people"), expected_revision=None)
    current = store.current("ppl", principal_id="person:sparks", audience_id="local:text")
    assert current is not None and current.expansion == "people"
    store.hold(
        taught_record("ppl", "people / relatives", revision=2), expected_revision=1,
    )
    assert [
        record.revision for record in store.history(
            "ppl", principal_id="person:sparks", audience_id="local:text",
        )
    ] == [1, 2]
    with pytest.raises(ShorthandConcurrencyError, match="already exists"):
        store.hold(taught_record("ppl", "dup"), expected_revision=None)
    with pytest.raises(ShorthandConcurrencyError, match="already exists"):
        store.hold(taught_record("ppl", "stale"), expected_revision=None)
    with pytest.raises(ShorthandConcurrencyError, match="revision changed"):
        store.hold(
            taught_record("ppl", "stale", revision=2), expected_revision=9,
        )


def test_store_validates_tokens_scopes_and_integrity(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ShorthandStore(tmp_path / "sofia.db")
    with pytest.raises(ValueError, match="token"):
        store.hold(taught_record("PPL", "people"), expected_revision=None)
    with pytest.raises(ValueError, match="expansion"):
        store.hold(taught_record("ppl", " "), expected_revision=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        ShorthandRecord(
            token=taught_record("ppl", "people").token,
            principal_id=taught_record("ppl", "people").principal_id,
            audience_id=taught_record("ppl", "people").audience_id,
            expansion="people", note=None,
            evidence_ref="evidence:revision",
            status=ShorthandStatus.ACTIVE, revision=1,
            recorded_at=NOW.replace(tzinfo=None),
        )
    # One audience cannot read another audience's taught mapping.
    store.hold(taught_record("ppl", "people"), expected_revision=None)
    assert store.current(
        "ppl", principal_id="person:sparks", audience_id="discord:dm:1",
    ) is None
    assert tuple(store.interpretations(
        ("ppl",), principal_id="other:someone", audience_id="local:text",
    )) == ()
    with pytest.raises(ValueError, match="limit"):
        store.taught(
            principal_id="person:sparks", audience_id="local:text", limit=257,
        )


def test_interpretations_are_whole_word_and_withdrawable(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ShorthandStore(tmp_path / "sofia.db")
    store.hold(taught_record("ppl", "people"), expected_revision=None)
    matches = tuple(store.interpretations(
        ("ppl", "hello", "supply"),  # "supply" contains "ppl" as a substring
        principal_id="person:sparks", audience_id="local:text",
    ))
    assert tuple(match.token for match in matches) == ("ppl",)
    unknown = tuple(store.interpretations(
        ("wrld",), principal_id="person:sparks", audience_id="local:text",
    ))
    assert unknown == ()
    store.hold(
        taught_record("ppl", "people", revision=2, status=ShorthandStatus.WITHDRAWN),
        expected_revision=1,
    )
    assert tuple(store.interpretations(
        ("ppl",), principal_id="person:sparks", audience_id="local:text",
    )) == ()
    # Only ACTIVE mappings appear in the current listing.
    assert store.taught(
        principal_id="person:sparks", audience_id="local:text",
    ) == ()
    assert [
        record.status for record in store.history(
            "ppl", principal_id="person:sparks", audience_id="local:text",
        )
    ] == [ShorthandStatus.ACTIVE, ShorthandStatus.WITHDRAWN]


def test_service_is_owner_gated_and_interprets_only_authenticated_scope(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ShorthandStore(tmp_path / "sofia.db")
    service = CommunicationLearningService(store)
    with pytest.raises(TypeError):
        service.teach(
            principal=object(),
            token="ppl", expansion="people", evidence_ref="conversation:m1",
            now=NOW,
        )
    with pytest.raises(PermissionError):
        service.teach(
            principal=PrincipalContext(
                "person:other", "local:text", AudienceKind.PRIVATE, "Other",
            ),
            token="ppl", expansion="people", evidence_ref="conversation:m1",
            now=NOW,
        )
    record = service.teach(
        principal=local_sparks_principal(),
        token="ppl", expansion="people", evidence_ref="conversation:m1",
        now=NOW,
    )
    assert record.status is ShorthandStatus.ACTIVE
    matches = service.interpret(
        principal=local_sparks_principal(), text="The ppl arrived.",
    )
    assert tuple(match.expansion for match in matches) == ("people",)
    # A non-owner principal gets no readings of owner-taught shorthand.
    assert tuple(service.interpret(
        principal=local_sparks_principal(audience_id="discord:dm:7"),
        text="The ppl arrived.",
    )) == ()
    withdrawn = service.withdraw(
        principal=local_sparks_principal(),
        token="ppl", evidence_ref="conversation:m2", expected_revision=record.revision,
        now=NOW + timedelta(days=1),
    )
    assert withdrawn.status is ShorthandStatus.WITHDRAWN
    with pytest.raises(LookupError):
        service.withdraw(
            principal=local_sparks_principal(),
            token="ppl", evidence_ref="conversation:m3",
            expected_revision=withdrawn.revision,
            now=NOW + timedelta(days=2),
        )
    # Teaching survives a restart and never resurfaces a withdrawn token.
    reopened = CommunicationLearningService(ShorthandStore(tmp_path / "sofia.db"))
    assert [
        record.status for record in reopened.taught(
            principal=local_sparks_principal(),
        )
    ] == []
    assert tuple(reopened.interpret(
        principal=local_sparks_principal(), text="The ppl arrived.",
    )) == ()
    # After withdrawal a retaught mapping applies from a new revision.
    retaught = reopened.taught(principal=local_sparks_principal())
    assert retaught == ()


def test_unicode_whole_words_and_unsupported_tokens_never_reach_store(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = CommunicationLearningService(ShorthandStore(tmp_path / "sofia.db"))
    for token, expansion in (
        ("ppl", "people"), ("brb", "be right back"),
        ("can't", "cannot"), ("check-in", "status check"),
    ):
        service.teach(
            principal=local_sparks_principal(), token=token,
            expansion=expansion, evidence_ref=f"conversation:{token}", now=NOW,
        )

    cases = (
        ("Sofía, I told the ppl.", ("ppl",)),
        ("BRB—Sofía!", ("brb",)),
        ("I can't; check-in later.", ("can't", "check-in")),
        ("x — a — punctuation... unknown", ()),
        ("a" * 41 + " ppl", ("ppl",)),
        ("¿Sofía habla español? l’été, ppl", ("ppl",)),
    )
    for text, expected in cases:
        matches = service.interpret(
            principal=local_sparks_principal(), text=text,
        )
        assert tuple(match.token for match in matches) == expected


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


def test_bootstrap_wires_shorthand_learning(tmp_path: Path) -> None:
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.communication_learning, CommunicationLearningService)
        assert app.conversation._interpretation_provider is not None
        app.start()
    finally:
        app.shutdown()


def test_taught_shorthand_reaches_the_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        no_text_messages = []
        app.conversation.respond(
            "Ping the fleet later.",
            principal=local_sparks_principal(),
        )
        assert requests, "the turn must still reach the model request"
        request = requests[-1]
        no_text_messages = [
            message for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("LEARNED OWNER SHORTHAND")
        ]
        assert no_text_messages == []
        app.communication_learning.teach(
            principal=local_sparks_principal(),
            token="ppl", expansion="people",
            evidence_ref="conversation:m1", now=NOW,
        )
        app.conversation.respond(
            "Ppl ping the fleet later.",
            principal=local_sparks_principal(),
        )
        assert len(requests) == 2
        request = requests[-1]
        blocks = [
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("LEARNED OWNER SHORTHAND")
        ]
        assert len(blocks) == 1
        assert "ppl => people" in blocks[0]
        assert "never commands" in blocks[0]
    finally:
        app.shutdown()


def test_unicode_conversation_preserves_original_text_without_projection_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    original = "Sofía, I can't check-in about el ferrocarril—¿verdad?"
    app.start()
    try:
        response = app.conversation.respond(
            original, principal=local_sparks_principal(),
        )
        assert response.content == "Captured."
        assert len(requests) == 1
        assert any(
            message.role is CognitiveRole.USER and message.content == original
            for message in requests[0].messages
        )
    finally:
        app.shutdown()
