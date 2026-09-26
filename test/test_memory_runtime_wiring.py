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
from sofia.memory.model import MemoryRecord
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem


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

    result = system.recall_relevant(
        "model trains"
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
        )
    )

    assert recorder.last_request is not None
    assembled = "\n".join(
        message.content
        for message in recorder.last_request.messages
    )
    assert candidate.content in assembled
    assert "Legacy model trains memory" not in assembled

    runtime.shutdown()
