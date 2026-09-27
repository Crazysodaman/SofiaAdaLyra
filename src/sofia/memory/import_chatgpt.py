from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sofia.config import create_default_configuration
from sofia.memory.chatgpt_import import parse_chatgpt_memory_dump
from sofia.memory.chatgpt_import_store import ChatGPTMemoryImportStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.memory.import_chatgpt"
    )
    parser.add_argument(
        "input",
        help="Path to the ChatGPT memory dump text or JSON file.",
    )
    parser.add_argument(
        "--state-path",
        help="Sofía SQLite state path. Defaults to configured state_path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without writing to Sofía state.",
    )
    args = parser.parse_args(argv)

    source = Path(args.input)
    try:
        payload = source.read_text(encoding="utf-8-sig")
        batch = parse_chatgpt_memory_dump(payload)
        if args.dry_run:
            print(
                f"ChatGPT memory dump valid: {len(batch.items)} items "
                f"digest={batch.source_digest}"
            )
            return 0

        state_path = (
            Path(args.state_path)
            if args.state_path
            else Path(create_default_configuration().state_path)
        )
        store = ChatGPTMemoryImportStore(state_path)
        try:
            created = store.save(
                batch,
                original_payload=payload,
            )
        finally:
            store.close()

        status = "imported" if created else "already_imported"
        print(
            f"ChatGPT memory dump {status}: {len(batch.items)} items "
            f"digest={batch.source_digest}"
        )
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"ChatGPT memory import refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
