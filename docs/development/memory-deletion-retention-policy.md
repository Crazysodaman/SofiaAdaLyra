# Sofía Phase 07: Approved Option B memory deletion and backup retention

**Owner decision: 2026-10-11. Source-coded to `main`, no tests executed.**

## Contract

1. Only an **explicitly authorized memory candidate UUID** is erased by this
   first production capability. The original candidate summary, copied source
   provenance, reviewed expiration rows and correction links are physically
   deleted from active `sofia.db` under one SQLite transaction.
2. A separately authenticated **append-only deletion journal** is committed
   before active deletion. It contains scoped IDs and authority references,
   but **never the original memory text**. The journal and its OS lock file
   must be on protected storage **outside all state-home and backup archives**.
3. A journal-derived local SQLite guard prevents a later import from
   silently recreating the forgotten candidate ID. On configured runtime
   startup, the journal replays pending erasures before candidate access.
4. Backup restore, restore rehearsal and an approved future Venus-to-Sofia
   staged writer migration **refuse to publish** an old snapshot without the
   present authenticated journal and applying its erasure instructions to
   the staging database first. Other backup data still receives existing
   manifest authentication, schema, identity and Constitution checks.
5. Previously generated encrypted backup snapshots are **not modified or
   rewritten**; they are removed by the existing operator-selected
   `rotate --keep N` retention policy, under its safe archive-path checks.
   There is deliberately no silently imposed backup expiration date or
   autonomous destructive timer. Choose and document `N` and schedule
   rotation through the existing approved operator RUN/scheduler path.
6. "Forget memory candidate" does **not** mean delete the authoritative
   original conversation, media attachments, cloud copies, social messages,
   other candidates paraphrasing that fact or a remote service's backups.
   Those require **separate exact IDs and independent operator authority**.
   No user-facing API should promise wider deletion than it proves.

## Required offline operator workflow

A trusted operator must stop and fence the active Sofía runtime and dependent
writers first. Do not run these commands against a live, multi-writer SQLite
database. Keep the journal on its own approved, protected failure domain
and never let restore overwrite it. No LLM or untrusted task may choose
candidate UUIDs, grant deletion rights or approve destructive restoration.

Provision the journal once using the same operator-held 32-byte backup
authentication key:

```powershell
python -m sofia.memory.deletion_cli --key "<KEY_PATH>" --erasure-journal "<EXTERNAL_JOURNAL_PATH>" --state-path "<SOFIA_DB_PATH>" init-journal --approve-external-journal
```

After separately validating the original candidate ID, principal/audience and
operator approval receipt, and with the runtime stopped:

```powershell
python -m sofia.memory.deletion_cli --key "<KEY_PATH>" --erasure-journal "<EXTERNAL_JOURNAL_PATH>" --state-path "<SOFIA_DB_PATH>" forget-candidate --candidate-id "<UUID>" --confirm-candidate-id "<SAME_UUID>" --principal-id "person:sparks" --audience-id "local:text" --approval-ref "<OPERATOR_APPROVAL_REF>"
```

If the journal record was persisted but the process stopped before erasure
committed, run the replay while the runtime is still stopped:

```powershell
python -m sofia.memory.deletion_cli --key "<KEY_PATH>" --erasure-journal "<EXTERNAL_JOURNAL_PATH>" --state-path "<SOFIA_DB_PATH>" replay --approve-replay
```

To ensure a configured candidate store always heals a pending journal
after a crash, set these **outside the backed-up state home** for the Sofía
runtime service:

```text
SOFIA_MEMORY_ERASURE_JOURNAL=<EXTERNAL_JOURNAL_PATH>
SOFIA_MEMORY_ERASURE_KEY=<OPERATOR_PROTECTED_KEY_PATH>
```

If only one setting is present, runtime candidate memory initialization
fails closed. Missing or tampered journal, incorrect key, or conflicting
restored private scope similarly fails closed.

## Recover and retention

A restore command needs the journal even when restoring a snapshot that
predates the deletion:

```powershell
python -m sofia.ops.backup_cli restore --key "<KEY_PATH>" --backup-dir "<OLD_BACKUP>" --target-state "<NEW_SOFiA_DB>" --verifier "<OPERATOR_ID>" --erasure-journal "<EXTERNAL_JOURNAL_PATH>"
```

A rehearsal uses the same `--erasure-journal`. Staged state relocation
receives `erasure_journal_path` from the independently authorized operator.
Do not repurpose the journal path into any migrated/restored state root.

The existing retention command keeps the most recent **N** operator-chosen
backups and prunes older archives; N is a count, **not days**:

```powershell
python -m sofia.ops.backup_cli rotate --root "<BACKUP_ROOT>" --keep 14
```

`14` is illustrative only, **not** an approved default. Backup retention
must be set by the operator with a documented restoration-window requirement.
The external journal MUST outlive **all** backups and clones of their source
state, including offsite or offline media. Retention alone does not enforce
a request until the prior snapshots expire.

## Important limits

- A journal signed by the backup key proves record authenticity, but cannot
  prove that a **rolled-back, previously signed** journal is the newest one.
  Operators must maintain independent replication and freshness/failure-domain
  controls. A lost journal **blocks recovery**, not just an optional feature.
- SQLite `secure_delete` overwrites deleted cells, but does not promise
  forensic erasure of old filesystems, snapshots, SSD firmware, crash dumps,
  external search indexes or already delivered conversations. Live cache
  invalidation is achieved by shutting the runtime down and starting it
  after the deletion/replay.
- Automatic ordinary candidate **revocation** is not this destructive
  erasure mechanism. Operator review must choose the correct semantics.
- Future broader deletion (original message IDs, transcript removal, external
  archives, ephemeral embeddings, mobile devices) needs its own source
  inventory, exact scope contracts, signed tombstones and restore integration.
- All code and regression tests are unexecuted pending the user's final
  verification campaign. No production host changes were made.
