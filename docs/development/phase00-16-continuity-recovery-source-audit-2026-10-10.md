# Continuing code/audit pass: lifelong memory and safe state mobility

**Reference:** GitHub `main` through `6d32ac9a5c20de4deeb24890b10e84b423d4fa72`.  
**Instruction:** code and source audits only; **no tests, no CI and no production state changes**. One `main` branch only.

## Source-backed findings and reuse decisions

| Area | Reused existing owner | Change / concrete benefit | Why no removal now |
| --- | --- | --- | --- |
| Lifelong retrieval | `ConversationStore` / `ConversationService` | `search_messages` now ranks all messages of the authenticated session directly in bounded SQL. Fixes recall's prior silent limit to 256 most recent matching rows; doesn't materialize the transcript. | Legacy `list_messages` is still used by UI/historical memory callers. Don't delete it before converting those callers and testing. |
| Cross-device owner threads | `SocialSessionStore` + `LifelongThreadStore` | Linked event reads join the *current* original message and session binding, checking principal, audience ID and audience kind. | Source transcripts and channel-specific social bindings are canonical; don't flatten private Discord/desktop audiences. |
| Offline companion | `OfflineDraftJournal` | Pending decrypts are device/principal/audience scoped; ciphertext hash is verified; a typed canonical-host acknowledgement with an independent signature verifier is mandatory before marking sent. | The offline journal is intentionally not a second Sofía; trusted transport/import and host receipt verifier are still not wired. |
| Topic detours | Existing `SQLiteConversationFocusStore` and `ProductionTurnKernel` | Focus-topic history persists alongside the existing CAS transaction. Explicit “back to [topic]” turns can read bounded audience-scoped topic IDs and source-turn refs without inventing an alternate focus manager. | Earlier reference-resolution logic is active. Keep it until acceptance proves replacement unnecessary. |
| Canonical database discoverability | Existing `RuntimeStorageLayout`, `BackupEngine`, `state_mobility` | Opt-in externally authenticated, writer-host-scoped and minimum-epoch-scoped state-home pointer. HMAC key and pointer must remain outside state home. | A valid pointer is **not** a writer lease. Old writer fencing and signed pointer promotion remain separate. |
| Staged relocation | `BackupEngine.create/verify/restore` | Reused encrypted consistent SQLite snapshot and semantic restore for a separately staged destination, only with independent operator/fencing proof callback. No switch or activation. | A raw `sofia.db` copy would lose WAL and protected-state consistency and is forbidden. |
| Previous LIFE/SAFE/EMOTION | Existing package owners | No alternative DB, self-authorization, emotion journal or GOALS/RUN executor was added in this pass. | Existing adapters and service/serialization boundaries require a full tested caller graph before removing. |

## Still unfinished coding

- **Phase 03:** genuine independently issued signed pointer, privileged fencing broker, fenced writer lease, destination asset inventory, safe cutover, pointer activation and rollback. Staging cannot be promoted by model text.
- **Phase 04:** authenticated offline transport/host ingestion, host-generated receipts, replay proof and real device reconnection UI.
- **Phase 05:** complete Main+project thread UI across devices, cross-audience reviewed disclosure, client ordering/conflict resolution and topic-return quality for pronouns/ellipsis.
- **Phase 06:** indexed full-text search for years of data, temporal truth review, exact correction/supersession and memory benchmarks. The current SQL ranks all matching rows but may still scan the full message table.
- **Phase 00/01/02 and Phases 07–16:** remain only partially coded, not declared complete. All test and production acceptance gates are deferred by explicit instruction.

## Removal decision

**No production file deleted.** GitHub source search confirms `ConversationStore.list_messages` is still referenced outside the newly bounded model call path, including memory originals and UI APIs. Likewise, Cognition v2 focus is already the source of truth, so adding a new topic authority would be an architectural regression. Only remove code after a complete caller/import, serialization compatibility and exact-SHA verification audit.

## Validation policy

New source was inspected at GitHub paths and comments/contracts were compared to call signatures. No tests, Python imports, SQLite migration execution, PowerShell, Windows services, real model inference, UI startup or database copy were performed. The presence of code in `main` is **not** a passing test.
