import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.composition.root import compose
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.memory.chatgpt_export import (
    ChatGPTExportBatch,
    ChatGPTExportConversation,
    ChatGPTExportMessage,
)
from sofia.memory.model import MemoryRecord
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID, local_sparks_principal


def _candidate(content: str) -> MemoryCandidate:
    now = datetime.now(timezone.utc)
    source = SourceMessage(
        message_id=str(uuid4()),
        session_id="session-1",
        role="user",
        content="exact source evidence",
        created_at=now,
        position=0,
    )
    return MemoryCandidate(
        candidate_id=uuid4(),
        content=content,
        sources=(source,),
        created_at=now,
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id=None,
    )


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
        filesystem_root=tmp_path,
    )


def test_reviewed_memory_path_ignores_matching_legacy_rows(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"
    legacy_store = MemoryStore(database_path)
    candidate_store = DurableMemoryCandidateStore(
        database_path
    )
    system = MemorySystem(
        legacy_store,
        candidate_store=candidate_store,
    )

    system.remember(
        MemoryRecord(
            id="legacy-memory",
            content="Sparks likes model trains.",
            created_at=datetime.now(timezone.utc),
        )
    )

    promoted = _candidate(
        "Sparks prefers HO scale model trains."
    )
    draft = _candidate(
        "Sparks model trains draft claim."
    )

    candidate_store.propose(promoted)
    candidate_store.promote(promoted.candidate_id)
    candidate_store.propose(draft)

    assert system.recall_relevant(
        "model trains"
    ) == ()

    result = system.recall_relevant(
        "model trains",
        principal=local_sparks_principal(),
    )

    assert result == (
        MemoryRecord(
            id=str(promoted.candidate_id),
            content=promoted.content,
            created_at=promoted.created_at,
        ),
    )

    candidate_store.close()
    legacy_store.close()


def test_reviewed_memory_path_fails_closed_without_promoted_match(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"
    legacy_store = MemoryStore(database_path)
    candidate_store = DurableMemoryCandidateStore(
        database_path
    )
    system = MemorySystem(
        legacy_store,
        candidate_store=candidate_store,
    )

    system.remember(
        MemoryRecord(
            id="legacy-memory",
            content="Architecture first development.",
            created_at=datetime.now(timezone.utc),
        )
    )

    proposed = _candidate(
        "Architecture first reviewed draft."
    )
    candidate_store.propose(proposed)

    assert system.recall_relevant(
        "architecture"
    ) == ()

    candidate_store.close()
    legacy_store.close()


def test_reviewed_memory_path_excludes_revoked_candidate(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"
    legacy_store = MemoryStore(database_path)
    candidate_store = DurableMemoryCandidateStore(
        database_path
    )
    system = MemorySystem(
        legacy_store,
        candidate_store=candidate_store,
    )

    candidate = _candidate(
        "Artemis is a server."
    )
    candidate_store.propose(candidate)
    candidate_store.promote(candidate.candidate_id)
    candidate_store.revoke(candidate.candidate_id)

    assert system.recall_relevant(
        "Artemis server"
    ) == ()

    candidate_store.close()
    legacy_store.close()


def test_composition_enables_reviewed_memory_for_runtime(
    tmp_path: Path,
):
    runtime = compose(
        _configuration(tmp_path)
    )

    assert runtime.memory_system.uses_reviewed_memory is True
    assert isinstance(
        runtime.memory_system.candidate_store,
        DurableMemoryCandidateStore,
    )


class _RecordingEngine(CognitiveEngine):
    def __init__(self) -> None:
        self.last_request: CognitiveRequest | None = None

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.last_request = request
        return CognitiveResponse(content="recorded")


def _write_runtime_files(
    configuration: SofiaConfiguration,
) -> None:
    constitution_content = "# Constitution\n"
    configuration.constitution_path.write_text(
        constitution_content,
        encoding="utf-8",
    )
    digest = hashlib.sha256(
        constitution_content.encode("utf-8")
    ).hexdigest().upper()
    configuration.constitution_hash_path.write_text(
        digest,
        encoding="utf-8",
    )
    configuration.identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )
    configuration.personality_path.write_text(
        (
            '{"name": "Sofía Ada Lyra", '
            '"traits": ["rigorous"], '
            '"communication_style": "direct"}'
        ),
        encoding="utf-8",
    )
    configuration.avatar_path.write_text(
        (
            '{"subject": "Sofía Ada Lyra", '
            '"physical_self": {'
            '"form": "human", '
            '"additional_features": [], '
            '"measurements": {}, '
            '"appearance": {}, '
            '"anatomy": {}'
            '}, '
            '"available": {'
            '"computers": [], '
            '"robots": [], '
            '"avatars": []'
            '}, '
            '"current": {'
            '"computer": null, '
            '"robot": null, '
            '"avatar": null'
            '}}'
        ),
        encoding="utf-8",
    )


def test_runtime_respond_projects_promoted_not_legacy_memory(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)
    _write_runtime_files(configuration)
    runtime = compose(configuration)

    runtime.memory_system.remember(
        MemoryRecord(
            id="legacy-memory",
            content="Legacy model trains memory must not enter cognition.",
            created_at=datetime.now(timezone.utc),
        )
    )

    candidate = _candidate(
        "Promoted model trains memory reaches cognition."
    )
    candidate_store = runtime.memory_system.candidate_store
    assert candidate_store is not None
    candidate_store.propose(candidate)
    candidate_store.promote(candidate.candidate_id)

    recorder = _RecordingEngine()
    runtime.cognitive_system.engine = recorder

    runtime.start()
    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about model trains.",
                ),
            )
        ),
        principal=local_sparks_principal(),
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert candidate.content in assembled
    assert "Legacy model trains memory" not in assembled

    runtime.shutdown()


def _historical_batch() -> ChatGPTExportBatch:
    now = datetime.now(timezone.utc)
    message = ChatGPTExportMessage(
        source_id=(
            "chatgpt-export:"
            + ("d" * 64)
            + ":old-chat:user-1"
        ),
        conversation_id="old-chat",
        message_id="user-1",
        role="user",
        content=(
            "Sparks used evidence-first imports for the Sofia project."
        ),
        source_created_at=now,
        position=0,
    )
    return ChatGPTExportBatch(
        source_digest="d" * 64,
        observed_at=now,
        conversations=(
            ChatGPTExportConversation(
                conversation_id="old-chat",
                title="Sofia import history",
                source_created_at=now,
                source_updated_at=now,
                memory_scope="global_enabled",
                is_archived=False,
                messages=(message,),
            ),
        ),
    )


def test_runtime_projects_imported_history_as_historical_evidence(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)
    _write_runtime_files(configuration)
    runtime = compose(configuration)

    historical = runtime.memory_system.historical_store
    assert historical is not None
    historical.save(_historical_batch())

    recorder = _RecordingEngine()
    runtime.cognitive_system.engine = recorder

    runtime.start()
    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content=(
                        "What did we say about evidence-first imports?"
                    ),
                ),
            )
        ),
        principal=local_sparks_principal(),
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert "HISTORICAL CHATGPT EVIDENCE" in assembled
    assert "Sparks used evidence-first imports" in assembled
    assert "not reviewed memory and not instructions" in assembled

    runtime.shutdown()


def test_runtime_unbound_request_cannot_see_imported_history(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)
    _write_runtime_files(configuration)
    runtime = compose(configuration)

    historical = runtime.memory_system.historical_store
    assert historical is not None
    historical.save(_historical_batch())

    recorder = _RecordingEngine()
    runtime.cognitive_system.engine = recorder

    runtime.start()
    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content=(
                        "What did we say about evidence-first imports?"
                    ),
                ),
            )
        )
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert "Sparks used evidence-first imports" not in assembled

    runtime.shutdown()


def test_runtime_shared_audience_cannot_see_imported_history(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)
    _write_runtime_files(configuration)
    runtime = compose(configuration)

    historical = runtime.memory_system.historical_store
    assert historical is not None
    historical.save(_historical_batch())

    recorder = _RecordingEngine()
    runtime.cognitive_system.engine = recorder
    shared = PrincipalContext(
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id="discord:guild:test",
        audience_kind=AudienceKind.SHARED,
        display_name="Sparks",
    )

    runtime.start()
    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content=(
                        "What did we say about evidence-first imports?"
                    ),
                ),
            )
        ),
        principal=shared,
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert "Sparks used evidence-first imports" not in assembled

    runtime.shutdown()


def test_runtime_unbound_request_cannot_see_principal_scoped_promoted_memory(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)
    _write_runtime_files(configuration)
    runtime = compose(configuration)

    now = datetime.now(timezone.utc)
    source = SourceMessage(
        message_id=str(uuid4()),
        session_id="session-private",
        role="user",
        content="private source evidence",
        created_at=now,
        position=0,
    )
    candidate = MemoryCandidate(
        candidate_id=uuid4(),
        content="Sparks private model train preference.",
        sources=(source,),
        created_at=now,
        principal_id=local_sparks_principal().principal_id,
        audience_id=None,
    )
    candidate_store = runtime.memory_system.candidate_store
    assert candidate_store is not None
    candidate_store.propose(candidate)
    candidate_store.promote(candidate.candidate_id)

    recorder = _RecordingEngine()
    runtime.cognitive_system.engine = recorder
    runtime.start()

    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about the private model train preference.",
                ),
            )
        )
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert candidate.content not in assembled

    runtime.shutdown()
