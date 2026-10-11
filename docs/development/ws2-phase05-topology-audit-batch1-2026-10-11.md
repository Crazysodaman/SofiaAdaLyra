# Workstream 2 • Phase 05 original topology audit, batch 1

**Date:** 2026-10-11. **Branch:** `main` only.  
**Classification:** traced source is `partial_wiring`, never accepted. The user defers all test/CI/build/live operations.

| Original ID | Actual production source found | What's still missing |
| --- | --- | --- |
| CA-4101 | `ConversationStore` persists `conversation_sessions` and `conversation_messages` in canonical SQLite; `ConversationService.start(session_id=...)` explicitly attaches only a known saved session; `SocialSessionStore.bind` makes source audiences immutable. | An end-user authenticated cross-channel experience cannot be inferred merely from this persistence/resume contract; full client acceptance unrun. |
| CA-4102 | `LifelongThreadStore.get_or_create` owns stable per-principal `main` and optional named `project` logical threads, separate from per-channel source sessions. Unique partial index `lifelong_one_main` enforces one owner Main, while original-source links retain their audience and timestamps. | Full project-thread lifecycle, per-channel default selection UX and long-term import acceptance are not complete. |
| CA-4112 | `LifelongThreadStore.preview_historical_import`, `apply_historical_import`, `rollback_historical_import` re-use the original messages/sessions and keep the reviewed canonical Main linking separate. Item 70 added bounded `next_cursor` pagination for sessions longer than 128 messages; items 71–72 fence withdrawn reviews and already adopted canonical links. | Reviewed migration must be exercised across actual desktop, Discord and mobile histories with duplicate/overlap, rollback and privacy leakage tests; no automatic import. |
| CA-5301 | `LifelongThreadStore` `main` logical ID owned by authenticated principal; `canonical_conversation_turn` and `lifelong_thread_event` preserve separate source session and audience per event. | All real desktop, Discord, Terra and phone services must be proven to attach/synchronize according to this one-owner Main contract; no credentials or tool grants cross channel. |
| CA-5501 | Same canonical Main/project table plus `SocialSessionStore` and `ConversationService.start(session_id)` demonstrate that `thread_id` and `conversation_session.id` are distinct identities, with indexed original links instead of copied/transformed source text. | Approved topology ADR, archive/pin/rename/resume controls and audited clients not yet signed off. |

## Coding delivered in this audit continuation

- **Item 69** immutable admission identity required for uncertainty transition: `4a772feaf1d9f70fc09890340c22c4f470371b7e`. Deferred regression `c260837c8f0ec323ef317c3a8b31ac862b5a4953`.
- **Item 70** original-session keyset reviewed-history pagination: `6292828ec3fdcd7838e25a0853dcd5d0f4675542`. Deferred regression `6a59382a94bc88d5a1952e44488d1e066bb579a8`.
- **Item 71** independent final owner-approval check before history import or rollback effects: `3102d60c5760c6d49735d8d434571df6dbbd1149`. Deferred regression `7657c9da9fc6ceb8414915977b22f1b0edf9a690`.
- **Item 72** decline historical rollback of links later adopted by separately ordered canonical turns: `9b12131a88228c4e3a4c681863a02053c87ef083`. Deferred regression `0cf40c354d58f7c1b6c13c2ac3d982fba821257b`.

None of the above performs a historical import, erases a source, authorizes a privilege transfer, starts a VM, migrates databases, sends notifications, runs tests or proves full production readiness.

## Next source gates

1. Canonical Main delivery routing and per-channel receipt/sync consistency across desktop, Discord and Android.
2. Project-thread creation, active-thread selection, explicit linking/archiving and owner-audience restrictions.
3. Topic-switch/retrieval continuity with source-backed context rather than full lifetime transcript loading.
4. Cross-host writer fencing and canonical-state relocation remain separately required for future Artemis ownership.
