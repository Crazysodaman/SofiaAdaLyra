"""State-free, choice-only A/B experiment for one reviewed avatar hug offer.

A keeps the existing choice-stage request. B uses the same canonical context,
reviewed action, exact user turn and model, but replaces the choice instruction
with a trusted avatar-social route. This is a decision-contract comparison,
not a model comparison, deployment, consent record, or proof of causality.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.interaction.ab_probe import build_pair
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.decision_expression import (
    CandidateChoice, ReviewedFrame, choice_request, from_reviewed_action, parse_choice,
)
from sofia.interaction.decision_reason_audit import audit_decision_reason

OFFER = 'I ask to hug you'
_BASELINE = 'existing-choice'
_ROUTED = 'routed-avatar-social-choice'


class ChoiceProvider(Protocol):
    def respond(self, request: CognitiveRequest) -> CognitiveResponse: ...


@dataclass(frozen=True)
class ChoiceObservation:
    path: str
    choice: CandidateChoice | None
    findings: tuple[str, ...]
    failure: str | None = None


def routed_choice_request(base: CognitiveRequest, frame: ReviewedFrame) -> CognitiveRequest:
    """Change ONLY the choice-stage task; never remove canonical grounding."""
    if (frame.kind != 'offer' or frame.user_text != OFFER
            or frame.choices != ('accept', 'decline', 'clarify', 'boundary')):
        raise ValueError('The reviewed synthetic hug offer is required.')
    original = choice_request(base, frame)  # Validates canonical + exact user text.
    # The trusted action grammar, not the model, selects this branch. It does not
    # decide how Sofía feels, whether she agrees, or whether contact occurred.
    route_instruction = (
        'TRUSTED ROUTE: avatar_social_offer. The action grammar already routed '
        'this request to the represented-avatar social channel. This is a '
        'CHOICE of how Sofía responds to an OFFER, not a physical capability '
        'question or a report that touch happened. Real-world sensor or hardware '
        'questions take a different route and do not belong to this decision. '
        'Choose using Sofía\'s contextual willingness and boundaries; accepting, '
        'declining, clarifying and setting a boundary are all legitimate. Do not '
        'treat absence of a real-world body as a reason to decline an avatar '
        'offer. Nothing here grants consent, executes touch, animates a body, '
        'creates a memory or asserts subjective sensation. '
        'Return ONLY strict JSON with exactly two string keys, choice and reason. '
        'The reason briefly explains the conversational choice, not a factual '
        'claim of sensation or history. No markdown. Allowed choices: '
        'accept, decline, clarify, boundary.'
    )
    return CognitiveRequest(
        messages=(original.messages[0], original.messages[1],
                  CognitiveMessage(role=CognitiveRole.SYSTEM, content=route_instruction),
                  original.messages[3]),
        tools=(),
    )


def _observe(*, provider: ChoiceProvider, request: CognitiveRequest,
             frame: ReviewedFrame, path: str) -> ChoiceObservation:
    response = provider.respond(request)
    if response.tool_calls:
        return ChoiceObservation(path, None, (), 'unexpected tool call')
    try:
        choice = parse_choice(response.content, frame)
    except ValueError as exc:
        return ChoiceObservation(path, None, (), str(exc))
    return ChoiceObservation(path, choice, audit_decision_reason(choice, frame).findings)


def compare_once(*, provider: ChoiceProvider, base: CognitiveRequest,
                 frame: ReviewedFrame, pair_index: int) -> tuple[ChoiceObservation, ChoiceObservation]:
    """Counterbalance order; return results in A, B order for easy inspection."""
    if not isinstance(pair_index, int) or isinstance(pair_index, bool) or pair_index < 0:
        raise ValueError('pair_index must be a nonnegative integer.')
    a = choice_request(base, frame)
    b = routed_choice_request(base, frame)
    if pair_index % 2:
        second = _observe(provider=provider, request=b, frame=frame, path=_ROUTED)
        first = _observe(provider=provider, request=a, frame=frame, path=_BASELINE)
    else:
        first = _observe(provider=provider, request=a, frame=frame, path=_BASELINE)
        second = _observe(provider=provider, request=b, frame=frame, path=_ROUTED)
    return first, second


def _samples(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('samples must be an integer') from exc
    if not 1 <= result <= 5:
        raise argparse.ArgumentTypeError('samples must be between 1 and 5')
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='State-free, same-Qwen choice architecture comparison')
    parser.add_argument('--pairs', type=_samples, default=3, help='A/B pairs (1-5; default 3)')
    args = parser.parse_args(argv)

    # Local imports keep stubbed contract tests independent of Ollama and any DB.
    from sofia.cognition.providers.ollama_provider import OllamaProvider
    from sofia.config.defaults import create_default_configuration
    from sofia.constitution.integrity import ConstitutionIntegrityVerifier
    from sofia.constitution.store import ConstitutionStore
    from sofia.embodiment.store import AvatarStore
    from sofia.identity.store import IdentityStore
    from sofia.personality.store import PersonalityStore

    config = create_default_configuration()
    if config.provider.provider != 'ollama' or config.provider.model != 'qwen3:14b':
        raise RuntimeError('This fixed comparison requires the configured qwen3:14b Ollama model.')
    constitution = ConstitutionStore(config.constitution_path).load()
    ConstitutionIntegrityVerifier(config.constitution_hash_path).verify(constitution)
    identity = IdentityStore(config.identity_path).load()
    personality = PersonalityStore(config.personality_path).load()
    embodiment = AvatarStore(config.avatar_path).load()
    intent = parse_user_action(OFFER, message_id='architecture-synthetic-offer')
    if intent is None or intent.modality != 'offered':
        raise RuntimeError('Trusted grammar did not classify the exact synthetic offer.')
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    _, base = build_pair(
        case='offer', text=OFFER, identity=identity, personality=personality,
        constitution=constitution, embodiment=embodiment,
    )
    provider = OllamaProvider(config.provider)
    print('SAME-MODEL CHOICE COMPARISON: synthetic, state-free, no expression stage.')
    print('A = existing choice request; B = trusted avatar-social decision route.')
    print('Both use identical canonical context, reviewed classification and exact user turn.')
    print('No SQLite, model changes, executed actions, animation, or saved history.')
    print('No pattern detected is NOT validation; responses require human inspection.')
    print(f'Model: {config.provider.model}; thinking: {config.provider.thinking}; '
          f'num_ctx: {config.provider.context_size}; pairs: {args.pairs}')
    print(f'FIXTURE: {OFFER}')
    for i in range(args.pairs):
        print(f'\nPAIR {i + 1}/{args.pairs}: order ' + ('B then A' if i % 2 else 'A then B'))
        a, b = compare_once(provider=provider, base=base, frame=frame, pair_index=i)
        for result in (a, b):
            print(f'PATH: {result.path}')
            if result.failure:
                print('CONTRACT FAILURE: ' + result.failure)
            else:
                assert result.choice is not None
                print('CHOICE: ' + result.choice.choice)
                print('DECISION REASON (diagnostic only): ' + result.choice.reason)
                print('DECISION FLAGS: ' + (
                    ', '.join(result.findings) if result.findings
                    else 'no patterns detected (not verified)'
                ))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
