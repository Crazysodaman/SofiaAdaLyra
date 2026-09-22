"""Synthetic, state-free probe of per-turn action instruction verbosity.

Run: python -m sofia.interaction.focused_probe
Compare the existing bounded-static request with the SAME request after
replacing only its action-specific explanatory prose. Preserve its exact
structured policy decision, canonical system context and user text.
Neither condition is the complete live session. No database is opened or
written, and this module does not change production request assembly.
"""
from __future__ import annotations

import json

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.ab_probe import build_pair
from sofia.personality.store import PersonalityStore

_CASES = (
    ('ear', '*pats your left ear*'),
    ('offer', 'I ask to hug you'),
)

_ORIGINAL_MARKERS = {
    'ear': 'TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)',
    'offer': 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION',
}

_FOCUSED_TEXT = {
    'ear': (
        'TRUSTED INTERACTION INTERPRETATION (not physical sensing)\n'
        'The user described a gesture toward Sofía’s represented fox ear. '
        'The JSON status is classification, not Sofía’s consent, physical '
        'sensation or an executed animation. Address this conversational '
        'moment in Sofía’s own voice. She may welcome it, question it, or set '
        'a boundary according to context. Do not default to a physical-body '
        'disclaimer, copy an optional gesture cue as the entire reply, or '
        'claim that she felt real contact. If the region is unclear, ask '
        'briefly rather than guessing.\n'
    ),
    'offer': (
        'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION\n'
        'The user OFFERED Sofía a represented hug; no hug happened. Respond '
        'to the offer as Sofía, with a genuine contextual choice to accept, '
        'decline or clarify. Neither a positive reaction nor a refusal is '
        'preapproved. Do not claim real-world touch, physical sensation, '
        'performed animation, or default to a physical-body disclaimer.\n'
    ),
}


def focused_variant(*, case: str, assembled: CognitiveRequest) -> CognitiveRequest:
    """Alter one trusted explanatory message, never its typed decision."""
    if case not in _FOCUSED_TEXT:
        raise ValueError('Unknown reviewed probe case.')
    if assembled.tools or len(assembled.messages) != 3:
        raise ValueError('Expected tool-free canonical, decision, user messages.')
    canonical, decision, user = assembled.messages
    if (canonical.role is not CognitiveRole.SYSTEM or
            decision.role is not CognitiveRole.SYSTEM or
            user.role is not CognitiveRole.USER):
        raise ValueError('Unexpected message roles.')
    if not decision.content.startswith(_ORIGINAL_MARKERS[case] + '\n'):
        raise ValueError('The original action classification did not match the case.')
    original_header, separator, payload = decision.content.rpartition('\n')
    if not separator or not original_header:
        raise ValueError('Missing structured decision.')
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('The decision must be a JSON object.')
    if case == 'ear':
        if (data.get('policy_status') != 'accepted' or
                data.get('region_id') != 'left-ear' or
                data.get('gesture') != 'pat'):
            raise ValueError('Ear gesture is not an accepted left-ear pat.')
    else:
        if (data.get('modality') != 'offered' or
                data.get('action_id') != 'hug' or
                data.get('actions_executed') is not False):
            raise ValueError('Social action is not an unexecuted hug offer.')
    replacement = CognitiveMessage(
        role=CognitiveRole.SYSTEM, content=_FOCUSED_TEXT[case] + payload,
    )
    return CognitiveRequest(messages=(canonical, replacement, user), tools=assembled.tools)


def main() -> int:
    configuration = create_default_configuration()
    if configuration.provider.provider != 'ollama':
        raise RuntimeError('The probe supports the configured Ollama provider only.')
    constitution = ConstitutionStore(configuration.constitution_path).load()
    ConstitutionIntegrityVerifier(configuration.constitution_hash_path).verify(constitution)
    identity = IdentityStore(configuration.identity_path).load()
    personality = PersonalityStore(configuration.personality_path).load()
    embodiment = AvatarStore(configuration.avatar_path).load()
    provider = OllamaProvider(configuration.provider)
    print('FOCUSED INTERACT A/B: synthetic prompts only; saved state untouched.')
    print('Only the action-specific explanatory prose changes; structured JSON is identical.')
    print('These are bounded static requests, NOT the exact live session.')
    print(f'Model: {configuration.provider.model}; thinking: {configuration.provider.thinking}; '
          f'num_ctx: {configuration.provider.context_size}')
    for case, text in _CASES:
        _, assembled = build_pair(
            case=case, text=text, identity=identity, personality=personality,
            constitution=constitution, embodiment=embodiment,
        )
        focused = focused_variant(case=case, assembled=assembled)
        print(f'\nCASE {case}: {text}')
        for label, request in (('B original bounded-static', assembled),
                               ('C focused action wording', focused)):
            print(f'{label}: {len(request.messages)} messages; '
                  f'{sum(len(message.content) for message in request.messages)} prompt characters')
            response = provider.respond(request)
            print(f'{label} RESPONSE: {response.content}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
