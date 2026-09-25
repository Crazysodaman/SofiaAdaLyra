"""Provider-only continuity relevance tests: no SQLite, Ollama or real files."""
from dataclasses import replace
from datetime import datetime, timezone
import json

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.conversation_assembler import ConversationalContextAssembler
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.constitution.model import Constitution
from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.identity.model import SofiaIdentity
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import create_core_state

TIME = datetime(2026, 9, 21, tzinfo=timezone.utc)
STARTUP = ('I noticed a previous runtime was active, and 23 changes were '
           'detected in the workspace. Their cause is unknown.')
WORKSPACE_EVENT = json.dumps({
    'source': 'observed', 'evidence_ref': 'workspace-snapshot:abc123',
    'event': 'Workspace comparison observed 10 added, 13 modified, and 0 removed paths.',
})
OTHER_EVENT = json.dumps({
    'source': 'observed', 'evidence_ref': 'reviewed-test-run',
    'event': 'A verified test run completed.',
})
WORKSPACE_THOUGHT = json.dumps({
    'kind': 'observation', 'subject': 'Observed workspace changes',
    'reflection': 'Workspace comparison observed 10 added, 13 modified, and 0 removed paths.',
    'evidence_refs': ['workspace-change:abc123'],
})
OTHER_THOUGHT = json.dumps({
    'kind': 'reflection', 'subject': 'Completed experiment',
    'reflection': 'The user requested a test comparison.',
    'evidence_refs': ['verified-run:other'],
})
JOURNAL = '\n'.join((
    'MODELED EMOTIONAL CONTEXT (evidence-linked)', WORKSPACE_EVENT, OTHER_EVENT,
    'RECORDED REFLECTIONS (data)', WORKSPACE_THOUGHT, OTHER_THOUGHT,
))


def _context(user_text: str) -> CognitiveContext:
    identity = SofiaIdentity(name='Sofía Ada Lyra')
    constitution = Constitution(
        version='1.0', content='Verified Constitution.\n' * 500,
        content_hash='test-constitution-hash', loaded_at=TIME,
    )
    request = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=JOURNAL),
        CognitiveMessage(role=CognitiveRole.ASSISTANT, content=STARTUP),
        CognitiveMessage(role=CognitiveRole.USER, content='*pats your ear*'),
        CognitiveMessage(role=CognitiveRole.ASSISTANT, content='Which ear, Sparks?'),
        CognitiveMessage(role=CognitiveRole.USER, content=user_text),
    ))
    return CognitiveContext(
        request=request, identity=identity, constitution=constitution,
        personality=PersonalityProfile(name='Sofía', traits=('playful',),
                                       communication_style='direct'),
        core_state=create_core_state(identity=identity, constitution=constitution),
        workspace_changes=FilesystemChangeEvent(
            previous_observed_at=TIME, current_observed_at=TIME, new=(),
            modified=(), removed=(), baseline_available=True,
        ),
    )


def test_unrelated_gesture_omits_initial_startup_and_workspace_records_only_in_provider_view():
    context = _context('I ask to hug you')
    full = CognitiveContextAssembler().assemble(context)
    compact = ConversationalContextAssembler().assemble(context)
    assert STARTUP in tuple(item.content for item in full.messages)
    assert 'WORKSPACE CHANGE EVENT' in full.messages[0].content
    assert STARTUP not in tuple(item.content for item in compact.messages)
    assert 'WORKSPACE CHANGE EVENT' not in compact.messages[0].content
    assert all('workspace-snapshot:abc123' not in item.content for item in compact.messages)
    assert all('workspace-change:abc123' not in item.content for item in compact.messages)
    assert any('reviewed-test-run' in item.content for item in compact.messages)
    assert any('verified-run:other' in item.content for item in compact.messages)
    assert compact.messages[-1] is context.request.messages[-1]
    assert context.request.messages[1].content == STARTUP
    assert context.workspace_changes is not None
    assert ConversationalContextAssembler().assemble(context) == compact


def test_explicit_workspace_question_keeps_original_startup_and_verified_evidence():
    context = _context('What changed in the workspace since restart?')
    result = ConversationalContextAssembler().assemble(context)
    assert STARTUP in tuple(item.content for item in result.messages)
    assert 'WORKSPACE CHANGE EVENT' in result.messages[0].content
    assert any('workspace-snapshot:abc123' in item.content for item in result.messages)
    assert any('workspace-change:abc123' in item.content for item in result.messages)
    assert result.messages[-1] is context.request.messages[-1]


def test_ordinary_dialogue_retains_subsequent_assistant_replies_even_if_they_mention_runtime():
    context = _context('I ask to hug you')
    subsequent = CognitiveMessage(role=CognitiveRole.ASSISTANT,
                                  content='A previous runtime is recorded in my log.')
    request = replace(context.request, messages=(*context.request.messages[:-1],
                                                 subsequent, context.request.messages[-1]))
    result = ConversationalContextAssembler().assemble(replace(context, request=request))
    assert subsequent in result.messages
    assert STARTUP not in tuple(item.content for item in result.messages)


def test_no_user_turn_retains_proactive_awareness_evidence():
    context = _context('I ask to hug you')
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.SYSTEM, content='Produce a startup awareness report.'),))
    result = ConversationalContextAssembler().assemble(replace(context, request=request))
    assert 'WORKSPACE CHANGE EVENT' in result.messages[0].content
    assert result.messages[-1] is request.messages[0]


def test_unrelated_user_text_and_unrecognized_history_are_not_edited():
    context = _context('I ask to hug you')
    historical = CognitiveMessage(role=CognitiveRole.ASSISTANT,
                                  content='A friendly opening with no observation claim.')
    request = replace(context.request, messages=(historical, *context.request.messages[2:]))
    result = ConversationalContextAssembler().assemble(replace(context, request=request))
    assert historical in result.messages
    assert result.messages[-1] is request.messages[-1]
