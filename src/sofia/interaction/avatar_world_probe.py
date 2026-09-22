"""Review avatar-world conversation with Qwen in disposable application state.

Run: python -m sofia.interaction.avatar_world_probe

Uses the real application and Ollama provider, but never reads, resets, exports
or writes the normal state/sofia.db. Each synthetic case has an independent
temporary database and filesystem root. All temporary app instances are closed.
The model output is observational evidence, not proof of emotions or animation.
"""
from __future__ import annotations

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
                app.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
