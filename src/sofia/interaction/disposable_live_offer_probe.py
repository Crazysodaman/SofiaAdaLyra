"""Supervised real-Qwen offer probe using a TEMPORARY application database only.

Run explicitly with --run-disposable. No production conversation, preferences,
model settings, actual actions, animations or sensor state are modified.
The synthetic boundary is test evidence, NOT an authentic Sofía preference.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sofia.application.bootstrap import SofiaApplication
from sofia.config.defaults import create_default_configuration
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.interaction import live_offer_service
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState

_SYNTHETIC_BOUNDARY = 'I do not want hugs in this avatar scene.'


def _show(label, result, reply: str) -> None:
    print('\nCASE:', label)
    print('GATE STATUS:', result.status)
    if result.choice is not None:
        print('CHOICE:', result.choice.choice)
        print('DECISION REASON (diagnostic only):', result.choice.reason)
        print('DECISION FLAGS (heuristic only):', result.decision_findings)
        print('EXPRESSION FLAGS (heuristic only):', result.expression_findings)
    print('SAVED ASSISTANT REPLY:', reply)


def run_disposable_probe() -> None:
    """Construct the actual app with an independently isolated state path."""
    with TemporaryDirectory(prefix='sofia-interact-supervised-') as directory:
        root = Path(directory).resolve()
        state = root / 'disposable-sofia.db'
        defaults = create_default_configuration()
        if state == Path(defaults.state_path).resolve() or not state.is_relative_to(root):
            raise RuntimeError('Disposable state isolation check failed.')
        config = replace(defaults, state_path=state, filesystem_root=root)
        if config.provider.provider != 'ollama' or config.provider.model != 'qwen3:14b':
            raise RuntimeError('Probe requires the existing configured qwen3:14b model.')

        print('SUPERVISED REAL-APPLICATION OFFER PROBE')
        print('Temporary database:', state)
        print('Production state path is NOT used:', Path(defaults.state_path).resolve())
        print('Model:', config.provider.model, 'thinking:', config.provider.thinking,
              'num_ctx:', config.provider.context_size)
        print('All source evidence in the second case is SYNTHETIC.')
        print('No contact, consent, animation, tool action or real sensing occurs.')
        print('Human inspection is required; absent heuristic flags prove nothing.')

        app = SofiaApplication(config)
        # Provision the optional interaction schemas ONLY on the temporary DB.
        InteractionLedger(state)
        verifier = VerifiedInteractionState(
            state, InteractionCatalog(('head', 'left-hand', 'right-hand')),
        )
        started = False
        outcomes = []
        original_gate = live_offer_service.run_guarded_offer

        def observe_gate(**kwargs):
            result = original_gate(**kwargs)
            outcomes.append(result)
            return result

        # Environment changes live only within this process and this scope.
        with patch.dict(os.environ, {
            'SOFIA_INTERACT_STAGED_OFFERS': '1',
            'SOFIA_IDLE_REFLECTIONS': '0',
        }):
            try:
                app.start()
                started = True
                session = app.conversation.session
                if session is None:
                    raise RuntimeError('Application did not start its conversation.')
                engine = app.runtime.cognitive_system.engine
                provider = engine.provider
                with (patch.object(provider, 'respond', wraps=provider.respond) as spy,
                      patch.object(live_offer_service, 'run_guarded_offer',
                                   side_effect=observe_gate)):
                    first = app.conversation.respond(OFFER)
                    if len(outcomes) != 1 or outcomes[-1].status != 'responded':
                        raise RuntimeError('First offer did not complete the guarded path.')
                    if spy.call_count != 2:
                        raise RuntimeError('Expected choice and expression inference only.')
                    _show('no recorded boundary', outcomes[-1], first.content)

                    # Explicitly test-only simulated Sofía statement, followed
                    # by independently attested policy data in disposable DB.
                    now = datetime.now(timezone.utc)
                    source = ConversationMessage(
                        id=str(uuid4()), session_id=session.id,
                        role=ConversationRole.ASSISTANT,
                        content=_SYNTHETIC_BOUNDARY, created_at=now,
                    )
                    app.conversation._conversation_store.save(source)
                    verifier.record_boundary(
                        revision_id=str(uuid4()), subject='sofia',
                        semantic_id='hug', region_id='*', active=True,
                        source_id=source.id, session_id=session.id,
                        exact_content=_SYNTHETIC_BOUNDARY,
                        reviewer_id='synthetic-disposable-probe-only',
                        prior_id=None, at=now,
                    )
                    print('\nSynthetic no-hugs boundary recorded and source-attested in TEMP DB.')
                    before = spy.call_count
                    second = app.conversation.respond(OFFER)
                    if len(outcomes) != 2 or outcomes[-1].status != 'blocked-boundary':
                        raise RuntimeError('Second offer was not blocked by verified boundary.')
                    if spy.call_count != before:
                        raise RuntimeError('Model inference occurred despite active boundary.')
                    _show('synthetic attested no-hugs boundary', outcomes[-1], second.content)

                    saved = app.conversation.messages()
                    if (sum(m.role is ConversationRole.USER and m.content == OFFER
                            for m in saved) != 2
                            or sum(m.role is ConversationRole.ASSISTANT and
                                   m.content == first.content for m in saved) < 1
                            or saved[-1].content != second.content):
                        raise RuntimeError('Saved conversation did not match probe replies.')
                    print('\nDISPOSABLE INTEGRATION CHECKS: PASS')
                    print('Provider calls for two offers:', spy.call_count)
                    print('This does NOT certify the human-reviewed quality of reply one.')
            finally:
                if started:
                    app.shutdown()
                else:
                    app.conversation.close()
    print('Temporary database directory exited; no production DB was opened.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-disposable', action='store_true',
                        help='Explicitly run real Qwen with temporary app state.')
    args = parser.parse_args()
    if not args.run_disposable:
        parser.error('Use --run-disposable to opt into the temporary real-model probe.')
    run_disposable_probe()


if __name__ == '__main__':
    main()
