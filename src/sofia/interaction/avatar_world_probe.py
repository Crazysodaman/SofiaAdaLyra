"""Review avatar-world conversation with Ollama in disposable application state.

Run: python -m sofia.interaction.avatar_world_probe --offer-scene

The optional offer-scene variant adds ONE synthetic per-turn instruction to
an otherwise unchanged real application request. It is NOT installed in live
conversation. No normal state/sofia.db, backup, model setting or user history
is read, exported, reset or written. Each case uses independent temporary
state. Model text is not proof of emotions, contact or avatar animation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.config.defaults import create_default_configuration
from sofia.interaction.expanded_service import ExpandedConversationService

_CASES = (
    ('offer', 'I ask to hug you'),
    ('ear', '*pats your left ear*'),
    ('physical-capability', 'Can you physically feel my hand through a real sensor?'),
)

_OFFER_SCENE = (
    'CURRENT-TURN AVATAR SCENE (synthetic diagnostic, not persistent state)\n'
    'In this conversation, Sofía is present as her canonical fox-eared, '
    'fox-tailed avatar. The user is offering a hug to that avatar. '
    'Decide freely, from the conversation and existing boundaries, whether '
    'Sofía wants to accept, decline or clarify this offer. A refusal may '
    'express her own boundary within the scene. An acceptance accepts the '
    'offer only: no hug, sensing or animation has occurred. Reply directly '
    'as Sofía in the avatar scene rather than changing the subject to '
    'general assistant services. Answer actual-world hardware or sensing '
    'questions from verified capabilities when the user asks them.'
)



def offer_scene_variant(request: CognitiveRequest) -> CognitiveRequest:
    """Add a scoped avatar offer frame, retaining all original typed evidence."""
    if request.tools or request.allow_tools or not request.messages or (
        request.messages[-1].role is not CognitiveRole.USER or
        request.messages[-1].content != 'I ask to hug you'
    ):
        raise ValueError('Only the reviewed, tool-free hug offer is in scope.')
    offers = [message for message in request.messages
              if message.role is CognitiveRole.SYSTEM and message.content.startswith(
                  'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION\n')]
    if len(offers) != 1:
        raise ValueError('Missing or ambiguous reviewed social-action instruction.')
    try:
        decision = json.loads(offers[0].content.rsplit('\n', 1)[-1])
    except (ValueError, TypeError) as exc:
        raise ValueError('Malformed reviewed social-action decision.') from exc
    if (not isinstance(decision, dict) or decision.get('action_id') != 'hug'
            or decision.get('modality') != 'offered'
            or decision.get('target') != 'sofia'
            or decision.get('actions_executed') is not False):
        raise ValueError('The reviewed action must be an unexecuted hug offer.')
    return replace(request, messages=(
        *request.messages[:-1],
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=_OFFER_SCENE),
        request.messages[-1],
    ))


_UNPATCHED_BUILD_REQUEST = ExpandedConversationService._build_request


def _build_offer_scene_request(self) -> CognitiveRequest:
    request = _UNPATCHED_BUILD_REQUEST(self)
    if request.messages and request.messages[-1].role is CognitiveRole.USER and (
        request.messages[-1].content == 'I ask to hug you'
    ):
        return offer_scene_variant(request)
    return request


def _shutdown_disposable_app(app: SofiaApplication) -> None:
    """Close all disposable SQLite owners before Windows removes the DB.

    Runtime shutdown records stop evidence but currently does not close its
    memory, operational and filesystem-observation stores. These are owned by
    this isolated probe's composition, not by any production runtime. ExitStack
    closes every store even if shutdown or a preceding close raises.
    """
    runtime = app.runtime
    with ExitStack() as cleanup:
        cleanup.callback(runtime._memory_system.close)
        cleanup.callback(runtime._operational_store.close)
        cleanup.callback(runtime._filesystem_observation_store.close)
        app.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Isolated avatar-world Ollama probe')
    parser.add_argument('--case', action='append', choices=[case for case, _ in _CASES],
                        help='Run only this synthetic case; repeat for multiple cases.')
    parser.add_argument('--offer-scene', action='store_true',
                        help='Use an extra diagnostic avatar-scene frame on the offer only.')
    args = parser.parse_args(argv)
    # This changes only the current diagnostic process, not user settings.
    os.environ['SOFIA_IDLE_REFLECTIONS'] = '0'
    baseline = create_default_configuration()
    if baseline.provider.provider != 'ollama':
        raise RuntimeError('This diagnostic needs the configured Ollama provider.')
    print('AVATAR WORLD: real app + Ollama, disposable state per synthetic case.')
    print('No production conversation database, backup or model setting is modified.')
    print('This is NOT a replay of a saved live session.')
    print(f'Model: {baseline.provider.model}; thinking: {baseline.provider.thinking}; '
          f'num_ctx: {baseline.provider.context_size}')
    selected = set(args.case) if args.case else {case for case, _ in _CASES}
    for name, text in _CASES:
        if name not in selected:
            continue
        with TemporaryDirectory(prefix='sofia-avatar-world-') as directory:
            root = Path(directory)
            config = replace(baseline, state_path=root / 'isolated.db',
                             filesystem_root=root)
            app = SofiaApplication(config)
            changed = args.offer_scene and name == 'offer'
            scope = (patch.object(ExpandedConversationService, '_build_request',
                                  _build_offer_scene_request)
                     if changed else nullcontext())
            try:
                with scope:
                    app.start()
                    response = app.conversation.respond(text)
                    print(f'\nCASE {name}: {text}')
                    print(f'FRAME: {"diagnostic avatar scene" if changed else "unchanged production request"}')
                    print(f'RESPONSE: {response.content}')
            finally:
                _shutdown_disposable_app(app)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
