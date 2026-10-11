# Sofía portable conversation export, version 1

**Status (2026-10-11): source code and deferred tests on `main`. This is
an operator-invoked recovery aid, not an automatic backup, scheduled action,
production migration or permission grant. No live host execution or tests
were performed as part of this workstream.**

## Purpose

Preserve **the original bytes** of conversation messages, current
principal/audience bindings and separately linked Main/project thread
catalog references in an open, model-independent UTF-8 JSONL format.
A restored database is read in **SQLite read-only mode**; this operation
does not ask an LLM to reconstruct old speech, copy a synthesized recap
into memory, modify canonical source, or choose a replacement writer.

This format is specifically for an **operator-controlled, private offline
recovery copy**. The single output includes all available private, shared,
desktop, Discord and mobile audience records. An offline copy is **not**
permission to display a Discord message on another channel, restore
previously revoked source access, or send an outbound message.

## Before exporting

1. Retrieve the **encrypted backup bundle** and its separate 32-byte
   backup decryption key from your independently protected recovery process.
   The key and private export must never be placed on a public SMB share,
   in Git, or in an unencrypted synchronized folder.
2. On an offline or otherwise trusted machine, use an approved local
   filesystem with enough free disk space for a complete temporary
   decrypted restore and final JSONL file.
3. Install a compatible release of the Sofía backup CLI and its Python
   cryptography dependencies. No Ollama server, CUDA model or LLM is needed.
4. Choose a **new, absolute, local output path** ending in `.jsonl`.
   The file must not already exist. The output will contain sensitive
   plaintext. Owner authorization remains a human decision.

## Explicit owner command

Run from the project with the approved Python environment:

```bash
python -m sofia.ops.backup_cli verify \
  --key /secure/offline/backup.key \
  --backup-dir /offline/backups/verified-bundle

python -m sofia.ops.backup_cli export-jsonl \
  --key /secure/offline/backup.key \
  --backup-dir /offline/backups/verified-bundle \
  --output /secure/offline/export/sofia-conversations.jsonl \
  --approve-sensitive-plaintext
```

The command authenticates the original encrypted archive and performs a
full integrity-checked restore inside a temporary directory before
exporting. A missing explicit `--approve-sensitive-plaintext` flag
fails without producing plaintext. The exporter refuses path redirects,
remote/unverified output media, and overwriting an existing export.
On Unix, its newly created file is mode `0600`. Windows still requires
appropriate OS and folder ACLs.

## Verify without launching Sofía

The checker is a standalone **Python standard-library-only** program.
It does not import the Sofía package, decrypt a backup, access a
database, contact the network or require the original language model:

```bash
python tools/verify_sofia_portable_jsonl.py \
  /secure/offline/export/sofia-conversations.jsonl
```

You can copy that single script with the export. It validates the
schema, UTF-8 JSONL record structure, version, counts, footer, and
SHA-256 digest of the exact preceding output lines.

**Important:** JSONL SHA-256 is an *integrity error detector*, not an
authenticated signature. A malicious actor who can rewrite the entire
export can recompute an unkeyed checksum. Authenticate original recovery
data using the **encrypted manifest and protected key** before exporting;
independently protect the plaintext output with your chosen offline
media/backup security.

## Portable JSONL record layout

`schema = "sofia.portable-conversations.v1"`.

- `header`: schema, UTC creation time and explicit all-audience
  plaintext sensitivity.
- `original_message`: immutable original message ID, session, role,
  full UTF-8 content, original timestamp, current authenticated
  principal/audience/kind, or `unbound_not_authorized` when the source
  session currently has no binding.
- `thread`: canonical Main/project ID, owner, kind, name and original
  creation time. A thread title alone grants no visibility.
- `thread_source_link`: original source ID/session, original audience,
  visibility label and link timestamp. It reports whether the original
  message is currently present and whether its source audience still
  matches, rather than treating an old link as access authority.
- `footer`: exact message/thread/link counts and SHA-256 of all preceding
  JSONL lines. A truncated or edited file fails the standalone verifier.

Items are streamed in bounded SQLite keyset pages, so long-lived
transcripts do not require materializing all source rows at once.
The export preserves evidence references; it does not generate an
inferred topic history or automatically promote facts into long-term
memory.

## Scope and known limitations

This is a **conversation evidence export**, not a full portable Sofía
runtime snapshot, nor a complete human-recovery kit for encrypted
protected identity, goals, action receipts, voice assets, media, archive
chunks, embeddings, tombstones or the independent writer-fencing witness.
Those remain in the authenticated recovery bundle or separate
operator-controlled media.

Do not import this JSONL file into a live `sofia.db` directly, and
do not treat it as a device pairing token, consent receipt, safety grant,
or new writer authority. An erased original may have a remaining
source-link reference labelled unavailable; it must not be reconstructed
from guessed text. Full restore and verified migration must follow the
separate recovery/failover procedure.

**Deferred acceptance:** negative permission tests, local-only storage
and symlink checks, Unicode/source fidelity, page boundaries, truncated
and tampered file detection, original backups verified on clean Windows
and headless Debian, and an independently observed cold restore.
