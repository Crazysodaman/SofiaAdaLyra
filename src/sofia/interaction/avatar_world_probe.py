"""Review avatar-world conversation with Qwen in disposable application state.

Run: python -m sofia.interaction.avatar_world_probe

Uses the real application and Ollama provider, but never reads, resets, exports
or writes the normal state/sofia.db. Each synthetic case has an independent
temporary database and filesystem root. The model output is observational
evidence, not proof of emotions or animation.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from sofia.application.bootstrap import SofiaApplication
from sofia.config.defaults import create_default_configuration

_CASES = (
    ('offer', 'I ask to hug you'),
    ('ear', '*pats your left ear*'),
    ('physical capability', 'Can you physically feel my hand through a real sensor?'),
)


def _shutdown_disposable_app(app: SofiaApplication) -> None:
    """Close *all* disposable SQLite owners before Windows removes the DB.

    Runtime shutdown records stop evidence but currently does not close its
    memory, operational and filesystem-observation stores. These are owned by
    this isolated probe's composition, not by any production runtime. ExitStack
    closes every store even when shutdown or a preceding close raises. A
    general runtime lifecycle change needs independent restart review.
    """
    runtime = app.runtime
    with ExitStack() as cleanup:
        cleanup.callback(runtime._memory_system._store.close)
        cleanup.callback(runtime._operational_store.close)
        cleanup.callback(runtime._filesystem_observation_store.close)
        app.shutdown()


def main() -> int:
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
    for name, text in _CASES:
        with TemporaryDirectory(prefix='sofia-avatar-world-') as directory:
            root = Path(directory)
            config = replace(baseline, state_path=root / 'isolated.db',
                             filesystem_root=root)
            app = SofiaApplication(config)
            try:
                app.start()
                response = app.conversation.respond(text)
                print(f'\nCASE {name}: {text}')
                print(f'RESPONSE: {response.content}')
            finally:
                _shutdown_disposable_app(app)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
