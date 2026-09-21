"""Supervised, synthetic A/B probe; does not open or modify Sofía's SQLite state.

Run: python -m sofia.interaction.ab_probe
A = short prompt grounded in the actual personality profile.
B = canonical STATIC cognitive assembler plus the relevant INTERACT instruction.
B is NOT the exact live session: no saved history, memory, emotional/reflection
journal, runtime continuity, filesystem changes, or tool execution is included.
Both variants use the configured Ollama model and generation settings.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.body_discussion import body_discussion_prompt
from sofia.interaction.expanded_service import action_prompt
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.chat import interaction_prompt
from sofia.personality.store import PersonalityStore
from sofia.self_model.model import create_core_state

_CASES = (
    ('ear', '*pats your ear*'),
    ('offer', 'I ask to hug you'),
    ('hypothetical', 'What happens if I pat your tail or rub your chest?'),
    ('technical', "I'm troubleshooting a Windows service that won't start. How would you diagnose it?"),
)


def build_pair(*, case: str, text: str, identity, personality,
               constitution, embodiment) -> tuple[CognitiveRequest, CognitiveRequest]:
    """Build isolated comparison requests; never load or initialize a state DB."""
    if case not in {item[0] for item in _CASES}:
        raise ValueError('Unreviewed A/B case.')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Nonempty synthetic input required.')
    user = CognitiveMessage(role=CognitiveRole.USER, content=text)
    minimal = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=(
            f'You are {personality.name}. Your identity and represented embodiment '
            'are fictional, not physical sensor data. Respond naturally in character; '
            'do not fabricate actions, prior interactions, feelings, or tool results. '
            'Use the personality profile rather than a generic assistant voice.\n'
            f'Traits: {", ".join(personality.traits)}\n'
            f'Communication style: {personality.communication_style}\n'
            f'Embodiment guidance: {personality.embodiment_guidance}'
        )), user,
    ))
    additions = ()
    if case == 'ear':
        decision = NaturalInteractionEngine(embodiment).from_text(
            content=text, message_id='synthetic-probe-ear',
            session_id='synthetic-probe-session', occurred_at=datetime.now(timezone.utc))
        # The original live phrase leaves the side unspecified. A canonical
        # clarification is valid; guessing a left/right ear or pretending a
        # completed gesture is not. Preserve the SAME user text in A and B.
        if decision is None or decision.status not in ('accepted', 'clarify'):
            raise RuntimeError('The canonical engine did not classify the synthetic ear gesture.')
        additions = (CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content=interaction_prompt(decision)),)
    elif case == 'offer':
        action = parse_user_action(text, message_id='synthetic-probe-offer')
        if action is None or action.modality != 'offered':
            raise RuntimeError('The canonical social-action parser rejected the synthetic offer.')
        additions = (CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content=action_prompt(action)),)
    elif case == 'hypothetical':
        instruction = body_discussion_prompt(
            content=text, engine=NaturalInteractionEngine(embodiment))
        if instruction is None:
            raise RuntimeError('The canonical hypothetical handler rejected the synthetic question.')
        additions = (CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content=instruction),)
    static = CognitiveContextAssembler().assemble(CognitiveContext(
        request=CognitiveRequest(messages=(*additions, user)),
        identity=identity, personality=personality, constitution=constitution,
        embodiment=embodiment,
        core_state=create_core_state(identity=identity, constitution=constitution),
    ))
    assert static.messages[-1].content == minimal.messages[-1].content == text
    return minimal, static


def main() -> int:
    configuration = create_default_configuration()
    if configuration.provider.provider != 'ollama':
        raise RuntimeError('This diagnostic supports the configured Ollama provider only.')
    constitution = ConstitutionStore(configuration.constitution_path).load()
    ConstitutionIntegrityVerifier(configuration.constitution_hash_path).verify(constitution)
    identity = IdentityStore(configuration.identity_path).load()
    personality = PersonalityStore(configuration.personality_path).load()
    embodiment = AvatarStore(configuration.avatar_path).load()
    provider = OllamaProvider(configuration.provider)
    print('INTERACT A/B: synthetic inputs only; SQLite and conversation history are untouched.')
    print('B is a static assembled approximation, NOT the exact live runtime prompt.')
    print(f'Model: {configuration.provider.model}; thinking: {configuration.provider.thinking}; '
          f'num_ctx: {configuration.provider.context_size}')
    for name, text in _CASES:
        baseline, assembled = build_pair(
            case=name, text=text, identity=identity, personality=personality,
            constitution=constitution, embodiment=embodiment)
        print(f'\nCASE {name}: {text}')
        for label, request in (('A minimal-profile', baseline), ('B assembled-static', assembled)):
            print(f'{label}: {len(request.messages)} messages; '
                  f'{sum(len(m.content) for m in request.messages)} prompt characters')
            response = provider.respond(request)
            print(f'{label} RESPONSE: {response.content}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
