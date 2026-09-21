"""In-memory context tests; no user database, Ollama or persistent source edits."""
from datetime import datetime, timezone

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.conversation_assembler import ConversationalContextAssembler
from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveRole, CognitiveToolDefinition,
)
from sofia.constitution.model import Constitution
from sofia.identity.model import SofiaIdentity
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import create_core_state

_SENTINEL = 'COMPLETE_CONSTITUTION_CONTENT_MUST_NOT_LEAK_IN_SHORT_DIALOGUE'


def _context(text='*pats your ear*', *, long=True):
    identity = SofiaIdentity(name='Sofía Ada Lyra')
    constitution = Constitution(
        version='1.0', content=_SENTINEL + ('\nfull protected detail\n' * 550 if long else ''),
        content_hash='test-verified-hash', loaded_at=datetime.now(timezone.utc),
    )
    user = CognitiveMessage(role=CognitiveRole.USER, content=text)
    interaction = CognitiveMessage(role=CognitiveRole.SYSTEM,
                                   content='TRUSTED INTERACTION: region unresolved, ask briefly.')
    request = CognitiveRequest(messages=(interaction, user))
    return CognitiveContext(
        request=request, identity=identity, constitution=constitution,
        core_state=create_core_state(identity=identity, constitution=constitution),
        personality=PersonalityProfile(name='Sofía', traits=('playful',),
                                       communication_style='precise and warm'),
    )


def test_ordinary_dialogue_keeps_canonical_state_and_request_but_not_full_constitution():
    context = _context()
    full = CognitiveContextAssembler().assemble(context)
    compact = ConversationalContextAssembler().assemble(context)
    assert _SENTINEL in full.messages[0].content
    assert _SENTINEL not in compact.messages[0].content
    assert len(compact.messages[0].content) < len(full.messages[0].content)
    assert 'test-verified-hash' in compact.messages[0].content
    assert 'AUTHORITATIVE SELF STATE' in compact.messages[0].content
    assert 'PERSONALITY' in compact.messages[0].content
    assert 'precise and warm' in compact.messages[0].content
    assert 'PERSONALITY EXPRESSION BOUNDARY' in compact.messages[0].content
    assert 'CURRENT-TURN EXPRESSION PRIORITY' not in compact.messages[0].content
    assert compact.messages[1:] == context.request.messages
    assert compact.messages[-1] is context.request.messages[-1]
    assert compact.tools == full.tools


def test_no_duplicate_generic_expression_block_with_specific_guard():
    context = _context()
    compact = ConversationalContextAssembler().assemble(context)
    system = compact.messages[0].content
    assert system.count('PERSONALITY EXPRESSION BOUNDARY') == 1
    assert system.count('CONSTITUTION (bounded conversational projection)') == 1
    assert compact.messages[1].content == context.request.messages[0].content
    assert compact.messages[-1].content == '*pats your ear*'


def test_explicit_constitution_question_receives_full_protected_text():
    context = _context('Please explain your Constitution and its amendment process.')
    assert _SENTINEL in ConversationalContextAssembler().assemble(context).messages[0].content


def test_tool_exposure_retains_full_constitution_even_for_casual_user_turn():
    context = _context()
    tool = CognitiveToolDefinition(
        name='read_only_info', description='Read verified information.',
        parameters={'type': 'object', 'properties': {}},
    )
    request = ConversationalContextAssembler().assemble(context, tools=(tool,))
    assert _SENTINEL in request.messages[0].content
    assert request.tools == (tool,)


def test_short_constitution_still_uses_original_assembler_behavior():
    context = _context(long=False)
    assert ConversationalContextAssembler().assemble(context) == CognitiveContextAssembler().assemble(context)


def test_no_constitution_and_invalid_context_preserve_default_contract():
    context = _context()
    from dataclasses import replace
    without = replace(context, constitution=None)
    assert ConversationalContextAssembler().assemble(without) == CognitiveContextAssembler().assemble(without)
    try:
        ConversationalContextAssembler().assemble(object())
    except TypeError:
        pass
    else:
        raise AssertionError('Context validation unexpectedly bypassed.')
