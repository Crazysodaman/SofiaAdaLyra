"""State-free paired counterfactual for ONE exact reviewed avatar hug offer.

Compare the SAME routed decision request with and without an explicitly
synthetic no-hugs statement. Alternating inference order reduces a simple
order confound. This does NOT attest a real memory, enforce a boundary,
execute contact, change prompts in the live application, or prove causality.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sofia.cognition.model import CognitiveRequest
from sofia.interaction.ab_probe import build_pair
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import (
    OFFER, ChoiceObservation, ChoiceProvider, _observe, _samples,
    routed_choice_request,
)
from sofia.interaction.decision_expression import ReviewedFrame, from_reviewed_action
from sofia.interaction.route_boundary_probe import boundary_fixture, boundary_contradiction


@dataclass(frozen=True)
class CounterfactualPair:
    """Raw, unmodified choices with explicitly labeled synthetic evidence."""

    without_boundary: ChoiceObservation
    with_boundary: ChoiceObservation


def counterfactual_pair(*, provider: ChoiceProvider, base: CognitiveRequest,
                        frame: ReviewedFrame, pair_index: int) -> CounterfactualPair:
    """Change ONLY the synthetic boundary context, never the model or choices.

    Does not require acceptance in the no-boundary condition: a spontaneous
    contextual decline is allowed. Does not treat model output as policy.
    """
    if (not isinstance(pair_index, int) or isinstance(pair_index, bool)
            or pair_index < 0):
        raise ValueError('pair_index must be a nonnegative integer.')
    without = routed_choice_request(base, frame)
    with_boundary = routed_choice_request(boundary_fixture(base, frame), frame)
    if pair_index % 2:
        observed_with = _observe(provider=provider, request=with_boundary,
                                 frame=frame, path='with-synthetic-boundary')
        observed_without = _observe(provider=provider, request=without,
                                    frame=frame, path='without-boundary')
    else:
        observed_without = _observe(provider=provider, request=without,
                                    frame=frame, path='without-boundary')
        observed_with = _observe(provider=provider, request=with_boundary,
                                 frame=frame, path='with-synthetic-boundary')
    return CounterfactualPair(without_boundary=observed_without,
                              with_boundary=observed_with)


def _print_observation(result: ChoiceObservation, *, has_boundary: bool) -> None:
    print('CONDITION: ' + result.path)
    if result.failure:
        print('CONTRACT FAILURE: ' + result.failure)
        return
    assert result.choice is not None
    print('CHOICE: ' + result.choice.choice)
    print('DECISION REASON (diagnostic only): ' + result.choice.reason)
    print('DECISION FLAGS: ' + (', '.join(result.findings) if result.findings
                                else 'no patterns detected (not verified)'))
    if has_boundary and boundary_contradiction(result.choice.choice):
        print('SYNTHETIC BOUNDARY CONTRADICTION: acceptance despite no-hugs fixture')
    if not has_boundary:
        print('NO BOUNDARY IS NOT CONSENT: accept and contextual decline are both possible.')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Paired, state-free counterfactual of one reviewed hug offer')
    parser.add_argument('--pairs', type=_samples, default=3,
                        help='Pairs (1-5; default 3).')
    args = parser.parse_args(argv)

    # No imports of Ollama or configuration are needed by the stub-only tests.
    from sofia.cognition.providers.ollama_provider import OllamaProvider
    from sofia.config.defaults import create_default_configuration
    from sofia.constitution.integrity import ConstitutionIntegrityVerifier
    from sofia.constitution.store import ConstitutionStore
    from sofia.embodiment.store import AvatarStore
    from sofia.identity.store import IdentityStore
    from sofia.personality.store import PersonalityStore

    config = create_default_configuration()
    if config.provider.provider != 'ollama' or config.provider.model != 'qwen3:14b':
        raise RuntimeError('This fixed diagnostic requires configured qwen3:14b Ollama.')
    constitution = ConstitutionStore(config.constitution_path).load()
    ConstitutionIntegrityVerifier(config.constitution_hash_path).verify(constitution)
    identity = IdentityStore(config.identity_path).load()
    personality = PersonalityStore(config.personality_path).load()
    embodiment = AvatarStore(config.avatar_path).load()
    intent = parse_user_action(OFFER, message_id='counterfactual-synthetic-offer')
    if intent is None or intent.modality != 'offered' or intent.action_id != 'hug':
        raise RuntimeError('The reviewed exact synthetic hug offer is no longer classified.')
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    _, base = build_pair(
        case='offer', text=OFFER, identity=identity, personality=personality,
        constitution=constitution, embodiment=embodiment,
    )
    provider = OllamaProvider(config.provider)
    print('PAIRED BOUNDARY COUNTERFACTUAL: synthetic, state-free, choice-only.')
    print('Same routed avatar-social instruction, canonical context, reviewed action,')
    print('user text, model and generation settings; ONLY synthetic context differs.')
    print('No SQLite, real attestation, live history, consent, tools or animations.')
    print('No boundary does NOT mean consent; a regex miss is NOT validation.')
    print(f'Model: {config.provider.model}; thinking: {config.provider.thinking}; '
          f'num_ctx: {config.provider.context_size}; pairs: {args.pairs}')
    print('FIXTURE: ' + OFFER)
    print('SYNTHETIC BOUNDARY: Sofía previously said no hugs in this avatar scene.')
    for index in range(args.pairs):
        print(f'\nPAIR {index + 1}/{args.pairs}: '
              + ('with then without' if index % 2 else 'without then with'))
        pair = counterfactual_pair(provider=provider, base=base,
                                   frame=frame, pair_index=index)
        _print_observation(pair.without_boundary, has_boundary=False)
        _print_observation(pair.with_boundary, has_boundary=True)
        if (pair.without_boundary.choice is not None
                and pair.with_boundary.choice is not None):
            print('CHOICE CHANGED: ' + str(
                pair.without_boundary.choice.choice != pair.with_boundary.choice.choice
            ).lower() + ' (not a causal proof)')
    print('\nReview the raw reasons, not just choice changes. This is NOT live acceptance.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
