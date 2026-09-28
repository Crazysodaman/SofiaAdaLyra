from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from sofia.config import create_default_configuration
from sofia.memory.chatgpt_export import parse_chatgpt_export_archive
from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.memory.chatgpt_import import parse_chatgpt_memory_dump
from sofia.memory.chatgpt_import_store import ChatGPTMemoryImportStore
from sofia.memory.chatgpt_migration import ChatGPTMemoryMigrationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.memory.import_chatgpt"
    )
    parser.add_argument(
        "input",
        help="Path to a ChatGPT memory dump text/JSON file or full export ZIP.",
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
    parser.add_argument(
        "--promote-all",
        action="store_true",
        help=(
            "Explicitly promote every imported item into Sparks-scoped "
            "reviewed memory after proposing it."
        ),
    )
    parser.add_argument(
        "--approved-by",
        default=None,
        help="Required as Sparks when --promote-all is used.",
    )
    args = parser.parse_args(argv)

    source = Path(args.input)
    try:
        if args.promote_all and args.approved_by != "Sparks":
            raise PermissionError(
                "--promote-all requires explicit --approved-by Sparks"
            )
        if not args.promote_all and args.approved_by is not None:
            raise ValueError(
                "--approved-by is only valid with --promote-all"
            )

        state_path = (
            Path(args.state_path)
            if args.state_path
            else Path(create_default_configuration().state_path)
        )

        if source.suffix.casefold() == ".zip":
            if args.promote_all:
                raise PermissionError(
                    "full ChatGPT conversation exports are source evidence; "
                    "blind --promote-all is not allowed"
                )
            export_batch = parse_chatgpt_export_archive(
                source.read_bytes()
            )
            if args.dry_run:
                print(
                    "ChatGPT export valid: "
                    f"{len(export_batch.conversations)} conversations "
                    f"{export_batch.message_count} visible messages "
                    f"{export_batch.attachment_count} attachment links "
                    f"skipped_do_not_remember="
                    f"{export_batch.skipped_do_not_remember} "
                    f"skipped_memory_disabled="
                    f"{export_batch.skipped_memory_disabled} "
                    f"digest={export_batch.source_digest}"
                )
                return 0
            export_store = ChatGPTExportEvidenceStore(state_path)
            created = export_store.save(export_batch)
            status = "imported" if created else "already_imported"
            print(
                f"ChatGPT export {status}: "
                f"{len(export_batch.conversations)} conversations "
                f"{export_batch.message_count} visible messages "
                f"{export_batch.attachment_count} attachment links "
                f"skipped_do_not_remember="
                f"{export_batch.skipped_do_not_remember} "
                f"skipped_memory_disabled="
                f"{export_batch.skipped_memory_disabled} "
                f"digest={export_batch.source_digest} "
                "memory_status=evidence_only"
            )
            return 0

        payload = source.read_text(encoding="utf-8-sig")
        batch = parse_chatgpt_memory_dump(payload)
        if args.dry_run:
            print(
                f"ChatGPT memory dump valid: {len(batch.items)} items "
                f"digest={batch.source_digest}"
            )
            return 0

        store = ChatGPTMemoryImportStore(state_path)
        migration = None
        try:
            created = store.save(
                batch,
                original_payload=payload,
            )
            migration = ChatGPTMemoryMigrationService(
                state_path,
                imports=store,
            )
            candidate_ids = migration.propose_batch(
                batch.source_digest
            )
            if args.promote_all:
                migration.promote_batch(
                    batch.source_digest,
                    approved_by=args.approved_by,
                    at=datetime.now(timezone.utc),
                )
        finally:
            if migration is not None:
                migration.close()
            store.close()

        status = "imported" if created else "already_imported"
        memory_status = (
            "promoted"
            if args.promote_all
            else "proposed_for_review"
        )
        print(
            f"ChatGPT memory dump {status}: {len(batch.items)} items "
            f"digest={batch.source_digest} "
            f"candidates={len(candidate_ids)} "
            f"memory_status={memory_status}"
        )
        return 0
    except (
        LookupError,
        OSError,
        PermissionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"ChatGPT memory import refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
