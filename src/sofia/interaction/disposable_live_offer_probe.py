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
from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate

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


def _close_disposable_app(app: SofiaApplication, *, started: bool) -> None:
    """Close ALL app-owned SQLite handles before Windows removes temp files.

    SofiaApplication.shutdown() closes conversation, but current runtime
    lifetime retains separate memory, operational and workspace observation
    connections. Close them here ONLY on the disposable instance.
    """
    try:
        if started:
            app.shutdown()
        else:
            app.conversation.close()
    finally:
        try:
            app.runtime.memory_system._store.close()
        finally:
            try:
                app.runtime.operational_store.close()
            finally:
                app.runtime.filesystem_observation_store.close()


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
        started = False
        outcomes = []
        provider_outputs = []
        try:
            InteractionLedger(state)
            verifier = VerifiedInteractionState(
                state, InteractionCatalog(('head', 'left-hand', 'right-hand')),
            )
            original_gate = live_offer_service.run_guarded_offer

            def observe_gate(**kwargs):
                result = original_gate(**kwargs)
                outcomes.append(result)
                return result

            with patch.dict(os.environ, {
                'SOFIA_INTERACT_STAGED_OFFERS': '1',
                'SOFIA_IDLE_REFLECTIONS': '0',
            }):
                app.start()
                started = True
                session = app.conversation.session
                if session is None:
                    raise RuntimeError('Application did not start its conversation.')
                provider = app.runtime.cognitive_system.engine.provider
                original_respond = provider.respond

                def observe_provider(request):
                    response = original_respond(request)
                    provider_outputs.append(response)
                    return response

                with (patch.object(provider, 'respond', side_effect=observe_provider) as spy,
                      patch.object(live_offer_service, 'run_guarded_offer',
                                   side_effect=observe_gate)):
                    first = None
                    try:
                        first = app.conversation.respond(OFFER)
                    except ValueError as exc:
                        if 'Expression contradicts' not in str(exc):
                            raise
                        if len(provider_outputs) != 2 or spy.call_count != 2:
                            raise RuntimeError('Unexpected inference count on expression veto.') from exc
                        print('\nCASE: no recorded boundary')
                        print('GATE STATUS: expression-contradiction-veto; no assistant reply released')
                        print('RAW DECISION (diagnostic only):', provider_outputs[0].content)
                        print('RAW EXPRESSION (NOT SAVED):', provider_outputs[1].content)
                        if app.conversation.messages()[-1].role is not ConversationRole.USER:
                            raise RuntimeError('Vetoed expression unexpectedly persisted an assistant reply.')
                    else:
                        if len(outcomes) != 1 or outcomes[-1].status != 'responded':
                            raise RuntimeError('First offer did not complete the guarded path.')
                        if spy.call_count != 2:
                            raise RuntimeError('Expected choice and expression inference only.')
                        _show('no recorded boundary', outcomes[-1], first.content)

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
                    prior_outcomes = len(outcomes)
                    second = app.conversation.respond(OFFER)
                    # The live host now blocks BEFORE context assembly, so
                    # run_guarded_offer is intentionally NOT called here.
                    if (len(outcomes) != prior_outcomes
                            or _policy_gate(state_path=state, session_id=session.id) != 'blocked-boundary'
                            or 'recorded interaction boundary' not in second.content):
                        raise RuntimeError('Second offer was not blocked by verified boundary.')
                    if spy.call_count != before:
                        raise RuntimeError('Model inference occurred despite active boundary.')
                    _show('synthetic attested no-hugs boundary',
                          GuardedOfferResult(status='blocked-boundary'), second.content)

                    saved = app.conversation.messages()
                    if (sum(m.role is ConversationRole.USER and m.content == OFFER
                            for m in saved) != 2
                            or saved[-1].content != second.content
                            or saved[-1].role is not ConversationRole.ASSISTANT):
                        raise RuntimeError('Saved conversation did not match probe replies.')
                    if first is not None and not any(
                        m.role is ConversationRole.ASSISTANT and m.content == first.content
                        for m in saved
                    ):
                        raise RuntimeError('First completed reply was not saved.')
                    if first is None and any(
                        m.role is ConversationRole.ASSISTANT and
                        m.content == provider_outputs[1].content for m in saved
                    ):
                        raise RuntimeError('Vetoed expression leaked into conversation history.')
                    print('\nDISPOSABLE INTEGRATION CHECKS: PASS')
                    print('Provider calls for two offers:', spy.call_count)
                    print('This does NOT certify the human-reviewed quality of reply one.')
        finally:
            _close_disposable_app(app, started=started)
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
