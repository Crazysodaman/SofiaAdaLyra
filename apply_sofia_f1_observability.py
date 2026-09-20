"""Apply only Batch F.1 live-test progress reporting to Sofía's local checkout.

Run from the SofiaAdaLyra repository root. Makes no commits or pushes.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import subprocess
from pathlib import Path

TARGET = Path('test/test_embodiment_prompt_regression.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one source anchor; found {count}. No changes made.')
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Preflight and print diff without changing the file')
    args = parser.parse_args()

    if not Path('AGENTS.MD').is_file() or not TARGET.is_file():
        raise SystemExit('Run this script from the SofiaAdaLyra repository root. No changes made.')
    clean = subprocess.run(['git', 'diff', '--quiet', '--', str(TARGET)], check=False)
    if clean.returncode != 0:
        raise SystemExit(f'{TARGET} has local modifications (or Git failed); inspect it first. No changes made.')

    original_bytes = TARGET.read_bytes()
    bom = original_bytes.startswith(b'\xef\xbb\xbf')
    original = original_bytes.decode('utf-8-sig')
    if '\r' in original.replace('\r\n', ''):
        raise SystemExit('Unsupported mixed/CR-only newlines. No changes made.')
    newline = '\r\n' if '\r\n' in original else '\n'
    content = original.replace('\r\n', '\n')

    content = replace_once(
        content,
        'import os\nimport re\n',
        'import os\nimport re\nimport time\n',
        'time import',
    )

    helper = '''\n\ndef observe_live_generation(\n    provider: OllamaProvider,\n    request: CognitiveRequest,\n    label: str,\n) -> CognitiveResponse:\n    """Report progress without changing the provider response or assertions."""\n    print(f"[OLLAMA] START: {label}", flush=True)\n    started = time.perf_counter()\n\n    try:\n        response = provider.respond(request)\n    except Exception as exc:\n        elapsed = time.perf_counter() - started\n        print(\n            f"[OLLAMA] FAILED: {label} "\n            f"after {elapsed:.1f}s "\n            f"({type(exc).__name__}: {exc})",\n            flush=True,\n        )\n        raise\n\n    elapsed = time.perf_counter() - started\n    print(\n        f"[OLLAMA] COMPLETE: {label} in {elapsed:.1f}s",\n        flush=True,\n    )\n    return response\n'''
    content = replace_once(
        content,
        '\n\ndef extract_measurements(\n',
        helper + '\n\ndef extract_measurements(\n',
        'helper insertion',
    )
    content = replace_once(
        content,
        '        response = provider.respond(\n            variant\n        )\n',
        '        response = observe_live_generation(\n            provider,\n            variant,\n            name,\n        )\n',
        'variant call',
    )
    content = replace_once(
        content,
        '        response = provider.respond(\n            request\n        )\n',
        '        response = observe_live_generation(\n            provider,\n            request,\n            f"Generation {generation}/{REPEATED_GENERATION_COUNT}",\n        )\n',
        'repeated-generation call',
    )

    ast.parse(content, filename=str(TARGET))
    diff = ''.join(difflib.unified_diff(
        original.replace('\r\n', '\n').splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile=f'a/{TARGET}', tofile=f'b/{TARGET}',
    ))
    print(diff)
    if args.check:
        print('Preflight successful; no files changed.')
        return

    updated = content.replace('\n', newline)
    encoded = (b'\xef\xbb\xbf' if bom else b'') + updated.encode('utf-8')
    if TARGET.read_bytes() != original_bytes:
        raise SystemExit('Target changed during preflight; no changes made.')
    TARGET.write_bytes(encoded)
    print(f'Updated {TARGET} only. No commits or pushes made.')


if __name__ == '__main__':
    main()
